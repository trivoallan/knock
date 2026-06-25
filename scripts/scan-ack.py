import sys

from scripts import scan_streams

msg_id = open("/shared/msgid").read().strip()
ref = open("/shared/digest").read().strip()
digest = ref.split("@", 1)[1]
attested_at = int(open("/shared/attested_at").read().strip())
scan_streams.ack(scan_streams.connect(), msg_id, digest=digest, attested_at=attested_at)
print(f"ack {ref}", file=sys.stderr)
