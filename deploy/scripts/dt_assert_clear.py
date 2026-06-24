#!/usr/bin/env python3
"""Beat 4 assertion: no Dependency-Track project carries a given (vulnerable) component.

This is the package-level blast-radius query that is houba's whole thesis — and it needs ONLY
the SBOM data houba already published to DT, no vulnerability mirror. (A CVE-based check would
depend on DT having mirrored that CVE; the one-command demo populates no vuln source, and the
log4shell CVE lives only in the heavy NVD/GitHub feeds — not the light OSV-Debian one — so we
assert on the component's presence instead.)

stdlib only (the houba image has no curl/jq). Exit codes are distinct so a green beat-4 can't
be faked by a misconfiguration:
  0 = checked, clear (no project carries the component)
  1 = checked, still present (>=1 project carries it)  -> blast radius not cleared
  2 = could NOT check (missing env, auth/HTTP/network error) -> inconclusive, not a verdict
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CANT_CHECK = 2


def main() -> int:
    component = sys.argv[1] if len(sys.argv) > 1 else "log4j-core"
    try:
        base = os.environ["DT_BASE_URL"].rstrip("/")  # e.g. http://dependency-track-apiserver:8080
        key = os.environ["DT_API_KEY"]
    except KeyError as e:
        print(f"cannot check: set DT_BASE_URL and DT_API_KEY ({e} unset)", file=sys.stderr)
        return CANT_CHECK
    # Portfolio-wide component search by name; X-Total-Count carries the match count.
    # URL/scheme come from the trusted in-cluster DT_BASE_URL; S310 (arbitrary-scheme) is moot.
    req = urllib.request.Request(  # noqa: S310
        f"{base}/api/v1/component/identity?name={urllib.parse.quote(component)}",
        headers={"X-Api-Key": key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            total = resp.headers.get("X-Total-Count")
            matches = json.load(resp)
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        # HTTPError (401 bad key, 5xx) / URLError (DNS, refused) / bad body — inconclusive,
        # NOT "clear".
        print(f"cannot check {component!r} against DT: {e}", file=sys.stderr)
        return CANT_CHECK
    n = int(total) if total is not None else (len(matches) if isinstance(matches, list) else 0)
    print(f"DT: {n} component(s) named {component!r} across the portfolio")
    return 0 if n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
