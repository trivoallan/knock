#!/usr/bin/env bash
#
# spike-mongobleed.sh — de-risk AND regression-guard the brownfield demo's core premise.
#
# Finding this encodes (verified 2026-06-26): grype AND trivy both report the official
# `mongo` image CLEAN of CVE-2025-14847 ("mongobleed", CISA-KEV, CVSS 8.7), because
# `mongodb-org-server` ships from MongoDB's own apt repo (not a distro feed) and neither
# scanner NVD-CPE-matches a deb. But syft CATALOGS mongodb-org-server@<vuln-version>, so the
# package-level SBOM *inventory* query finds the blast radius the scanners miss. That gap is the
# demo's headline value beat, not a bug — so we assert it stays true:
#
#   Act 1 premise (always):  grype==0  AND  trivy==0  on the mongo CVE,  AND  syft inventory>=1
#   Act 2 gate    (--gate):  grype flags the XZ image,  attach --fail-on exits 1
#
# Run as a spike (go/no-go) or in CI as a regression guard. Exits non-zero on any broken assert.
#
# Deps: grype, syft, jq (Act 1).  + trivy (Act 1 scanner-blind-spot beat).  + regctl, houba,
#       a writable registry (Act 2, opt-in via --gate).
#
# Usage:
#   scripts/spike-mongobleed.sh                         # Act 1 premise only
#   scripts/spike-mongobleed.sh --gate localhost:5001   # + Act 2 gate against a throwaway registry
#
set -uo pipefail

MONGO_IMG="${MONGO_IMG:-mongo:7.0.14}"          # any 7.0.0-7.0.27 is mongobleed-affected
MONGO_CVE="${MONGO_CVE:-CVE-2025-14847}"
MONGO_PKG="${MONGO_PKG:-mongodb-org-server}"
XZ_IMG="${XZ_IMG:-demo/debian-xz:5.6.1}"        # Act 2 gate target (scanner-clean: liblzma deb)
XZ_CVE="${XZ_CVE:-CVE-2024-3094}"
THRESHOLD="${THRESHOLD:-high}"
GATE_REG=""
[ "${1:-}" = "--gate" ] && GATE_REG="${2:?--gate needs a registry, e.g. localhost:5001}"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
fail=0
say()  { printf '%s\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$*"; fail=1; }

need() { command -v "$1" >/dev/null 2>&1 || { say "missing dependency: $1"; exit 127; }; }
need grype; need syft; need jq

say "== spike/guard: $MONGO_CVE on $MONGO_IMG (work: $WORK) =="
export GRYPE_DB_AUTO_UPDATE=false
grype db status >/dev/null 2>&1 || { say "grype DB missing — run 'GRYPE_DB_AUTO_UPDATE=true grype db update' once."; exit 1; }

# --- Act 1 premise: the scanners miss it, the inventory catches it ---
say "[Act 1] scanner blind-spot vs SBOM inventory"

grype "$MONGO_IMG" -o json > "$WORK/grype.json" 2>/dev/null
GR=$(jq -r --arg c "$MONGO_CVE" '[.matches[]|select(.vulnerability.id==$c)]|length' "$WORK/grype.json")
[ "${GR:-1}" -eq 0 ] && ok "grype reports 0 $MONGO_CVE (blind to the vendor-repo package)" \
                     || bad "grype now matches $MONGO_CVE ($GR) — the blind-spot beat changed; revisit the demo framing"

if command -v trivy >/dev/null 2>&1; then
  trivy image --quiet --scanners vuln --format json "$MONGO_IMG" 2>/dev/null > "$WORK/trivy.json"
  TR=$(jq -r --arg c "$MONGO_CVE" '[.Results[]?.Vulnerabilities[]?|select(.VulnerabilityID==$c)]|length' "$WORK/trivy.json")
  [ "${TR:-1}" -eq 0 ] && ok "trivy reports 0 $MONGO_CVE" \
                       || bad "trivy now matches $MONGO_CVE ($TR) — revisit the demo framing"
else
  say "  (trivy absent — skipping the second-scanner leg of the beat)"
fi

syft "$MONGO_IMG" -o syft-json > "$WORK/syft.json" 2>/dev/null
INV=$(jq -r --arg p "$MONGO_PKG" '[.artifacts[]|select(.name==$p)]|length' "$WORK/syft.json")
VER=$(jq -r --arg p "$MONGO_PKG" 'first(.artifacts[]|select(.name==$p)).version // "?"' "$WORK/syft.json")
[ "${INV:-0}" -ge 1 ] && ok "syft inventory catches $MONGO_PKG@$VER (the query the scanners can't answer)" \
                      || bad "syft no longer catalogs $MONGO_PKG — Act 1's inventory query breaks"

# --- Act 2 gate (opt-in): the front door says no on a scanner-flagged image ---
if [ -n "$GATE_REG" ]; then
  say "[Act 2] --fail-on gate on $XZ_IMG"
  need regctl; need houba
  REG="$GATE_REG/spike/$(basename "$XZ_IMG")"
  if regctl image copy "$XZ_IMG" "$REG" >/dev/null 2>&1; then
    grype "$REG" -o sarif > "$WORK/xz.sarif" 2>/dev/null
    XZHIT=$(jq -r --arg c "$XZ_CVE" '[.runs[0].results[]?|select(.ruleId==$c)]|length' "$WORK/xz.sarif")
    [ "${XZHIT:-0}" -ge 1 ] && ok "grype flags $XZ_CVE on the gate image" \
                            || bad "grype does not flag $XZ_CVE — the gate has nothing to block"
    houba attach "$REG" --report "$WORK/xz.sarif" --fail-on "$THRESHOLD" >/dev/null 2>&1; RC=$?
    case "$RC" in
      1) ok "attach --fail-on $THRESHOLD exits 1 — image GATED (the win)";;
      2) bad "attach exits 2 (AdapterError) — registry write failed; needs WRITE creds (finding D-a)";;
      0) bad "attach exits 0 — gate did NOT fire (stale DB, or SARIF kind trap; finding D-b)";;
      *) bad "attach exits $RC — unexpected";;
    esac
  else
    bad "could not copy $XZ_IMG to $REG — build the demo XZ image / check the registry"
  fi
else
  say "[Act 2] skipped (pass '--gate <registry>' to assert the --fail-on exit code)"
fi

say "=="
[ "$fail" -eq 0 ] && { say "GO / GREEN: demo premise holds."; exit 0; } \
                  || { say "BROKEN: an assert failed (see FAIL above)."; exit 1; }
