import sys

from scripts import scan_streams

r = scan_streams.connect()
cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
arg = sys.argv[2] if len(sys.argv) > 2 else ""

if cmd == "list":
    for e in scan_streams.dlq_list(r):
        print(
            f"{e['id']}  {e.get('ref', '?')}  stage={e.get('stage', '?')}  "
            f"err={e.get('error', '?')[:60]}  deliveries={e.get('delivery_count', '?')}"
        )
elif cmd == "show":
    for e in scan_streams.dlq_list(r):
        if e.get("ref", "").endswith("@" + arg):
            for k, v in e.items():
                print(f"{k}: {v}")
            print(f"suggested_action: {e.get('suggested_action', '(none recorded)')}")
elif cmd == "replay":
    print(f"replayed {scan_streams.dlq_replay(r, arg)} entr(y/ies) to work")
elif cmd == "drop":
    print(f"dropped {scan_streams.dlq_drop(r, arg)} entr(y/ies)")
else:
    print(
        "usage: scan-dlq.py list | show <digest> | replay <digest|--all> | drop <digest>",
        file=sys.stderr,
    )
    raise SystemExit(2)
