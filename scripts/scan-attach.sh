#!/usr/bin/env bash
# scan-attach.sh — run an off-the-shelf analyzer (grype) on the SBOM houba already
# attached, and attach its SARIF as a signed referrer on the same digest.
#
# Two modes, because grype runs in a separate (credential-free) container between them:
#   fetch  — (init, houba image) pull each placed image's CycloneDX SBOM referrer to /shared
#   attach — (main, houba image) houba attach the SARIF grype wrote to /shared
# The grype step in between is an unmodified anchore/grype container: grype sbom:<file>.
#
# Inputs (environment): HOUBA_REGISTRIES, BLAST_REGISTRY (opt), BLAST_REPOS, SHARED (default /shared).
set -euo pipefail
: "${HOUBA_REGISTRIES:?set HOUBA_REGISTRIES (the registry roster JSON)}"
: "${BLAST_REPOS:?set BLAST_REPOS (space/comma-separated repositories)}"
MODE="${1:?usage: scan-attach.sh fetch|attach}"
SHARED="${SHARED:-/shared}"
CDX_TYPE="application/vnd.cyclonedx+json"
SPDX_TYPE="application/spdx+json"

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
if [ "${TLS}" = "false" ]; then regctl registry set "${HOST}" --tls disabled; fi
if [ "${USER_NAME}" != "-" ] && [ "${PASSWORD}" != "-" ]; then
  printf '%s' "${PASSWORD}" | regctl registry login "${HOST}" -u "${USER_NAME}" --pass-stdin
fi

REPOS=${BLAST_REPOS//,/ }
for repo in ${REPOS}; do
  case "${repo}" in bypassed/*) echo "» skip ${repo} (bypass — stays un-provenanced)" >&2; continue;; esac
  ref_base="${HOST}/${repo}"
  seen=""   # digests already handled (dedup tags that share a digest)
  for tag in $(regctl tag ls "${ref_base}" 2>/dev/null); do
    # Pin to the SAME digest blast-radius reads (regctl image digest) so the scan referrer lands
    # where the consumer looks. houba and regctl can resolve a tag to different digests
    # (multi-arch index vs child manifest); the digest ref removes that ambiguity.
    digest=$(regctl image digest "${ref_base}:${tag}" 2>/dev/null || echo "")
    [ -n "${digest}" ] || { echo "» ${repo}:${tag} — cannot resolve digest — skipped" >&2; continue; }
    case " ${seen} " in *" ${digest} "*) continue;; esac
    seen="${seen} ${digest}"
    ref="${ref_base}@${digest}"
    key="${repo//\//_}_${digest#sha256:}"
    short="${repo}@${digest:0:19}"   # repo@sha256:<first 12 hex>, for readable logs
    case "${MODE}" in
      fetch)
        if regctl artifact get --subject "${ref}" --filter-artifact-type "${CDX_TYPE}" \
             > "${SHARED}/${key}.sbom.json" 2>/dev/null && [ -s "${SHARED}/${key}.sbom.json" ]; then
          echo "» fetched CycloneDX SBOM for ${short}" >&2
        elif regctl artifact get --subject "${ref}" --filter-artifact-type "${SPDX_TYPE}" \
             > "${SHARED}/${key}.sbom.json" 2>/dev/null && [ -s "${SHARED}/${key}.sbom.json" ]; then
          echo "» fetched SPDX SBOM for ${short}" >&2
        else
          rm -f "${SHARED}/${key}.sbom.json"
          echo "» ${short} — no SBOM referrer (CDX or SPDX) — skipped" >&2
        fi
        ;;
      attach)
        # One referrer per analyzer: grype writes <key>.grype.sarif, regis writes <key>.regis.sarif.
        # The SBOM is <key>.sbom.json, so the *.sarif glob never matches it.
        attached=0
        for sarif in "${SHARED}/${key}".*.sarif; do
          [ -e "${sarif}" ] || continue
          houba attach "${ref}" --report "${sarif}"
          attached=$((attached + 1))
        done
        [ "${attached}" -gt 0 ] || echo "» ${short} — no SARIF (grype/regis) — skipped" >&2
        ;;
      *) echo "unknown mode ${MODE}" >&2; exit 2;;
    esac
  done
done
