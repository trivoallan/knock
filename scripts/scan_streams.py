"""Thin redis-py I/O for the scan pipeline. The DECISIONS live in scan_queue.py
(pure, unit-tested); this module is the broker boundary.

INVARIANT: XACK is always the last op — every durable side-effect completes first."""

from __future__ import annotations

import os

import redis

from houba.domain.scan_queue import coverage_gap, should_dead_letter

WORK = os.environ.get("REDIS_WORK_STREAM", "houba:scan:work")
DEAD = os.environ.get("REDIS_DEAD_STREAM", "houba:scan:dead")
CONFIRMED = os.environ.get("REDIS_CONFIRMED_ZSET", "houba:scan:confirmed")
PLACED = os.environ.get("REDIS_PLACED_SET", "houba:scan:placed")
GROUP = os.environ.get("REDIS_GROUP", "scan")


def connect() -> redis.Redis:
    # REDIS_ADDR is "host:port" (no URL scheme). rsplit splits on the LAST colon.
    addr = os.environ.get("REDIS_ADDR", "scan-queue-redis:6379")
    host, port = addr.rsplit(":", 1)
    return redis.Redis(host=host, port=int(port), decode_responses=True)


def ensure_group(r: redis.Redis, stream: str = WORK, group: str = GROUP) -> None:
    try:
        r.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def enqueue(r: redis.Redis, stream: str, refs: list[str]) -> None:
    for ref in refs:
        r.xadd(stream, {"ref": ref})
        if "@" in ref:
            r.sadd(PLACED, ref.split("@", 1)[1])  # placed-set for the coverage convergence check


def reserve(r, consumer, stream=WORK, group=GROUP, block_ms=5000):
    """XREADGROUP one new entry. Returns (msg_id, ref) or None if the stream is empty."""
    resp = r.xreadgroup(group, consumer, {stream: ">"}, count=1, block=block_ms)
    if not resp:
        return None
    _stream, entries = resp[0]
    if not entries:
        return None
    msg_id, fields = entries[0]
    return msg_id, fields["ref"]


def _trim_minid(r, stream=WORK, group=GROUP):
    """Reclaim fully-processed entries WITHOUT evicting an un-acked OR un-read entry.
    XTRIM MINID X keeps id >= X. Floor = the oldest entry still needed (un-acked or un-read)."""
    pend = r.xpending(stream, group)
    if pend["pending"]:
        # oldest still-pending (delivered, un-acked) entry and everything after it survive
        r.xtrim(stream, minid=pend["min"], approximate=False)
        return
    groups = {g["name"]: g for g in r.xinfo_groups(stream)}
    last_delivered = groups[group]["last-delivered-id"]
    if last_delivered == "0-0":
        return
    # Requires Redis >= 6.2 (XAUTOCLAIM, XTRIM MINID) + XINFO last-generated-id;
    # the pipeline runs redis:7.
    last_generated = r.xinfo_stream(stream)["last-generated-id"]
    if last_delivered == last_generated:
        # nothing un-read: every entry is read+acked -> reclaim all of them
        ts, _seq = last_delivered.split("-")
        r.xtrim(stream, minid=f"{int(ts) + 1}-0", approximate=False)
    else:
        # un-read entries exist (their id > last_delivered) -> keep them; trim only the
        # fully-acked prefix below last_delivered. The acked last_delivered entry lingers
        # one cycle (harmless; reclaimed once a later entry is acked).
        r.xtrim(stream, minid=last_delivered, approximate=False)


def ack(r, msg_id, digest, attested_at, stream=WORK, group=GROUP, confirmed=CONFIRMED):
    """Success path. INVARIANT order: ZADD confirmed (durable) -> XACK -> trim."""
    r.zadd(confirmed, {digest: attested_at})
    r.xack(stream, group, msg_id)
    _trim_minid(r, stream, group)


def dead_letter(r, msg_id, ref, reason, stream=WORK, group=GROUP, dead=DEAD):
    """INVARIANT: XADD to dead (durable) BEFORE XACK on work. A crash between them
    re-delivers and re-dead-letters (a dedupable duplicate) — never a loss.
    NOTE: this function does NOT trim the work stream (the reaper trims after its loop).
    A standalone caller (e.g. a worker dead-lettering a classify_failure "permanent" verdict)
    must call _trim_minid itself, or processed entries on the work stream will not be reclaimed."""
    payload = {"ref": ref, **{k: str(v) for k, v in reason.items()}}
    r.xadd(dead, payload)
    r.xack(stream, group, msg_id)


def reaper(r, consumer, min_idle_ms, max_deliveries, reason=None, stream=WORK, group=GROUP):
    """Claim entries idle > min_idle_ms (a dead worker, OR a slow-alive scan past the
    window — the claim is purely idle-based). Past max_deliveries, route to the dead
    stream. Trim after."""
    cursor = "0-0"
    claimed: list[str] = []
    while True:
        cursor, msgs, _deleted = r.xautoclaim(
            stream, group, consumer, min_idle_ms, start_id=cursor, count=50
        )
        for msg_id, fields in msgs:
            claimed.append(msg_id)
            rng = r.xpending_range(stream, group, min=msg_id, max=msg_id, count=1)
            delivered = rng[0]["times_delivered"] if rng else 1
            if should_dead_letter(delivered, max_deliveries):
                dead_letter(
                    r,
                    msg_id,
                    fields.get("ref", ""),
                    reason or {"error": "max retries"},
                    stream,
                    group,
                )
        if cursor == "0-0":
            break
    _trim_minid(r, stream, group)
    return claimed


def coverage_check(r, placed, max_age_s, now, confirmed=CONFIRMED):
    """Fresh coverage gap = placed - {digests confirmed within max_age}. Cheap: one
    ZRANGEBYSCORE + a set-diff (the pure function). No DT query, no registry walk."""
    fresh = set(r.zrangebyscore(confirmed, now - max_age_s, now))
    return coverage_gap(set(placed), fresh)


def ref_matches(ref, selector):
    """Match a dead-entry ref against an operator selector. Accepts the full digest
    (`sha256:hex`) OR the bare hex (what an operator naturally copies from `scan-dlq list`).
    `--all` matches everything; an empty selector matches nothing (never a silent match-all)."""
    if selector == "--all":
        return True
    if not selector or "@" not in ref:
        return False
    digest = ref.split("@", 1)[1]  # "sha256:hex"
    return digest == selector or digest.split(":")[-1] == selector.split(":")[-1]


def dlq_list(r, dead=DEAD):
    return [{"id": mid, **fields} for mid, fields in r.xrange(dead)]


def dlq_replay(r, selector, dead=DEAD, work=WORK):
    """Re-enqueue every dead entry matching the selector (full digest, bare hex, or
    `--all`); remove it from the dead stream. Returns the count moved."""
    moved = 0
    for mid, fields in r.xrange(dead):
        if ref_matches(fields.get("ref", ""), selector):
            r.xadd(work, {"ref": fields["ref"]})
            r.xdel(dead, mid)
            moved += 1
    return moved


def dlq_drop(r, selector, dead=DEAD):
    """Permanently drop every dead entry matching the selector (full digest or bare hex).
    Returns the count dropped."""
    dropped = 0
    for mid, fields in r.xrange(dead):
        if ref_matches(fields.get("ref", ""), selector):
            r.xdel(dead, mid)
            dropped += 1
    return dropped
