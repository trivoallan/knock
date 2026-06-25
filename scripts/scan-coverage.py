import json
import os
import sys
import time

from scripts import scan_streams
from scripts.scan_queue import enqueue_refs, gap_by_owner

report = json.load(sys.stdin)
placed = {ref.split("@", 1)[1] for ref in enqueue_refs(report)}
owners: dict[str, str] = {}  # digest -> owner; populated from report stamps when available
max_age = int(os.environ.get("SCAN_MAX_AGE_S", "604800"))  # 7d
gap = scan_streams.coverage_check(scan_streams.connect(), placed, max_age, int(time.time()))
print(json.dumps({"coverage_gap": len(gap), "by_owner": gap_by_owner(gap, owners), "digests": gap}))
