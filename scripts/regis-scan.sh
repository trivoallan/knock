#!/bin/sh
# regis-scan.sh — run the regis governance analyzer on each placed image and write its
# SARIF verdicts to /shared/<key>.regis.sarif, for the attach step to bind as a referrer.
#
# regis reads the IMAGE (multi-analyzer: EOL / hygiene / licenses / CVE), unlike grype which
# reads the SBOM. It has no insecure-registry flag — it shells out to regctl, so we configure
# regctl for plain-HTTP here and regis inherits it. POSIX sh: the regis image is Alpine, no bash.
#
# Inputs (env): HOUBA_REGISTRIES, BLAST_REGISTRY (opt), BLAST_REPOS, SHARED (default /shared).
set -eu
: "${HOUBA_REGISTRIES:?set HOUBA_REGISTRIES (the registry roster JSON)}"
: "${BLAST_REPOS:?set BLAST_REPOS (space/comma-separated repositories)}"
SHARED="${SHARED:-/shared}"

# Resolve host + TLS + creds for the chosen registry from the roster (same python block the
# other demo scripts use — the regis image ships python3).
set -- $(BLAST_REGISTRY="${BLAST_REGISTRY:-}" python3 - <<'PY'
import json, os, sys
roster = json.loads(os.environ["HOUBA_REGISTRIES"])
name = os.environ.get("BLAST_REGISTRY") or (next(iter(roster)) if len(roster) == 1 else "")
if not name:
    sys.exit(f"BLAST_REGISTRY must be one of {sorted(roster)} (more than one configured)")
r = roster[name]
print(r["host"], str(r.get("tls_verify", True)).lower(), r.get("username", "-"), r.get("password", "-"))
PY
)
HOST="$1"; TLS="$2"; USER_NAME="$3"; PASSWORD="$4"

if [ "${TLS}" = "false" ]; then regctl registry set "${HOST}" --tls disabled; fi
if [ "${USER_NAME}" != "-" ] && [ "${PASSWORD}" != "-" ]; then
  printf '%s' "${PASSWORD}" | regctl registry login "${HOST}" -u "${USER_NAME}" --pass-stdin
fi

REPOS=$(echo "${BLAST_REPOS}" | tr ',' ' ')
for repo in ${REPOS}; do
  case "${repo}" in bypassed/*) echo "» skip ${repo} (bypass — stays un-provenanced)" >&2; continue;; esac
  ref_base="${HOST}/${repo}"
  seen=""
  for tag in $(regctl tag ls "${ref_base}" 2>/dev/null); do
    digest=$(regctl image digest "${ref_base}:${tag}" 2>/dev/null || echo "")
    [ -n "${digest}" ] || { echo "» ${repo}:${tag} — cannot resolve digest — skipped" >&2; continue; }
    case " ${seen} " in *" ${digest} "*) continue;; esac
    seen="${seen} ${digest}"
    ref="${ref_base}@${digest}"
    key=$(echo "${repo}" | tr '/' '_')_${digest#sha256:}
    out="${SHARED}/regis/${key}"
    mkdir -p "${out}"
    # regis writes report.sarif under --output-dir; tolerate a nonzero exit (some sub-analyzers
    # may fail against the insecure in-cluster registry) — governance verdicts from the
    # regctl-based analyzers still populate policy.*, which is the demo's point.
    regis analyze "${ref}" --sarif --output-dir "${out}" >&2 || echo "» regis exited nonzero for ${repo} (partial verdicts ok)" >&2
    f=$(find "${out}" -name report.sarif 2>/dev/null | head -1)
    if [ -n "${f}" ] && [ -s "${f}" ]; then
      cp "${f}" "${SHARED}/${key}.regis.sarif"
      echo "» regis SARIF for ${repo}@${digest#sha256:}" | cut -c1-72 >&2
    else
      echo "» ${repo}@${digest#sha256:} — no regis SARIF — skipped" >&2
    fi
  done
done
