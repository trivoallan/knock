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

# ---------------------------------------------------------------------------
# Mongo corpus (brownfield Act 1)
# ---------------------------------------------------------------------------
# Copy two mongobleed-affected tags from Docker Hub into the demo Zot so that:
#   upstream/mongo:8.0.15 + :8.0.16         — houba reconcile will copy these
#                                              through the front door (stamp + SBOM)
#   team-data-platform/mongo:8.0.15 + :8.0.16 — raw copy, never through houba (the
#                                              "before" world; the owner is only
#                                              *guessable* from the first path
#                                              segment "team-data-platform")
#   team-data-platform/mongo:8.0            — re-pointed alias: first → 8.0.15,
#                                              then → 8.0.16 — so a tag-only query
#                                              is ambiguous in the "before" world
#
# The path segment "team-data-platform" deliberately echoes (imperfectly) the
# declared owner "group:default/data-platform": the before-world query guesses
# the team from the repo path, while the after-world reads the authoritative
# io.houba.owners label off the houba'd copy.
#
# Note: houba's policy (docs/examples/brownfield/mongo.yml) sources directly
# from docker.io/library/mongo, NOT from upstream/mongo in the Zot.  The
# upstream/ copies below exist purely to have a local stand-in in air-gapped
# demo environments; remove them if the cluster has Docker Hub access.
# ---------------------------------------------------------------------------

# Idempotent: skip the Hub pull when the tag is already present (re-runs are
# fast and don't trip Docker Hub rate limits at demo time).
for TAG in 8.0.15 8.0.16; do
  for DEST in upstream/mongo team-data-platform/mongo; do
    if ! regctl manifest head "${HOST}/${DEST}:${TAG}" >/dev/null 2>&1; then
      echo "» copying docker.io/library/mongo:${TAG} → ${HOST}/${DEST}:${TAG}" >&2
      regctl image copy "docker.io/library/mongo:${TAG}" "${HOST}/${DEST}:${TAG}"
    else
      echo "» ${HOST}/${DEST}:${TAG} already present, skipping" >&2
    fi
  done
done

# Re-point the 8.0 alias: first pin it to 8.0.15, then advance to 8.0.16.
# This creates the ambiguity: a query on team-data-platform/mongo:8.0 today sees
# 8.0.16 but yesterday it saw 8.0.15 — the "before" world is tag-ambiguous.
echo "» pointing ${HOST}/team-data-platform/mongo:8.0 → 8.0.15 (first placement)" >&2
regctl image copy "${HOST}/team-data-platform/mongo:8.0.15" "${HOST}/team-data-platform/mongo:8.0"

echo "» re-pointing ${HOST}/team-data-platform/mongo:8.0 → 8.0.16 (tag now ambiguous)" >&2
regctl image copy "${HOST}/team-data-platform/mongo:8.0.16" "${HOST}/team-data-platform/mongo:8.0"

echo "» seeded upstream/mongo:8.0.15+8.0.16 + team-data-platform/mongo:8.0.15+8.0.16 (8.0 alias → 8.0.16)" >&2
