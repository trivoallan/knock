#!/usr/bin/env python3
"""Ack a reserved digest. Usage: scan-queue-ack.py ok|fail."""

# A Job that crashes between reserve and ack leaves its ref in the 'processing'
# list; the scan-queue-reaper CronJob (scan-queue-reap.sh, two-snapshot) requeues it.
import os
import socket
import sys


def _resp(*args: str) -> bytes:
    out = [f"*{len(args)}\r\n".encode()]
    for a in args:
        b = a.encode()
        out.append(f"${len(b)}\r\n".encode() + b + b"\r\n")
    return b"".join(out)


def _cmd(s: socket.socket, *args: str) -> bytes:
    s.sendall(_resp(*args))
    return s.recv(4096)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
    ref = open("/shared/digest").read().strip()
    if not ref:
        return 0
    addr = os.environ.get("REDIS_ADDR", "scan-queue-redis:6379")
    work = os.environ.get("REDIS_WORK_LIST", "houba:scan:work")
    proc = os.environ.get("REDIS_PROCESSING_LIST", "houba:scan:processing")
    dead = os.environ.get("REDIS_DEAD_LIST", "houba:scan:dead")
    max_retries = int(os.environ.get("MAX_RETRIES", "3"))
    h, p = addr.split(":")
    with socket.create_connection((h, int(p)), timeout=10) as s:
        _cmd(s, "LREM", proc, "1", ref)  # always leave the processing list clean
        if mode == "fail":
            n = _cmd(s, "INCR", f"houba:scan:retries:{ref}")
            count = int(n[1:].split(b"\r\n", 1)[0])
            target = dead if count > max_retries else work
            _cmd(s, "LPUSH", target, ref)
            if target == dead:
                _cmd(s, "DEL", f"houba:scan:retries:{ref}")
            print(f"ack: {ref} -> {target} (attempt {count})", file=sys.stderr)
        else:
            _cmd(s, "DEL", f"houba:scan:retries:{ref}")
            print(f"ack: {ref} done", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
