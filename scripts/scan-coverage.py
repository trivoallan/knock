import json
import os
import time

from knock.domain.scan_queue import gap_by_owner
from scripts import scan_streams

r = scan_streams.connect()
placed = r.smembers(scan_streams.PLACED)
owners: dict[str, str] = {}  # digest -> owner; populated from stamps when available
max_age = int(os.environ.get("SCAN_MAX_AGE_S", "604800"))  # 7d
gap = scan_streams.coverage_check(r, placed, max_age, int(time.time()))
print(json.dumps({"coverage_gap": len(gap), "by_owner": gap_by_owner(gap, owners), "digests": gap}))
