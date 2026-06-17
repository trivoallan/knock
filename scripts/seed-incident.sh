#!/usr/bin/env bash
# seed-incident.sh — build the deliberately-vulnerable xz fixture IN-CLUSTER (via buildkitd) and
# push it to the demo registry, twice:
#   - upstream/debian-xz:5.6.1  — the pretend-upstream houba rebuilds (front door → SBOM + stamp)
#   - bypassed/debian-xz:5.6.1  — the SAME bits pushed directly, never through houba (blind spot)
#
# In-cluster because Docker Desktop's daemon (a Linux VM) can't reach a host `kubectl port-forward`;
# buildkitd → Zot is on the cluster network. The fixture is built WITHOUT an SBOM on purpose —
# houba's rebuild is what generates the package SBOM the demo flags.
set -euo pipefail

: "${HOUBA_REGISTRIES:?set HOUBA_REGISTRIES (the registry roster JSON)}"
: "${BUILDKIT_HOST:?set BUILDKIT_HOST (the buildkitd gRPC endpoint)}"

# Resolve the demo registry host + TLS from the roster (sole entry).
read -r HOST TLS < <(
  python3 - <<'PY'
import json, os
roster = json.loads(os.environ["HOUBA_REGISTRIES"])
r = roster[next(iter(roster))]
print(r["host"], str(r.get("tls_verify", True)).lower())
PY
)

INSECURE=""
if [ "${TLS}" = "false" ]; then
  regctl registry set "${HOST}" --tls disabled
  INSECURE=",registry.insecure=true"
fi

echo "» building the xz fixture via buildkitd → ${HOST}/upstream/debian-xz:5.6.1" >&2
# oci-mediatypes=true: this Zot accepts only OCI manifests (415 on Docker schema2). buildkit
# defaults to Docker schema2 when no attestation is attached, so force OCI explicitly.
buildctl build \
  --frontend=dockerfile.v0 \
  --local=context=/ctx \
  --local=dockerfile=/ctx \
  --opt=filename=debian-xz.Dockerfile \
  "--output=type=image,name=${HOST}/upstream/debian-xz:5.6.1,push=true,oci-mediatypes=true${INSECURE}"

echo "» copying the same bits directly to ${HOST}/bypassed/debian-xz:5.6.1 (never through houba)" >&2
regctl image copy "${HOST}/upstream/debian-xz:5.6.1" "${HOST}/bypassed/debian-xz:5.6.1"

echo "» seeded upstream/debian-xz:5.6.1 (houba will rebuild it) + bypassed/debian-xz:5.6.1" >&2
