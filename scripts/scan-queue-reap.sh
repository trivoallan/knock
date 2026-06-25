#!/bin/sh
# scan-queue-reap.sh — two-snapshot stale-reaper for the reliable work queue.
#
# A ref still in `processing` across two consecutive reaper runs means its worker
# Job died between reserve (BRPOPLPUSH work->processing) and ack (LREM) — so requeue
# it to `work`. No per-item timestamps and no reserve/ack changes (hence no atomicity
# window): the reaper INTERVAL is the staleness threshold, so the CronJob schedule
# MUST exceed the max worker duration. Re-processing is idempotent (houba attach
# dedups, gc prunes), so a false reap of a genuinely-slow worker is harmless.
set -eu
R="redis-cli -h ${REDIS_HOST:-scan-queue-redis} -p ${REDIS_PORT:-6379}"
WORK="${REDIS_WORK_LIST:-houba:scan:work}"
PROC="${REDIS_PROCESSING_LIST:-houba:scan:processing}"
SEEN="${REDIS_REAPER_SET:-houba:scan:reaper:seen}"

seen="$($R SMEMBERS "$SEEN")"
reaped=0
# Refs never contain whitespace (host/repo@sha256:...), so word-splitting is safe.
for ref in $($R LRANGE "$PROC" 0 -1); do
  if printf '%s\n' "$seen" | grep -qxF "$ref"; then
    $R LREM "$PROC" 1 "$ref" >/dev/null
    $R LPUSH "$WORK" "$ref" >/dev/null
    reaped=$((reaped + 1))
    echo "reaped (requeued) $ref"
  fi
done

# Snapshot the CURRENT processing set for the next run (survivors only; reaped refs
# are already gone from the list).
$R DEL "$SEEN" >/dev/null
survivors="$($R LRANGE "$PROC" 0 -1)"
[ -z "$survivors" ] || printf '%s\n' $survivors | xargs $R SADD "$SEEN" >/dev/null
echo "reaper: requeued $reaped stale ref(s)"
