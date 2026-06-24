#!/usr/bin/env python3
"""Beat 4 assertion: DependencyTrack reports zero affected projects for a CVE.

stdlib only (the houba image has no curl/jq). Exit codes are distinct so a green
beat-4 can't be faked by a misconfiguration:
  0 = checked, clear (0 affected projects)
  1 = checked, still affected (>0 projects)  -> beat 4 not yet green
  2 = could NOT check (missing env, auth/HTTP/network error) -> inconclusive, not a verdict
"""
import json
import os
import sys
import urllib.error
import urllib.request

CANT_CHECK = 2


def main() -> int:
    cve = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"
    try:
        base = os.environ["DT_BASE_URL"].rstrip("/")      # e.g. http://dependency-track-apiserver:8080
        key = os.environ["DT_API_KEY"]
    except KeyError as e:
        print(f"cannot check: set DT_BASE_URL and DT_API_KEY ({e} unset)", file=sys.stderr)
        return CANT_CHECK
    # URL/scheme come from the trusted in-cluster DT_BASE_URL; S310 (arbitrary-scheme) is moot.
    req = urllib.request.Request(  # noqa: S310
        f"{base}/api/v1/vulnerability/source/NVD/vuln/{cve}/projects",
        headers={"X-Api-Key": key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            affected = json.load(resp)
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        # HTTPError (401 bad key, 5xx) / URLError (DNS, refused) / bad body — inconclusive,
        # NOT "clear". (404 would mean the CVE isn't in DT yet — also inconclusive here.)
        print(f"cannot check {cve} against DT: {e}", file=sys.stderr)
        return CANT_CHECK
    n = len(affected) if isinstance(affected, list) else 0
    print(f"DT: {n} project(s) still affected by {cve}")
    return 0 if n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
