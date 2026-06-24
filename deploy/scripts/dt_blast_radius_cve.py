#!/usr/bin/env python3
"""Best-effort blast-radius probe: which Dependency-Track projects are flagged for a CVE.

The opt-in companion to dt_assert_clear.py (the deterministic, mirror-free Beat 4). This one
shows the CVE-to-image leg of the story — but it needs DT's vuln feed mirrored (`make dt-vulns`,
OSV Debian) and the projects re-analyzed, BOTH of which are asynchronous. So it polls for a
while and then reports whatever DT knows; it never fails the build (always exits 0). A CVE that
entered DT as an OSV alias is matched through each finding's vulnerability aliases, not a direct
CVE lookup.

stdlib only. Env: DT_BASE_URL, DT_API_KEY. Args: [CVE] [timeout_seconds].
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def _get(base: str, key: str, path: str) -> list:
    req = urllib.request.Request(  # noqa: S310 (trusted in-cluster DT_BASE_URL)
        base + path, headers={"X-Api-Key": key, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        body = r.read()
    return json.loads(body) if body.strip() else []


def _affected(base: str, key: str, cve: str) -> list[tuple]:
    hits = []
    for p in _get(base, key, "/api/v1/project?pageSize=500"):
        try:
            findings = _get(base, key, f"/api/v1/finding/project/{p['uuid']}")
        except (urllib.error.URLError, json.JSONDecodeError):
            continue
        for f in findings:
            v = f.get("vulnerability", {})
            ids = {v.get("vulnId")}
            for a in v.get("aliases", []) or []:
                ids.update(
                    s for s in (a.values() if isinstance(a, dict) else []) if isinstance(s, str)
                )
            if cve in ids:
                c = f.get("component", {})
                hits.append((p.get("name"), p.get("version"), c.get("name"), c.get("version")))
    return hits


def main() -> int:
    cve = sys.argv[1] if len(sys.argv) > 1 else "CVE-2024-3094"
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    try:
        base = os.environ["DT_BASE_URL"].rstrip("/")
        key = os.environ["DT_API_KEY"]
    except KeyError as e:
        print(f"cannot probe: set DT_BASE_URL and DT_API_KEY ({e} unset)", file=sys.stderr)
        return 0  # best-effort: never fail the build

    deadline = time.monotonic() + timeout
    while True:
        try:
            hits = _affected(base, key, cve)
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            hits = []
            print(f"  (DT not ready yet: {e})", file=sys.stderr)
        if hits:
            print(f"\nBlast radius for {cve} — {len(hits)} affected image(s):")
            for name, ver, comp, cver in sorted(set(hits)):
                print(f"  • {name}:{ver}  ←  {comp} {cver}")
            print(
                "\nThe bypassed image never went through houba, so it carries no SBOM and is "
                "invisible here — that is the coverage gap the front door closes."
            )
            return 0
        if time.monotonic() >= deadline:
            print(
                f"\ninconclusive: no project flagged for {cve} within {timeout}s. The OSV mirror "
                "and DT's re-analysis are asynchronous — give it longer, then inspect in "
                "`make dt-ui`. (best-effort probe, not a gate.)"
            )
            return 0
        time.sleep(15)


if __name__ == "__main__":
    sys.exit(main())
