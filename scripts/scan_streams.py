"""Thin redis-py I/O for the scan pipeline. The DECISIONS live in scan_queue.py
(pure, unit-tested); this module is the broker boundary.

INVARIANT: XACK is always the last op — every durable side-effect completes first."""

from __future__ import annotations

import os

import redis

from scripts.scan_queue import coverage_gap, should_dead_letter

WORK = os.environ.get("REDIS_WORK_STREAM", "houba:scan:work")
DEAD = os.environ.get("REDIS_DEAD_STREAM", "houba:scan:dead")
CONFIRMED = os.environ.get("REDIS_CONFIRMED_ZSET", "houba:scan:confirmed")
GROUP = os.environ.get("REDIS_GROUP", "scan")


def connect() -> redis.Redis:
    addr = os.environ.get("REDIS_ADDR", "scan-queue-redis:6379")
    host, port = addr.split(":")
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
    """Reclaim stream memory WITHOUT evicting an un-acked entry: trim below the oldest
    still-pending id. NEVER MAXLEN (evicts un-acked under backlog), NEVER per-entry XDEL.

    MINID semantics: XTRIM MINID X keeps entries where id >= X. When there are no pending
    entries, all delivered entries are acked — trim at last-delivered+1ms to remove them all."""
    pend = r.xpending(stream, group)
    if pend["pending"]:
        r.xtrim(stream, minid=pend["min"], approximate=False)
    else:
        last = r.xinfo_groups(stream)[0]["last-delivered-id"]
        if last != "0-0":
            ts, seq = last.split("-")
            r.xtrim(stream, minid=f"{int(ts) + 1}-0", approximate=False)


def ack(r, msg_id, digest, attested_at, stream=WORK, group=GROUP, confirmed=CONFIRMED):
    """Success path. INVARIANT order: ZADD confirmed (durable) -> XACK -> trim."""
    r.zadd(confirmed, {digest: attested_at})
    r.xack(stream, group, msg_id)
    _trim_minid(r, stream, group)


def dead_letter(r, msg_id, ref, reason, stream=WORK, group=GROUP, dead=DEAD):
    """INVARIANT: XADD to dead (durable) BEFORE XACK on work. A crash between them
    re-delivers and re-dead-letters (a dedupable duplicate) — never a loss."""
    payload = {"ref": ref, **{k: str(v) for k, v in reason.items()}}
    r.xadd(dead, payload)
    r.xack(stream, group, msg_id)


def reaper(r, consumer, min_idle_ms, max_deliveries, reason=None,
           stream=WORK, group=GROUP):
    """Claim entries idle > min_idle_ms (a dead worker, OR a slow-alive scan past the
    window — the claim is purely idle-based). Past max_deliveries, route to the dead
    stream. Trim after."""
    cursor = "0-0"
    claimed: list[str] = []
    while True:
        cursor, msgs, _deleted = r.xautoclaim(stream, group, consumer, min_idle_ms,
                                               start_id=cursor, count=50)
        for msg_id, fields in msgs:
            claimed.append(msg_id)
            rng = r.xpending_range(stream, group, min=msg_id, max=msg_id, count=1)
            delivered = rng[0]["times_delivered"] if rng else 1
            if should_dead_letter(delivered, max_deliveries):
                dead_letter(r, msg_id, fields.get("ref", ""),
                            reason or {"error": "max retries"}, stream, group)
        if cursor == "0-0":
            break
    _trim_minid(r, stream, group)
    return claimed


def coverage_check(r, placed, max_age_s, now, confirmed=CONFIRMED):
    """Fresh coverage gap = placed - {digests confirmed within max_age}. Cheap: one
    ZRANGEBYSCORE + a set-diff (the pure function). No DT query, no registry walk."""
    fresh = set(r.zrangebyscore(confirmed, now - max_age_s, now))
    return coverage_gap(set(placed), fresh)
