#!/usr/bin/env bash
# migration-parity-proof.sh — prove houba's `destinations` fan-out keeps the package-SBOM
# referrer alive in EVERY team copy, which registry replication strips (goharbor/harbor#23210).
#
# Optionally reconciles the multi-destination migration example, then for every team copy
# asserts a package-SBOM referrer (CycloneDX or SPDX) is present on the placed digest. Exits
# non-zero — naming the bare copy — if any copy is missing it. Proves houba's *positive*
# (placement attaches referrers everywhere); it does NOT stand up Harbor to show stripping.
#
# Inputs (environment):
#   HOUBA_REGISTRIES  registry roster JSON (required)
#   PROOF_REGISTRY    which roster entry to target (optional if exactly one configured)
#   PROOF_REPOS       space/comma-separated team repos to check
#                     (default: "team-a/redis team-b/redis", matching docs/examples/migration)
#   POLICY_DIR        if set, `houba reconcile` this dir first (e.g. docs/examples/migration)
set -euo pipefail
: "${HOUBA_REGISTRIES:?set HOUBA_REGISTRIES (the registry roster JSON)}"
PROOF_REPOS="${PROOF_REPOS:-team-a/redis team-b/redis}"
CDX_TYPE="application/vnd.cyclonedx+json"
SPDX_TYPE="application/spdx+json"

read -r HOST TLS USER_NAME PASSWORD < <(
  PROOF_REGISTRY="${PROOF_REGISTRY:-}" python3 - <<'PY'
import json, os, sys
roster = json.loads(os.environ["HOUBA_REGISTRIES"])
name = os.environ.get("PROOF_REGISTRY") or (next(iter(roster)) if len(roster) == 1 else "")
if not name:
    sys.exit(f"PROOF_REGISTRY must be one of {sorted(roster)} (more than one configured)")
r = roster[name]
print(r["host"], str(r.get("tls_verify", True)).lower(), r.get("username", "-"), r.get("password", "-"))
PY
)
if [ "${TLS}" = "false" ]; then regctl registry set "${HOST}" --tls disabled; fi
if [ "${USER_NAME}" != "-" ] && [ "${PASSWORD}" != "-" ]; then
  printf '%s' "${PASSWORD}" | regctl registry login "${HOST}" -u "${USER_NAME}" --pass-stdin
fi

# Presence check for a package-SBOM referrer on a digest ref (CycloneDX or SPDX), using the
# same `artifact get --filter-artifact-type` idiom as scan-attach.sh.
has_sbom() {
  local ref="$1" tmp ok=1
  tmp=$(mktemp)
  if regctl artifact get --subject "${ref}" --filter-artifact-type "${CDX_TYPE}" > "${tmp}" 2>/dev/null && [ -s "${tmp}" ]; then
    ok=0
  elif regctl artifact get --subject "${ref}" --filter-artifact-type "${SPDX_TYPE}" > "${tmp}" 2>/dev/null && [ -s "${tmp}" ]; then
    ok=0
  fi
  rm -f "${tmp}"
  return "${ok}"
}

if [ -n "${POLICY_DIR:-}" ]; then
  echo "» reconciling ${POLICY_DIR} into ${HOST}" >&2
  houba reconcile "${POLICY_DIR}"
fi

REPOS=${PROOF_REPOS//,/ }
failures=0
checked=0
for repo in ${REPOS}; do
  ref_base="${HOST}/${repo}"
  tags=$(regctl tag ls "${ref_base}" 2>/dev/null || echo "")
  if [ -z "${tags}" ]; then
    echo "FAIL ${repo} — no tags placed (did reconcile run?)" >&2
    failures=$((failures + 1))
    continue
  fi
  seen=""   # dedup tags that share a digest
  for tag in ${tags}; do
    digest=$(regctl image digest "${ref_base}:${tag}" 2>/dev/null || echo "")
    [ -n "${digest}" ] || continue
    case " ${seen} " in *" ${digest} "*) continue ;; esac
    seen="${seen} ${digest}"
    checked=$((checked + 1))
    ref="${ref_base}@${digest}"
    short="${repo}:${tag}@${digest:0:19}"
    if has_sbom "${ref}"; then
      echo "PASS ${short} — SBOM referrer present"
    else
      echo "FAIL ${short} — no SBOM referrer (replication would have stripped it)" >&2
      failures=$((failures + 1))
    fi
  done
done

echo "—— ${checked} team copy/copies checked across: ${REPOS} ——" >&2
if [ "${failures}" -gt 0 ]; then
  echo "migration-parity proof FAILED: ${failures} copy/copies missing the SBOM referrer" >&2
  exit 1
fi
echo "migration-parity proof PASSED: every team copy is self-describing" >&2
