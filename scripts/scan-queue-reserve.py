#!/usr/bin/env python3
"""Reserve one digest: BRPOPLPUSH work -> processing, write it to /shared/digest."""

import os
import socket
import sys


def _resp(*args: str) -> bytes:
    out = [f"*{len(args)}\r\n".encode()]
    for a in args:
        b = a.encode()
        out.append(f"${len(b)}\r\n".encode() + b + b"\r\n")
    return b"".join(out)


def main() -> int:
    addr = os.environ.get("REDIS_ADDR", "scan-queue-redis:6379")
    work = os.environ.get("REDIS_WORK_LIST", "houba:scan:work")
    proc = os.environ.get("REDIS_PROCESSING_LIST", "houba:scan:processing")
    timeout = os.environ.get("RESERVE_TIMEOUT", "5")
    h, p = addr.split(":")
    with socket.create_connection((h, int(p)), timeout=int(timeout) + 5) as s:
        s.sendall(_resp("BRPOPLPUSH", work, proc, timeout))
        data = s.recv(4096)
    if data.startswith(b"$-1") or data.startswith(b"*-1"):
        print("reserve: queue empty", file=sys.stderr)
        return 75  # EX_TEMPFAIL — nothing to do
    # Bulk string: $<len>\r\n<payload>\r\n
    payload = data.split(b"\r\n", 1)[1].rstrip(b"\r\n").decode()
    with open("/shared/digest", "w") as f:
        f.write(payload)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
