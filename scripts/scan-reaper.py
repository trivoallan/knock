import os
import sys

from scripts import scan_streams

r = scan_streams.connect()
scan_streams.ensure_group(r)
claimed = scan_streams.reaper(
    r, "reaper",
    # 2x p99.9 scan; tune from metrics
    min_idle_ms=int(os.environ.get("REAP_MIN_IDLE_MS", "1800000")),
    max_deliveries=int(os.environ.get("MAX_DELIVERIES", "5")),
)
print(f"reaper reclaimed {len(claimed)}", file=sys.stderr)
