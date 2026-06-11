#!/usr/bin/env bash
# blast-radius.sh — the reference *consumer* of houba's provenance stamp.
#
# It reads nothing but the OCI annotations houba writes, and answers the two
# canonical incident-time questions:
#
#   1. "Which images derive from base digest X?"   (a CVE drops on an upstream base)
#   2. "Which images does team Y own?"             (who do we page?)
#
# This is deliberately generic — regctl + python3, no jq, no scanner, no lock-in.
# A real deployment points Datadog / Wiz / Trivy at the *same* annotations; this
# script is the minimal proof that the stamp alone is enough to compute blast radius.
#
# Inputs (environment):
#   HOUBA_REGISTRIES   JSON roster, same secret houba uses: {"name":{"host":...,"tls_verify":...,"username":...,"password":...}}
#   BLAST_REGISTRY     roster entry to scan (default: the sole entry)
#   BLAST_REPOS        space/comma-separated repos to walk, e.g. "demo/busybox demo/redis"
#   BLAST_BASE_DIGEST  (optional) filter the report to rows deriving from this base digest
#   BLAST_TEAM         (optional) filter the report to rows owned by this team
#
# Usage (standalone, against the local examples registry):
#   HOUBA_REGISTRIES='{"local":{"host":"localhost:5001","tls_verify":false}}' \
#   BLAST_REPOS='demo/busybox' ./scripts/blast-radius.sh
set -euo pipefail

: "${HOUBA_REGISTRIES:?set HOUBA_REGISTRIES (the registry roster JSON)}"
: "${BLAST_REPOS:?set BLAST_REPOS (space/comma-separated repositories to scan)}"

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

# Collect (ref, base.digest, owner.team, policy) for every tag of every repo,
# reading the annotations off the top-level manifest (the index for multi-arch).
REPOS=${BLAST_REPOS//,/ }
ROWS_FILE=$(mktemp)
trap 'rm -f "${ROWS_FILE}"' EXIT

for repo in ${REPOS}; do
  ref_base="${HOST}/${repo}"
  for tag in $(regctl tag ls "${ref_base}" 2>/dev/null); do
    # Read the top-level manifest (the index for multi-arch) as JSON and pull the
    # annotations from it — same shape the examples README documents.
    manifest=$(regctl manifest get "${ref_base}:${tag}" --format '{{json .}}' 2>/dev/null || echo '{}')
    REF="${repo}:${tag}" python3 - "${manifest}" >>"${ROWS_FILE}" <<'PY'
import json, os, sys
ann = (json.loads(sys.argv[1] or "{}") or {}).get("annotations", {}) or {}
base = ann.get("org.opencontainers.image.base.digest", "-")
team = ann.get("io.houba.owner.team", "-")
policy = ann.get("io.houba.policy", "-")
print("\t".join([os.environ["REF"], base, team, policy]))
PY
  done
done

# Render the inventory and the two blast-radius rollups (optionally filtered).
BLAST_BASE_DIGEST="${BLAST_BASE_DIGEST:-}" BLAST_TEAM="${BLAST_TEAM:-}" \
  python3 - "${ROWS_FILE}" <<'PY'
import os, sys
rows = []
for line in open(sys.argv[1]):
    ref, base, team, policy = (line.rstrip("\n").split("\t") + ["-", "-", "-", "-"])[:4]
    rows.append(dict(ref=ref, base=base, team=team, policy=policy))

fb, ft = os.environ.get("BLAST_BASE_DIGEST", ""), os.environ.get("BLAST_TEAM", "")
sel = [r for r in rows if (not fb or r["base"] == fb) and (not ft or r["team"] == ft)]

print(f"\n=== inventory ({len(sel)}/{len(rows)} artifacts) ===")
print(f"{'REF':40} {'TEAM':12} {'POLICY':12} BASE.DIGEST")
for r in sorted(sel, key=lambda r: r["ref"]):
    print(f"{r['ref']:40} {r['team']:12} {r['policy']:12} {r['base']}")

def rollup(key, title):
    groups = {}
    for r in sel:
        groups.setdefault(r[key], []).append(r["ref"])
    print(f"\n=== blast radius by {title} ===")
    for k, refs in sorted(groups.items()):
        print(f"{k}  →  {len(refs)} image(s): {', '.join(sorted(refs))}")

rollup("base", "base.digest (CVE on an upstream base)")
rollup("team", "owner.team (who to page)")

missing = [r["ref"] for r in rows if r["base"] == "-"]
if missing:
    print(f"\n⚠ {len(missing)} artifact(s) carry NO houba stamp (coverage gap): {', '.join(sorted(missing))}")
PY
