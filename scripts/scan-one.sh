#!/usr/bin/env bash
# scan-one.sh fetch|attach — operate on the single reserved digest in /shared/digest.
# Distilled from scan-attach.sh: no repo walk, one ref. SBOM->DT is Loop B (publish-sbom).
set -euo pipefail
: "${KNOCK_REGISTRIES:?set KNOCK_REGISTRIES}"
MODE="${1:?usage: scan-one.sh fetch|attach}"
REF="$(cat /shared/digest)"          # host/repo@sha256:...
CDX_TYPE="application/vnd.cyclonedx+json"
SPDX_TYPE="application/spdx+json"
HOST="${REF%%/*}"

# TLS/auth for this host from the roster (same resolution the demo scripts use).
read -r TLS USER_NAME PASSWORD < <(
  HOST="$HOST" python3 - <<'PY'
import json, os
roster = json.loads(os.environ["KNOCK_REGISTRIES"])
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
    # Loop A = scan + attach ONLY (SBOM->DT is Loop B). After attach, record the signed
    # attested_at for the confirmed-set, then ack via Streams.
    knock attach "$REF" --report /shared/scan.sarif
    knock verify "$REF" --field attested_at > /shared/attested_at 2>/dev/null \
      || date +%s > /shared/attested_at   # fallback: now, if verify can't surface it
    python3 /scripts/scan-ack.py
    ;;
  *) echo "unknown mode $MODE" >&2; exit 2;;
esac
