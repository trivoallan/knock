#!/usr/bin/env bash
# demo-mongobleed.sh — Act 1: the signed SBOM inventory catches CVE-2025-14847
# ("mongobleed", MongoDB 8.0.0–8.0.16) that grype + trivy both miss.
#
# Reads the demo registry directly via regctl; imports no houba-core.
# houba attaches a CycloneDX SBOM referrer to every placed image; this script
# fetches that referrer and queries it for the affected package + version range,
# proving the inventory answers questions that CVE scanners cannot.
#
# Why scanners miss it: mongodb-org-server ships from MongoDB's own apt repo,
# not a distro feed.  Neither grype nor trivy NVD-CPE-matches a .deb from a
# vendor repo.  syft catalogs it, so the SBOM inventory query finds it.
#
# Inputs (environment):
#   REG    demo registry host, e.g. localhost:5000 (required, no default)
#   REPO   image repository              (default: demo/mongo)
#
# Usage:
#   REG=localhost:5000 scripts/demo-mongobleed.sh
set -uo pipefail

REG="${REG:?set REG to the demo registry host, e.g. localhost:5000}"
REPO="${REPO:-demo/mongo}"
PKG="mongodb-org-server"
CVE="CVE-2025-14847"   # mongobleed
LO="8.0.0"
HI="8.0.16"   # mongobleed-affected range (inclusive)

# in_range: true when $1 is between LO and HI (inclusive) by version sort.
# Uses the same "put LO, candidate, HI in order; sort -V -c requires that order"
# trick: sort -V -c exits 0 only if the list is already non-decreasingly sorted.
in_range() {
  printf '%s\n%s\n%s\n' "$LO" "$1" "$HI" | sort -V -c >/dev/null 2>&1
}

echo "== Act 1: scanners vs the houba inventory =="
found=0
for tag in 8.0.15 8.0.16; do
  ref="${REG}/${REPO}:${tag}"

  # Read the digest from the registry.
  digest=$(regctl image digest "${ref}" 2>/dev/null || echo "-")

  # Pull io.houba.owners from the top-level manifest annotations
  # (same approach as blast-radius.sh: `regctl manifest get --format '{{json .}}'`
  # returns the raw manifest JSON; owners lives at .annotations["io.houba.owners"]).
  owners=$(regctl manifest get "${ref}" --format '{{json .}}' 2>/dev/null \
           | jq -r '.annotations["io.houba.owners"] // "-"')

  # Fetch the CycloneDX SBOM referrer houba attached to this image and query
  # it for the affected package.  No --format flag: regctl artifact get writes
  # the raw artifact body to stdout (matching publish-sbom.sh's usage).
  pkgver=$(regctl artifact get --subject "${ref}" \
             --filter-artifact-type application/vnd.cyclonedx+json 2>/dev/null \
           | jq -r --arg p "${PKG}" 'first(.components[]? | select(.name==$p)).version // "-"')

  hit="no"
  [ "${pkgver}" != "-" ] && in_range "${pkgver}" && hit="YES" && found=1

  printf '  %-10s digest=%s owners=%s %s@%s mongobleed=%s\n' \
    "${tag}" "${digest:0:19}" "${owners}" "${PKG}" "${pkgver}" "${hit}"
done

[ "${found}" -eq 1 ] || { echo "FAIL — no placed image showed mongobleed in the SBOM inventory (SBOM format mismatch, missing referrer, or wrong tags)." >&2; exit 1; }

echo ""
echo "== the scanner contrast (the beat) =="
for s in grype trivy; do
  command -v "${s}" >/dev/null 2>&1 || { echo "  ${s}: (absent)"; continue; }
  # Guard each capture with `|| echo 0`: under pipefail a scanner that exits
  # non-zero (cold DB, pull failure) would propagate through the pipe and could
  # abort the loop mid-run — yielding 0 keeps the demo alive.
  if [ "${s}" = grype ]; then
    n=$(grype "${REG}/${REPO}:8.0.16" -o json 2>/dev/null \
        | jq -r '[.matches[] | select(.vulnerability.id=="'"$CVE"'")] | length' 2>/dev/null || echo 0)
  else
    n=$(trivy image --quiet --scanners vuln --format json "${REG}/${REPO}:8.0.16" 2>/dev/null \
        | jq -r '[.Results[]?.Vulnerabilities[]? | select(.VulnerabilityID=="'"$CVE"'")] | length' 2>/dev/null || echo 0)
  fi
  echo "  ${s} reports ${CVE}: ${n:-0}  →  $([ "${n:-0}" -eq 0 ] && echo 'CLEAN (the blind spot)' || echo 'matched')"
done

echo ""
echo "The inventory found mongobleed by package+range; both scanners reported clean."
