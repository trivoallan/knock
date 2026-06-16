#!/usr/bin/env bash
# publish-sbom.sh — push each rebuilt image's SBOM into Dependency-Track.
#
# For every tag of every BLAST_REPOS repo: pull the SPDX SBOM that buildkit attached at build
# (an in-toto attestation manifest in the image index), unwrap the SPDX predicate, convert it
# to CycloneDX with `syft convert`, and upload it to DT. Copy-only images carry no SBOM and are
# skipped + logged (the same "coverage gap" semantics as blast-radius.sh).
#
# Generic glue: regctl + syft + python3, no houba coupling. DT is the worked-example consumer.
#
# Inputs (environment):
#   HOUBA_REGISTRIES  JSON roster (same secret houba uses)
#   BLAST_REGISTRY    roster entry to scan (default: the sole entry)
#   BLAST_REPOS       space/comma-separated repos to walk
#   DT_URL            Dependency-Track apiserver base URL (default in-cluster service)
#   DT_API_KEY        key with BOM_UPLOAD + PROJECT_CREATION (from the dt-api-key Secret)
set -euo pipefail

: "${HOUBA_REGISTRIES:?set HOUBA_REGISTRIES (the registry roster JSON)}"
: "${BLAST_REPOS:?set BLAST_REPOS (space/comma-separated repositories)}"
export DT_URL="${DT_URL:-http://dependency-track-apiserver:8080}"
if [ -z "${DT_API_KEY:-}" ]; then
  echo "» DT_API_KEY unset (DT not bootstrapped yet) — nothing to publish" >&2
  exit 0   # tolerate early/Argo apply before the bootstrap Job has run
fi

# Resolve host + TLS + creds for the chosen registry from the roster.
read -r HOST TLS USER_NAME PASSWORD < <(
  BLAST_REGISTRY="${BLAST_REGISTRY:-}" python3 - <<'PY'
import json, os, sys
roster = json.loads(os.environ["HOUBA_REGISTRIES"])
name = os.environ.get("BLAST_REGISTRY") or (next(iter(roster)) if len(roster) == 1 else "")
if not name:
    sys.exit(f"BLAST_REGISTRY must be one of {sorted(roster)} (more than one configured)")
r = roster[name]
print(r["host"], str(r.get("tls_verify", True)).lower(), r.get("username", "-"), r.get("password", "-"))
PY
)

echo "» scanning registry '${BLAST_REGISTRY:-<sole>}' at ${HOST} (tls_verify=${TLS})" >&2

# Configure regctl for this host (TLS + optional auth).
if [ "${TLS}" = "false" ]; then
  regctl registry set "${HOST}" --tls disabled
fi
if [ "${USER_NAME}" != "-" ] && [ "${PASSWORD}" != "-" ]; then
  printf '%s' "${PASSWORD}" | regctl registry login "${HOST}" -u "${USER_NAME}" --pass-stdin
fi

REPOS=${BLAST_REPOS//,/ }
WORK=$(mktemp -d); trap 'rm -rf "${WORK}"' EXIT

for repo in ${REPOS}; do
  ref_base="${HOST}/${repo}"
  for tag in $(regctl tag ls "${ref_base}" 2>/dev/null); do
    ref="${ref_base}:${tag}"
    spdx="${WORK}/sbom.spdx.json"

    # Extract the SPDX predicate from buildkit's attestation manifest (if any).
    if ! regctl manifest get "${ref}" --format '{{json .}}' 2>/dev/null \
         | DT_REF="${ref}" python3 /scripts/extract_sbom.py "${spdx}"; then
      echo "» ${repo}:${tag} — no SBOM attestation (copy-only?) — skipped" >&2
      continue
    fi

    # SPDX → CycloneDX, then upload (PUT /api/v1/bom takes base64 CycloneDX JSON; autoCreate).
    cdx="${WORK}/sbom.cdx.json"
    syft convert "${spdx}" -o "cyclonedx-json=${cdx}"
    B64=$(base64 -w0 < "${cdx}" 2>/dev/null || base64 < "${cdx}" | tr -d '\n')
    DT_API_KEY="${DT_API_KEY}" python3 - "$tag" "$repo" "$B64" <<'PY'
import json, os, sys, urllib.request
tag, repo, b64 = sys.argv[1], sys.argv[2], sys.argv[3]
body = json.dumps({"projectName": repo, "projectVersion": tag, "autoCreate": True, "bom": b64}).encode()
req = urllib.request.Request(os.environ["DT_URL"] + "/api/v1/bom", data=body, method="PUT")
req.add_header("Content-Type", "application/json")
req.add_header("X-Api-Key", os.environ["DT_API_KEY"])
urllib.request.urlopen(req, timeout=30)  # noqa: S310
print(f"» published {repo}:{tag} to Dependency-Track", flush=True)
PY
  done
done
