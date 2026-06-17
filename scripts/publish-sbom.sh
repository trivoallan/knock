#!/usr/bin/env bash
# publish-sbom.sh — push each image's CycloneDX SBOM into Dependency-Track.
#
# houba attaches a package-level SBOM as an OCI referrer on every placed image — copy AND
# rebuild — one referrer per HOUBA_SBOM_FORMATS entry (artifactType == the SBOM media type).
# With cyclonedx-json enabled, we fetch the CycloneDX referrer for each tag and upload it to DT.
# No conversion, no glue image: just regctl + python3 (both in the houba runtime image).
# Images with no CycloneDX referrer (e.g. the bypass image, never through houba) are skipped +
# logged — the same "coverage gap" semantics as blast-radius.sh.
#
# Inputs (environment):
#   HOUBA_REGISTRIES  JSON roster (same secret houba uses)
#   BLAST_REGISTRY    roster entry to scan (default: the sole entry)
#   BLAST_REPOS       space/comma-separated repos to walk
#   DT_URL            Dependency-Track apiserver base URL (default in-cluster service)
#   DT_API_KEY        key with BOM_UPLOAD + PROJECT_CREATION_UPLOAD (from the dt-api-key Secret)
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
CDX_TYPE="application/vnd.cyclonedx+json"

for repo in ${REPOS}; do
  ref_base="${HOST}/${repo}"
  for tag in $(regctl tag ls "${ref_base}" 2>/dev/null); do
    ref="${ref_base}:${tag}"
    cdx="${WORK}/sbom.cdx.json"

    # Fetch the CycloneDX SBOM referrer houba attached to this image (if any).
    if ! regctl artifact get --subject "${ref}" --filter-artifact-type "${CDX_TYPE}" \
         > "${cdx}" 2>/dev/null || ! [ -s "${cdx}" ]; then
      echo "» ${repo}:${tag} — no CycloneDX SBOM referrer (never through houba?) — skipped" >&2
      continue
    fi

    # Upload to DT (PUT /api/v1/bom takes base64 CycloneDX JSON; autoCreate the project).
    # python reads + base64-encodes the file itself — a large SBOM as an argv blows ARG_MAX.
    DT_API_KEY="${DT_API_KEY}" CDX="${cdx}" python3 - "$tag" "$repo" <<'PY'
import base64, json, os, sys, urllib.request
tag, repo = sys.argv[1], sys.argv[2]
b64 = base64.b64encode(open(os.environ["CDX"], "rb").read()).decode()
body = json.dumps({"projectName": repo, "projectVersion": tag, "autoCreate": True, "bom": b64}).encode()
req = urllib.request.Request(os.environ["DT_URL"] + "/api/v1/bom", data=body, method="PUT")
req.add_header("Content-Type", "application/json")
req.add_header("X-Api-Key", os.environ["DT_API_KEY"])
urllib.request.urlopen(req, timeout=60)  # noqa: S310
print(f"» published {repo}:{tag} to Dependency-Track", flush=True)
PY
  done
done
