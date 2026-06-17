#!/usr/bin/env bash
#
# stick-test — does coverage survive Harbor's internal fan-out (entry ns -> per-team ns)?
# See docs/superpowers/specs/2026-06-17-backstage-coverage-portal-design.md ("the real fragility").
#
# The stamp is a MANIFEST ANNOTATION -> it rides the (identical) digest through any byte-for-byte
# copy, so it always survives replication. The SBOM and the cosign signature are OCI REFERRERS,
# scoped to the repository they were pushed in -> they only follow a copy that explicitly carries
# accessories. This maps exactly onto the open question:
#
#   Harbor replicates accessories   <->  regctl image copy --referrers   ->  referrers SURVIVE
#   Harbor copies the manifest only <->  regctl image copy               ->  referrers LOST
#
# It demonstrates the mechanism locally with regctl alone. Only your real Harbor's config tells you
# which branch you are on — run the same probe (artifact list) on a real replicated team-ns ref.
#
# Installs what it can clean (regctl binary, the registry container); REQUIRES docker|podman.
# Cleans up everything it created on exit; touches no global regctl state (isolated REGCTL_CONFIG).
#
set -euo pipefail

UPSTREAM="docker.io/library/busybox:1.36.1"
SBOM_TYPE="application/spdx+json"                            # the #140 SBOM referrer
SIG_TYPE="application/vnd.dev.cosign.artifact.sig.v1+json"   # the cosign signature referrer
REG_NAME="stick-test-registry"
WORK="$(mktemp -d -t stick-test.XXXXXX)"
export REGCTL_CONFIG="$WORK/regctl.json"   # isolate regctl state — wiped with $WORK
PORT="$(python3 -c 'import socket;s=socket.socket();s.bind(("",0));print(s.getsockname()[1]);s.close()')"
HOST="localhost:${PORT}"
PRE_IMG=no

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\033[31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }

cleanup() {
  set +e
  "$RUNTIME" rm -f "$REG_NAME" >/dev/null 2>&1
  [ "$PRE_IMG" = no ] && "$RUNTIME" rmi registry:2 >/dev/null 2>&1
  rm -rf "$WORK"
}
trap cleanup EXIT

# --- 1. prereqs -------------------------------------------------------------
say "[1/5] prereqs"
RUNTIME="$(command -v docker || command -v podman || true)"
[ -n "$RUNTIME" ] || fail "need docker or podman on PATH"
if ! command -v regctl >/dev/null; then
  case "$(uname -s)/$(uname -m)" in
    Darwin/arm64)  A=darwin-arm64 ;; Darwin/x86_64) A=darwin-amd64 ;;
    Linux/aarch64) A=linux-arm64  ;; Linux/x86_64)  A=linux-amd64  ;;
    *) fail "no prebuilt regctl for $(uname -s)/$(uname -m)" ;;
  esac
  echo "  downloading regctl ($A)…"
  curl -fsSL "https://github.com/regclient/regclient/releases/latest/download/regctl-${A}" -o "$WORK/regctl"
  chmod +x "$WORK/regctl"; export PATH="$WORK:$PATH"
fi
echo "  runtime: $RUNTIME · regctl: $(command -v regctl)"

# --- 2. throwaway registry --------------------------------------------------
say "[2/5] throwaway registry on ${HOST}"
"$RUNTIME" image inspect registry:2 >/dev/null 2>&1 && PRE_IMG=yes
"$RUNTIME" run -d --name "$REG_NAME" -p "127.0.0.1:${PORT}:5000" registry:2 >/dev/null
regctl registry set "$HOST" --tls disabled >/dev/null
for _ in $(seq 1 30); do regctl repo ls "$HOST" >/dev/null 2>&1 && break; sleep 0.5; done
regctl repo ls "$HOST" >/dev/null 2>&1 || fail "registry did not come up"

digest()  { regctl image digest "$1"; }
has_ref() { regctl artifact list "$1" --format '{{json .}}' 2>/dev/null | grep -q "$2"; }
refs()    { has_ref "$1" "$SBOM_TYPE" && has_ref "$1" "$SIG_TYPE" && echo "SBOM+sig present" || echo "MISSING"; }

# --- 3. entry namespace: stamped image + SBOM/signature referrers -----------
say "[3/5] entry ns — image (stamp rides the digest) + SBOM & signature referrers"
ENTRY="${HOST}/requested/busybox:1.36.1"
regctl image copy "$UPSTREAM" "$ENTRY" >/dev/null   # in prod this is houba's stamped output
printf 'fake-spdx-sbom' > "$WORK/sbom.json"; printf 'fake-cosign-sig' > "$WORK/sig.json"
regctl artifact put --subject "$ENTRY" --artifact-type "$SBOM_TYPE" --file "$WORK/sbom.json" >/dev/null
regctl artifact put --subject "$ENTRY" --artifact-type "$SIG_TYPE"  --file "$WORK/sig.json"  >/dev/null
D="$(digest "$ENTRY")"
echo "  entry digest=$D · referrers: $(refs "$ENTRY")"
[ "$(refs "$ENTRY")" = "SBOM+sig present" ] || fail "could not attach referrers at the entry"

# --- 4. scenario A — Harbor replicates accessories (copy --referrers) -------
say "[4/5] scenario A — replication carries accessories (image copy --referrers)"
TEAM_A="${HOST}/team-a/busybox:1.36.1"
regctl image copy --referrers "$ENTRY" "$TEAM_A" >/dev/null
R_A="digest $([ "$(digest "$TEAM_A")" = "$D" ] && echo 'rides ✓' || echo 'CHANGED') · referrers: $(refs "$TEAM_A")"
echo "  $R_A"

# --- 5. scenario B — Harbor copies the manifest only (no --referrers) -------
say "[5/5] scenario B — replication copies manifest only (image copy)"
TEAM_B="${HOST}/team-b/busybox:1.36.1"
regctl image copy "$ENTRY" "$TEAM_B" >/dev/null
R_B="digest $([ "$(digest "$TEAM_B")" = "$D" ] && echo 'rides ✓' || echo 'CHANGED') · referrers: $(refs "$TEAM_B")"
echo "  $R_B"

# --- result -----------------------------------------------------------------
say "RESULT"
cat <<EOF
  A  accessories replicated (--referrers) : $R_A
  B  manifest only                        : $R_B

  => The stamp (a manifest annotation) rides the identical digest in BOTH cases — provenance
     always survives the fan-out. The SBOM + signature (OCI referrers) survive ONLY when the copy
     carries accessories (A); a manifest-only copy (B) leaves them behind in the entry namespace.

  This is bar 1 (stamped, stable) vs bar 2 (referrers present in your ns, can degrade).
  Which branch your org is on = whether your Harbor replicates accessories. Probe a REAL replicated
  team-ns ref the same way:  regctl artifact list <team-ns>/<repo>:<tag>
EOF
