"""RedisStreamsAdapter — the scan-queue I/O boundary. Decisions live in
houba.domain.scan_queue; this is the broker adapter (QueuePort). INVARIANT:
XACK is always the last op — every durable side-effect completes first. No retry
logic (CLAUDE.md): a connection loss raises QueueUnavailableError; the worker pod
exits, k8s restarts it, and stream redelivery covers the entry."""

from __future__ import annotations

import functools
from collections.abc import Callable
from datetime import datetime
from typing import Any

import redis

from houba.domain.scan_queue import coverage_gap, should_dead_letter
from houba.errors import QueueError, QueueUnavailableError
from houba.ports.queue import Reservation


def _wrap[T](fn: Callable[..., T]) -> Callable[..., T]:
    @functools.wraps(fn)
    def inner(*a: Any, **k: Any) -> T:
        try:
            return fn(*a, **k)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            raise QueueUnavailableError(str(e)) from e
        except redis.exceptions.RedisError as e:
            raise QueueError(str(e)) from e

    return inner


def _iso_to_epoch(iso: str) -> float:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        raise ValueError(f"attested_at must be timezone-aware: {iso!r}")
    return dt.timestamp()


class RedisStreamsAdapter:
    def __init__(
        self,
        client: redis.Redis,
        *,
        consumer: str,
        work: str = "houba:scan:work",
        dead: str = "houba:scan:dead",
        confirmed: str = "houba:scan:confirmed",
        placed: str = "houba:scan:placed",
        group: str = "scan",
    ) -> None:
        self._r: Any = client
        self._consumer = consumer
        self._work, self._dead, self._confirmed, self._placed, self._group = (
            work,
            dead,
            confirmed,
            placed,
            group,
        )
        self.ensure_group()

    @_wrap
    def ensure_group(self) -> None:
        try:
            self._r.xgroup_create(self._work, self._group, id="0", mkstream=True)
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    @_wrap
    def enqueue(self, refs: list[str]) -> None:
        for ref in refs:
            self._r.xadd(self._work, {"ref": ref})
            if "@" in ref:
                self._r.sadd(self._placed, ref.split("@", 1)[1])  # placed-set for coverage check

    @_wrap
    def reserve(self, *, block_ms: int = 5000) -> Reservation | None:
        """XREADGROUP one new entry. Returns Reservation or None if the stream is empty."""
        resp: Any = self._r.xreadgroup(
            self._group, self._consumer, {self._work: ">"}, count=1, block=block_ms
        )
        if not resp:
            return None
        _stream, entries = resp[0]
        if not entries:
            return None
        msg_id, fields = entries[0]
        return Reservation(token=str(msg_id), ref=str(fields["ref"]))

    @_wrap
    def ack(self, res: Reservation, *, digest: str, attested_at: str) -> None:
        """Success path. INVARIANT order: ZADD confirmed (durable) -> XACK -> trim."""
        epoch = _iso_to_epoch(attested_at)
        self._r.zadd(self._confirmed, {digest: epoch})
        self._r.xack(self._work, self._group, res.token)
        self._trim_minid()

    def _dead_letter_no_trim(self, token: str, ref: str, reason: dict[str, str]) -> None:
        # XADD dead (durable) BEFORE XACK on work — invariant preserved.
        payload = {"ref": ref, **{k: str(v) for k, v in reason.items()}}
        self._r.xadd(self._dead, payload)
        self._r.xack(self._work, self._group, token)

    @_wrap
    def dead_letter(self, res: Reservation, *, ref: str, reason: dict[str, str]) -> None:
        """Route a failed entry to the dead stream. INVARIANT: XADD dead (durable)
        BEFORE XACK on work — a crash between them re-delivers and re-dead-letters
        (a dedupable duplicate), never a loss. Trim is encapsulated here (the work
        stream's processed entries are reclaimed), so callers never manage trimming."""
        self._dead_letter_no_trim(res.token, ref, reason)
        self._trim_minid()

    def _trim_minid(self) -> None:
        """Reclaim fully-processed entries WITHOUT evicting an un-acked OR un-read entry.
        XTRIM MINID X keeps id >= X. Floor = the oldest entry still needed (un-acked or un-read)."""
        pend: Any = self._r.xpending(self._work, self._group)
        if pend["pending"]:
            # oldest still-pending (delivered, un-acked) entry and everything after it survive
            self._r.xtrim(self._work, minid=pend["min"], approximate=False)
            return
        groups: Any = {g["name"]: g for g in self._r.xinfo_groups(self._work)}
        last_delivered: str = str(groups[self._group]["last-delivered-id"])
        if last_delivered == "0-0":
            return
        # Requires Redis >= 6.2 (XAUTOCLAIM, XTRIM MINID) + XINFO last-generated-id;
        # the pipeline runs redis:7.
        xinfo: Any = self._r.xinfo_stream(self._work)
        last_generated: str = str(xinfo["last-generated-id"])
        if last_delivered == last_generated:
            # nothing un-read: every entry is read+acked -> reclaim all of them
            ts, _seq = last_delivered.split("-")
            self._r.xtrim(self._work, minid=f"{int(ts) + 1}-0", approximate=False)
        else:
            # un-read entries exist (their id > last_delivered) -> keep them; trim only the
            # fully-acked prefix below last_delivered. The acked last_delivered entry lingers
            # one cycle (harmless; reclaimed once a later entry is acked).
            self._r.xtrim(self._work, minid=last_delivered, approximate=False)

    @_wrap
    def reaper(self, *, min_idle_ms: int, max_deliveries: int) -> list[str]:
        """Claim entries idle > min_idle_ms (a dead worker, OR a slow-alive scan past the
        window — the claim is purely idle-based). Past max_deliveries, route to the dead
        stream. Trim after."""
        cursor = "0-0"
        claimed: list[str] = []
        while True:
            result: Any = self._r.xautoclaim(
                self._work, self._group, self._consumer, min_idle_ms, start_id=cursor, count=50
            )
            cursor, msgs, _deleted = result[0], result[1], result[2]
            for msg_id, fields in msgs:
                claimed.append(str(msg_id))
                rng: Any = self._r.xpending_range(
                    self._work, self._group, min=str(msg_id), max=str(msg_id), count=1
                )
                delivered: int = int(rng[0]["times_delivered"]) if rng else 1
                if should_dead_letter(delivered, max_deliveries):
                    ref = str(fields.get("ref", ""))
                    self._dead_letter_no_trim(str(msg_id), ref, {"error": "max retries"})
            if cursor == "0-0":
                break
        self._trim_minid()
        return claimed

    @_wrap
    def coverage_check(self, placed: list[str], *, max_age_s: int, now: float) -> list[str]:
        """Fresh coverage gap = placed - {digests confirmed within max_age}. Cheap: one
        ZRANGEBYSCORE + a set-diff (the pure function). No DT query, no registry walk."""
        raw: Any = self._r.zrangebyscore(self._confirmed, now - max_age_s, now)
        fresh: set[str] = {str(v) for v in raw}
        return coverage_gap(set(placed), fresh)

    @_wrap
    def dlq_list(self) -> list[dict[str, str]]:
        entries: Any = self._r.xrange(self._dead)
        return [
            {"id": str(mid), **{str(k): str(v) for k, v in fields.items()}}
            for mid, fields in entries
        ]

    @_wrap
    def dlq_replay(self, selector: str) -> int:
        """Re-enqueue every dead entry matching the selector (full digest, bare hex, or
        `--all`); remove it from the dead stream. Returns the count moved."""
        moved = 0
        entries: Any = self._r.xrange(self._dead)
        for mid, fields in entries:
            ref = str(fields.get("ref", ""))
            if _ref_matches(ref, selector):
                self._r.xadd(self._work, {"ref": ref})
                self._r.xdel(self._dead, str(mid))
                moved += 1
        return moved

    @_wrap
    def dlq_drop(self, selector: str) -> int:
        """Permanently drop every dead entry matching the selector (full digest or bare hex).
        Returns the count dropped."""
        dropped = 0
        entries: Any = self._r.xrange(self._dead)
        for mid, fields in entries:
            ref = str(fields.get("ref", ""))
            if _ref_matches(ref, selector):
                self._r.xdel(self._dead, str(mid))
                dropped += 1
        return dropped


def _ref_matches(ref: str, selector: str) -> bool:
    """Match a dead-entry ref against an operator selector. Accepts the full digest
    (`sha256:hex`) OR the bare hex (what an operator naturally copies from `scan-dlq list`).
    `--all` matches everything; an empty selector matches nothing (never a silent match-all)."""
    if selector == "--all":
        return True
    if not selector or "@" not in ref:
        return False
    digest = ref.split("@", 1)[1]  # "sha256:hex"
    return digest == selector or digest.split(":")[-1] == selector.split(":")[-1]
