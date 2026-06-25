#!/usr/bin/env bash
# scan-one.sh fetch|attach-publish — operate on the single reserved digest in /shared/digest.
# Distilled from scan-attach.sh + publish-sbom.sh: no repo walk, one ref.
set -euo pipefail
: "${HOUBA_REGISTRIES:?set HOUBA_REGISTRIES}"
MODE="${1:?usage: scan-one.sh fetch|attach-publish}"
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
  attach-publish)
    houba attach "$REF" --report /shared/scan.sarif
    if [ -n "${DT_API_KEY:-}" ]; then
      repo="${REF#*/}"; repo="${repo%@*}"
      DT_URL="${DT_URL:?}" DT_API_KEY="$DT_API_KEY" CDX=/shared/sbom.json REPO="$repo" python3 - <<'PY'
import base64, json, os, urllib.request
b64 = base64.b64encode(open(os.environ["CDX"], "rb").read()).decode()
body = json.dumps({"projectName": os.environ["REPO"], "projectVersion": "scanned",
                   "autoCreate": True, "bom": b64}).encode()
req = urllib.request.Request(os.environ["DT_URL"] + "/api/v1/bom", data=body, method="PUT")
req.add_header("Content-Type", "application/json"); req.add_header("X-Api-Key", os.environ["DT_API_KEY"])
urllib.request.urlopen(req, timeout=60)  # noqa: S310
print(f"published {os.environ['REPO']} to DT", flush=True)
PY
    fi
    python3 /scripts/scan-queue-ack.py ok
    ;;
  *) echo "unknown mode $MODE" >&2; exit 2;;
esac
