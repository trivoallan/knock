#!/usr/bin/env python3
"""Drain `houba reconcile -o json` (stdin) and LPUSH each applied out_digest to Redis.

Reads the reconcile report tree (run -> policies -> targets -> variants -> operations),
collects every operation with applied=true and a non-null out_digest, and pushes
"<host>/<repo>@<out_digest>" refs onto REDIS_WORK_LIST. Registry host comes from the
single-entry roster (HOUBA_REGISTRIES) unless SCAN_REGISTRY names one.
"""
import json
import os
import socket
import sys


def _resp(*args: str) -> bytes:
    out = [f"*{len(args)}\r\n".encode()]
    for a in args:
        b = a.encode()
        out.append(f"${len(b)}\r\n".encode() + b + b"\r\n")
    return b"".join(out)


def _host() -> str:
    roster = json.loads(os.environ["HOUBA_REGISTRIES"])
    name = os.environ.get("SCAN_REGISTRY") or (next(iter(roster)) if len(roster) == 1 else "")
    if not name:
        sys.exit(f"SCAN_REGISTRY must be one of {sorted(roster)} (more than one configured)")
    return str(roster[name]["host"])


def _refs(report: dict, host: str) -> list[str]:
    """Placed digests = applied operations carrying an out_digest.

    Verified against report.py: the report tree is run -> policies[] -> targets[] ->
    variants[] -> operations[]; the destination repo is TargetReport.dest_repo (Operation
    has out_tag/out_digest but NO out_repo). Target-level operations are deletions/marks,
    which carry no out_digest, so only variant operations yield placed images.
    """
    refs: list[str] = []
    for policy in report.get("policies", []):
        for target in policy.get("targets", []):
            dest_repo = target["dest_repo"]
            for variant in target.get("variants", []):
                for op in variant.get("operations", []):
                    if op.get("applied") and op.get("out_digest"):
                        refs.append(f"{host}/{dest_repo}@{op['out_digest']}")
    return refs


def main() -> int:
    report = json.load(sys.stdin)
    host = _host()
    refs = _refs(report, host)
    if not refs:
        print("enqueue: no applied out_digests", file=sys.stderr)
        return 0
    addr = os.environ.get("REDIS_ADDR", "scan-queue-redis:6379")
    work = os.environ.get("REDIS_WORK_LIST", "houba:scan:work")
    h, p = addr.split(":")
    with socket.create_connection((h, int(p)), timeout=10) as s:
        for ref in refs:
            s.sendall(_resp("LPUSH", work, ref))
            if not s.recv(64).startswith(b":"):
                sys.exit(f"enqueue: LPUSH failed for {ref}")
    print(f"enqueue: pushed {len(refs)} digests to {work}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
