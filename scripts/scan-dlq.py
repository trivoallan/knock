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
    found = False
    for e in scan_streams.dlq_list(r):
        if scan_streams.ref_matches(e.get("ref", ""), arg):
            found = True
            for k, v in e.items():
                if k != "suggested_action":
                    print(f"{k}: {v}")
            print(f"suggested_action: {e.get('suggested_action', '(none recorded)')}")
    if not found:
        print(f"no dead entry matched {arg!r}", file=sys.stderr)
elif cmd == "replay":
    n = scan_streams.dlq_replay(r, arg)
    print(f"replayed {n} entr(y/ies) to work")
    if n == 0:
        print(f"warning: no dead entry matched {arg!r}", file=sys.stderr)
elif cmd == "drop":
    n = scan_streams.dlq_drop(r, arg)
    print(f"dropped {n} entr(y/ies)")
    if n == 0:
        print(f"warning: no dead entry matched {arg!r}", file=sys.stderr)
else:
    print(
        "usage: scan-dlq.py list | show <digest> | replay <digest|--all> | drop <digest>",
        file=sys.stderr,
    )
    raise SystemExit(2)
