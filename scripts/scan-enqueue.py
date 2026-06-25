import json
import sys

from scripts import scan_streams
from scripts.scan_queue import enqueue_refs

r = scan_streams.connect()
scan_streams.ensure_group(r)
refs = enqueue_refs(json.load(sys.stdin))
scan_streams.enqueue(r, scan_streams.WORK, refs)
print(f"enqueued {len(refs)} ref(s)", file=sys.stderr)
