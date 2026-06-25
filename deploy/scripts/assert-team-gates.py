#!/usr/bin/env python3
"""Assert the two-team contrast: platform-prod promoted, data-prod held.

Reads kargo Stage status via kubectl (no kargo CLI dependency). A Stage that settled Freight in
prod has a non-empty status.freightHistory; a held Stage has none (its verification failed).
Exit 0 if the contrast holds (platform settled, data not), 1 otherwise.
"""

import json
import subprocess
import sys


def stage_settled(name: str) -> bool:
    out = subprocess.run(  # noqa: S603
        ["kubectl", "-n", "houba", "get", "stage", name, "-o", "json"],  # noqa: S607
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        print(f"  (stage {name} not found yet: {out.stderr.strip()})")
        return False
    status = json.loads(out.stdout).get("status", {})
    return len(status.get("freightHistory") or []) > 0


def main() -> int:
    platform = stage_settled("platform-prod")
    data = stage_settled("data-prod")
    print(f"platform-prod settled (promoted): {platform}")
    print(f"data-prod settled (promoted):     {data}")
    if platform and not data:
        print("\n✓ Contrast holds: team-platform PROMOTED, team-data HELD by its gate.")
        return 0
    print(
        "\n✗ Contrast not yet observed. OSV/scan + kargo verification are async — re-run after a "
        "minute, or inspect: kubectl -n houba get stages,analysisruns."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
