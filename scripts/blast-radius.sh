#!/usr/bin/env bash
# blast-radius.sh — the reference *consumer* of houba's provenance stamp.
#
# It reads nothing but the OCI annotations houba writes, and answers the two
# canonical incident-time questions:
#
#   1. "Which images derive from base digest X?"   (a CVE drops on an upstream base)
#   2. "Which images does owner Y own?"            (who do we page?)
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
#   BLAST_OWNER        (optional) filter the report to rows owned by this owner (membership)
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

# Collect (ref, base.digest, owners, policy) for every tag of every repo,
# reading the annotations off the top-level manifest (the index for multi-arch).
REPOS=${BLAST_REPOS//,/ }
ROWS_FILE=$(mktemp)

# Runtime leg: list pods via the in-cluster kube API (gated on the SA token so standalone use
# still works). Each marked pod carries houba.io/image-digest (annotation) + houba.io/cluster
# (label); we join those to each image's digest below. No kubectl binary needed.
PODS_FILE=$(mktemp)
SCAN_FILE=$(mktemp)
trap 'rm -f "${ROWS_FILE}" "${PODS_FILE}" "${SCAN_FILE}"' EXIT
SA_DIR=/var/run/secrets/kubernetes.io/serviceaccount
if [ -f "${SA_DIR}/token" ]; then
  # Query the kube API with python3 — the runtime image has no curl, and python is the same
  # interpreter the join below uses (regctl + python3, no extra deps). SA token + CA authenticate.
  if SA_DIR="${SA_DIR}" python3 - >"${PODS_FILE}" 2>/dev/null <<'PY'
import os, ssl, sys, urllib.request
sa = os.environ["SA_DIR"]
token = open(sa + "/token").read().strip()
ctx = ssl.create_default_context(cafile=sa + "/ca.crt")
req = urllib.request.Request(
    "https://kubernetes.default.svc/api/v1/pods",
    headers={"Authorization": "Bearer " + token},
)
sys.stdout.write(urllib.request.urlopen(req, context=ctx, timeout=10).read().decode())
PY
  then
    echo "» runtime: queried the kube API for marked pods (digest → cluster)" >&2
  else
    echo '{}' >"${PODS_FILE}"
    echo "» runtime: kube API query failed — RUNNING IN will show '-'" >&2
  fi
else
  echo '{}' >"${PODS_FILE}"
  echo "» runtime: no in-cluster API token — RUNNING IN will show '-'" >&2
fi

for repo in ${REPOS}; do
  ref_base="${HOST}/${repo}"
  for tag in $(regctl tag ls "${ref_base}" 2>/dev/null); do
    # Read the top-level manifest (the index for multi-arch) as JSON and pull the
    # annotations from it — same shape the examples README documents.
    manifest=$(regctl manifest get "${ref_base}:${tag}" --format '{{json .}}' 2>/dev/null || echo '{}')
    digest=$(regctl image digest "${ref_base}:${tag}" 2>/dev/null || echo '-')
    # Scan leg: fetch the scan-result referrer's SARIF (by digest) and bucket its findings.
    # Proven `artifact get --subject` (same as publish-sbom); write to a file — a large SARIF as
    # argv blows ARG_MAX. Empty file => no scan referrer on this digest.
    : > "${SCAN_FILE}"
    regctl artifact get --subject "${ref_base}:${tag}" \
      --filter-artifact-type application/vnd.houba.scan.result.v1 > "${SCAN_FILE}" 2>/dev/null || true
    REF="${repo}:${tag}" DIGEST="${digest}" python3 - "${manifest}" "${SCAN_FILE}" >>"${ROWS_FILE}" <<'PY'
import json, os, sys
ann = (json.loads(sys.argv[1] or "{}") or {}).get("annotations", {}) or {}
base = ann.get("org.opencontainers.image.base.digest", "-")
owners = ann.get("io.houba.owners", "-")
policy = ann.get("io.houba.policy", "-")
def scan_summary(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return "-"   # no scan referrer on this digest
    try:
        doc = json.load(open(path))
    except (ValueError, OSError):
        return "-"
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    def bucket(s):
        return "critical" if s >= 9 else "high" if s >= 7 else "medium" if s >= 4 else "low"
    for run in doc.get("runs") or []:
        driver = (run.get("tool") or {}).get("driver") or {}
        rules = {r.get("id"): r for r in (driver.get("rules") or [])}
        for res in run.get("results") or []:
            sev = (res.get("properties") or {}).get("security-severity")
            if sev is None:
                sev = ((rules.get(res.get("ruleId")) or {}).get("properties") or {}).get("security-severity")
            try:
                counts[bucket(float(sev))] += 1
            except (TypeError, ValueError):
                pass
    hits = [f"{k[0].upper()}{counts[k]}" for k in ("critical", "high", "medium", "low") if counts[k]]
    return " ".join(hits) if hits else "clean"
print("\t".join([os.environ["REF"], base, owners, policy, os.environ["DIGEST"], scan_summary(sys.argv[2])]))
PY
  done
done

# Render the inventory (now with the runtime column) and the rollups (optionally filtered).
BLAST_BASE_DIGEST="${BLAST_BASE_DIGEST:-}" BLAST_OWNER="${BLAST_OWNER:-}" \
  python3 - "${ROWS_FILE}" "${PODS_FILE}" <<'PY'
import json, os, sys

# digest -> sorted set of cluster labels, from the marked pods.
pods = json.load(open(sys.argv[2])) if os.path.getsize(sys.argv[2]) else {}
digest_clusters = {}
for item in pods.get("items", []) or []:
    meta = item.get("metadata", {})
    d = (meta.get("annotations", {}) or {}).get("houba.io/image-digest")
    c = (meta.get("labels", {}) or {}).get("houba.io/cluster")
    if d and c:
        digest_clusters.setdefault(d, set()).add(c)

rows = []
for line in open(sys.argv[1]):
    ref, base, owners, policy, digest, scan = (line.rstrip("\n").split("\t") + ["-"] * 6)[:6]
    clusters = ",".join(sorted(digest_clusters.get(digest, []))) or "-"
    rows.append(dict(ref=ref, base=base, owners=owners, policy=policy, digest=digest, clusters=clusters, scan=scan))

fb, fo = os.environ.get("BLAST_BASE_DIGEST", ""), os.environ.get("BLAST_OWNER", "")
def owns(row, owner):
    return owner in (row["owners"].split(",") if row["owners"] != "-" else [])
sel = [r for r in rows if (not fb or r["base"] == fb) and (not fo or owns(r, fo))]

print(f"\n=== inventory ({len(sel)}/{len(rows)} artifacts) ===")
print(f"{'REF':40} {'OWNERS':30} {'RUNNING IN':18} {'SCAN':16} BASE.DIGEST")
for r in sorted(sel, key=lambda r: r["ref"]):
    print(f"{r['ref']:40} {r['owners']:30} {r['clusters']:18} {r['scan']:16} {r['base']}")

def rollup(key, title):
    groups = {}
    for r in sel:
        groups.setdefault(r[key], []).append(r["ref"])
    print(f"\n=== blast radius by {title} ===")
    for k, refs in sorted(groups.items()):
        print(f"{k}  →  {len(refs)} image(s): {', '.join(sorted(refs))}")

def rollup_multi(key, title, empty="-"):
    groups = {}
    for r in sel:
        for v in (r[key].split(",") if r[key] != empty else [empty]):
            groups.setdefault(v, []).append(r["ref"])
    print(f"\n=== blast radius by {title} ===")
    for k, refs in sorted(groups.items()):
        print(f"{k}  →  {len(refs)} image(s): {', '.join(sorted(refs))}")

rollup("base", "base.digest (CVE on an upstream base)")
rollup_multi("owners", "owners (who to page)")
rollup_multi("clusters", "cluster (where it runs)")

missing = [r["ref"] for r in rows if r["base"] == "-"]
if missing:
    print(f"\n⚠ {len(missing)} artifact(s) carry NO houba stamp (coverage gap): {', '.join(sorted(missing))}")
PY
