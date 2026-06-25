#!/usr/bin/env bash
# scan-one.sh fetch|attach — operate on the single reserved digest in /shared/digest.
# Distilled from scan-attach.sh: no repo walk, one ref. SBOM->DT is Loop B (publish-sbom).
set -euo pipefail
: "${HOUBA_REGISTRIES:?set HOUBA_REGISTRIES}"
MODE="${1:?usage: scan-one.sh fetch|attach}"
REF="$(cat /shared/digest)"          # host/repo@sha256:...
CDX_TYPE="application/vnd.cyclonedx+json"
SPDX_TYPE="application/spdx+json"
HOST="${REF%%/*}"

# TLS/auth for this host from the roster (same resolution the demo scripts use).
read -r TLS USER_NAME PASSWORD < <(
  HOST="$HOST" python3 - <<'PY'
import json, os
roster = json.loads(os.environ["HOUBA_REGISTRIES"])
r = next(v for v in roster.values() if v["host"] == os.environ["HOST"])
print(str(r.get("tls_verify", True)).lower(), r.get("username", "-"), r.get("password", "-"))
PY
)
[ "$TLS" = false ] && regctl registry set "$HOST" --tls disabled || true
if [ "$USER_NAME" != "-" ] && [ "$PASSWORD" != "-" ]; then
  printf '%s' "$PASSWORD" | regctl registry login "$HOST" -u "$USER_NAME" --pass-stdin
fi

case "$MODE" in
  fetch)
    regctl artifact get --subject "$REF" --filter-artifact-type "$CDX_TYPE" > /shared/sbom.json 2>/dev/null \
      || regctl artifact get --subject "$REF" --filter-artifact-type "$SPDX_TYPE" > /shared/sbom.json
    [ -s /shared/sbom.json ] || { echo "no SBOM referrer for $REF" >&2; exit 1; }
    ;;
  attach)
    # Loop A = scan + attach ONLY. The SBOM -> Dependency-Track push is Loop B
    # (the existing publish-sbom Job), independent of the scan (the SBOM is made at
    # placement, not by the scan). Keeping them separate matches the spec and avoids
    # coupling a scan worker to DT's availability.
    houba attach "$REF" --report /shared/scan.sarif
    python3 /scripts/scan-queue-ack.py ok
    ;;
  *) echo "unknown mode $MODE" >&2; exit 2;;
esac
