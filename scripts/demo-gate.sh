#!/usr/bin/env bash
# demo-gate.sh — Act 2: the front door blocks a vulnerable image at intake.
# Uses XZ (liblzma is distro-tracked, so the scanner flags it cleanly).
#
# houba attach INGESTS a SARIF (--report); it does NOT run a scanner.
# grype runs first to produce the SARIF, then houba attach writes the
# scan referrer to the registry BEFORE computing the exit code:
#   exit 1 → gated      (the win — attach saw findings above threshold)
#   exit 2 → AdapterError (registry WRITE failed; check write creds)
#   exit 0 → gate silent (stale DB or SARIF kind trap; assert exit==1)
#
# Inputs (environment):
#   REG        demo registry host, e.g. localhost:5000 (required)
#   REF        full image reference       (default: $REG/upstream/debian-xz:5.6.1)
#   THRESHOLD  --fail-on severity level   (default: high)
#   HOUBA_REGISTRIES  registry roster JSON (required for registry auth)
#
# Usage:
#   REG=localhost:5000 HOUBA_REGISTRIES='{"demo":{"host":"localhost:5000","tls_verify":false}}' \
#     scripts/demo-gate.sh
set -uo pipefail

REG="${REG:?set REG to the demo registry host, e.g. localhost:5000}"
: "${HOUBA_REGISTRIES:?set HOUBA_REGISTRIES (the registry roster JSON)}"
REF="${REF:-${REG}/upstream/debian-xz:5.6.1}"   # seeded by make seed-incident
THRESHOLD="${THRESHOLD:-high}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

# Configure regctl auth from HOUBA_REGISTRIES — mirrors scan-attach.sh's approach
# so that houba attach can write the scan referrer to the demo registry.
read -r HOST TLS USER_NAME PASSWORD < <(
  python3 - <<'PY'
import json, os, sys
roster = json.loads(os.environ["HOUBA_REGISTRIES"])
# Use the registry that hosts REF (first entry when there is only one).
name = next(iter(roster)) if len(roster) == 1 else ""
if not name:
    # More than one registry: pick the one whose host matches REG.
    reg_host = os.environ.get("REG", "")
    name = next((k for k, v in roster.items() if v.get("host") == reg_host), "")
if not name:
    sys.exit("Cannot determine registry from HOUBA_REGISTRIES (set REG to match a host in the roster, or configure a single registry).")
r = roster[name]
print(r["host"], str(r.get("tls_verify", True)).lower(), r.get("username", "-"), r.get("password", "-"))
PY
)
if [ "${TLS}" = "false" ]; then regctl registry set "${HOST}" --tls disabled; fi
if [ "${USER_NAME}" != "-" ] && [ "${PASSWORD}" != "-" ]; then
  printf '%s' "${PASSWORD}" | regctl registry login "${HOST}" -u "${USER_NAME}" --pass-stdin
fi

echo "== Act 2: the front door blocks a vulnerable image at intake =="
echo "   image     : ${REF}"
echo "   threshold : ${THRESHOLD}"
echo ""

echo "» running grype …"
grype "${REF}" -o sarif > "$WORK/scan.sarif" 2>/dev/null
if [ ! -s "$WORK/scan.sarif" ]; then
  echo "FAIL — grype produced no SARIF (image not found, grype error, or empty scan). Check grype and the image ref." >&2
  exit 3
fi
echo "» SARIF written — attaching and gating …"

houba attach "${REF}" --report "$WORK/scan.sarif" --fail-on "${THRESHOLD}"; rc=$?
case "$rc" in
  1) echo "GATED ✓ — attach --fail-on ${THRESHOLD} exited 1: the front door said no.";;
  2) echo "FAIL — exit 2 (AdapterError): registry WRITE failed. attach writes a referrer before gating; check write creds."; exit 2;;
  0) echo "FAIL — exit 0: gate did not fire (stale grype DB, or a SARIF kind result). Pin the DB; assert exit==1."; exit 1;;
  *) echo "FAIL — unexpected exit $rc"; exit "$rc";;
esac
