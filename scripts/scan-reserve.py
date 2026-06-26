import os

from scripts import scan_streams

r = scan_streams.connect()
scan_streams.ensure_group(r)
resv = scan_streams.reserve(r, os.environ.get("HOSTNAME", "worker"))
if resv is None:
    print("queue empty", file=__import__("sys").stderr)
    raise SystemExit(75)  # EX_TEMPFAIL
msg_id, ref = resv
with open("/shared/msgid", "w") as f:
    f.write(msg_id)
with open("/shared/digest", "w") as f:
    f.write(ref)
print(ref)
