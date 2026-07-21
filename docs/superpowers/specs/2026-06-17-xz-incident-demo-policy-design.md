# XZ / CVE-2024-3094 incident demo policy — design

Date: 2026-06-17
Status: Approved (brainstorm)

## Goal

Make the reference deployment's package-level blast-radius loop light up on a **real,
recognizable incident** instead of a generic image. Reproduce the **XZ backdoor
(CVE-2024-3094)** so that, in the demo, querying Dependency-Track for `xz-utils` surfaces the
affected image — the front-door supply-chain story made concrete.

**The claim — and the guardrail.** The demo says: *"the day the CVE was disclosed,
blast-radius became one query, third-party images included."* It must **never** imply knock
*detects* or *blocks* the backdoor. knock rebuilds faithfully from its mirror; if the mirror
ships the backdoored `xz 5.6.1`, knock rebuilds *with* it — and stamps + SBOMs it, so the
post-disclosure query has an answer. The hero is the signed inventory at the front door, not a
scanner. Any narration that suggests detection is a defect.

### Why XZ (set aside: Log4Shell, Heartbleed)

XZ is the supply-chain build-time injection whose narrative *is* the front door: a backdoor in
an upstream OS dependency, and the single mandated entry point is what makes the blast-radius
query answerable on disclosure day. Topical (2024), and it tells the coverage story better than
a Java-depth case. One incident, done well — not a catalogue.

## Feasibility (validated by spike, 2026-06-17)

- **OSV match:** `POST api.osv.dev/v1/query` for `pkg:deb/debian/xz-utils@5.6.1-1` returns
  `DEBIAN-CVE-2024-3094` (ecosystem `Debian:13`). This is exactly what DT matches once its OSV
  Debian mirror is populated (`make dt-vulns`).
- **Match is on the *source* package `xz-utils`, not `liblzma5`** (`liblzma5@5.6.1-1` → no
  match). The image must carry the `xz-utils` package at `5.6.1-1`.
- **Retrievability:** `xz-utils 5.6.1-1` (and `5.6.0-0.1/0.2`) are archived on
  `snapshot.debian.org` (84 versions total). Reproducible from a pinned sid snapshot
  (~`20240328`).
- **Not in stable:** `Debian:12` (bookworm) does not match `5.6.1-1` — consistent with the real
  incident (stable never shipped it). The fixture must use a sid-era snapshot, not `debian:stable`.

## Architecture

knock's rebuild path derives `FROM <source>` and applies transform steps (the `debian-tz`
example rebuilds `library/debian` with `setTimezone`). There is **no "install package"
transform**, and the knock SBOM is produced **only on the rebuild path** (copy does not SBOM).
So the vulnerable `xz` version must arrive via the **source image**, and the image must be
**rebuilt** (not copied) to get a knock SBOM. The chosen shape (no knock core change):

### Three artifacts

1. **The fixture — a deliberately-vulnerable "upstream" image.**
   A `Dockerfile` that starts from a sid snapshot and installs the backdoored `xz`:
   ```dockerfile
   # demo fixture — DELIBERATELY VULNERABLE (CVE-2024-3094, the XZ backdoor). Inert as a static
   # layer (no sshd/systemd at runtime); built only to be rebuilt + inventoried by knock.
   FROM debian:sid
   RUN printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20240328T000000Z/ sid main\n' \
         > /etc/apt/sources.list && rm -f /etc/apt/sources.list.d/* \
    && apt-get update \
    && apt-get install -y --no-install-recommends xz-utils \
    && dpkg-query -W xz-utils    # expect 5.6.1-1
   LABEL org.opencontainers.image.description="demo fixture — deliberately vulnerable, CVE-2024-3094"
   ```
   Built **without** an SBOM attestation (knock's rebuild generates the real one) and pushed to
   the demo registry as a pretend-upstream, e.g. `upstream/debian-xz:5.6.1`.

2. **The hit — rebuilt through the front door.**
   A new MirrorPolicy sources the fixture and **rebuilds** it with a hardening transform
   (`setTimezone` — the only no-config built-in, and it reinforces "the front door hardens").
   The rebuild re-scans the final filesystem → the knock SPDX SBOM captures the inherited
   `xz-utils 5.6.1-1` → stamp + sign → pushed to `demo/debian-xz`. `publish-sbom` uploads it →
   DT flags `DEBIAN-CVE-2024-3094`.

3. **The bypass — the durable blind spot.**
   An image copied **directly** into the registry with `regctl` (never through knock) — no
   stamp, no SBOM, invisible to the inventory. e.g. `bypassed/debian-xz`. This is the *durable*
   coverage contrast: it survives the roadmap's future "SBOM on copied images" (the blind spot
   is "never came through the mandated door", not "copied vs rebuilt").

### The demo "aha" — one query, three states

- **DT** (`make dt-ui`): search `xz-utils` → `demo/debian-xz` is **red** (CVE-2024-3094); the
  clean stamped images (`demo/busybox`, `demo/debian-eu/-us`) stay **green** — precision, not FUD.
- **Coverage** (`knock audit` has-SBOM dimension / `blast-radius.sh` "⚠ N artifact(s) carry NO
  knock stamp"): `bypassed/debian-xz` is **uncovered** — the durable blind spot.
- **Narration:** "XZ dropped at 2am; the front-door images answered in one query — including the
  third-party `debian-xz`. The bypass image is the unknown: what never came through the door is
  ungovernable."

## Wiring (demo only)

- **Fixture build + push** to the in-cluster Zot. Mechanism is a plan-time detail (build via the
  demo's `buildkitd` and push, or host `docker build` + push through a port-forward) — see Risks.
- **Incident policy**: `docs/examples/incidents/xz-cve-2024-3094/xz.yml` — `source` = the fixture
  in the demo registry; one import; `transform: [setTimezone]`; destination `demo/debian-xz`.
- **Bypass placement**: one `regctl image copy <fixture> <registry>/bypassed/debian-xz` step,
  out-of-band (explicitly *not* via knock).
- **Coverage**: `BLAST_REPOS += demo/debian-xz bypassed/debian-xz` so the report walks both.
- **Orchestration**: a `make incident-xz` target (or folded into `make demo`/`make local`) that
  chains: build+push fixture → reconcile the incident policy → place the bypass image →
  `publish-sbom`, with narration echoes. The incident policy is reconciled in addition to the
  reference policy (POLICY_DIR or an explicit reconcile of the incident dir).

## Docs (CLAUDE.md obligations)

- **New example** `docs/examples/incidents/xz-cve-2024-3094/`: the MirrorPolicy + a README
  walkthrough carrying the narration **and** the "never claims detection" guardrail, plus the
  `_category_.json` if the examples site needs it.
- **Walkthrough / roadmap**: a note that the demo now reproduces a real incident (the package-
  level loop is shown, not just asserted). Update `deploy/overlays/local/README.md`.
- **C4**: no model change expected — `snapshot.debian.org` is just another upstream source and
  the fixture is a demo artifact; neither is a new modeled actor/system. Add a one-line note to
  the deploy-view prose only if a reviewer finds it warranted.
- **No knock core change** ⇒ no `make reference`, no coverage-gate impact. Everything lives in
  `docs/examples/`, `deploy/`, `scripts/`, and a fixture `Dockerfile`.

## Safety / honesty

- The fixture is **clearly labeled** deliberately-vulnerable (OCI label + README banner). The
  CVE-2024-3094 payload is **inert** in this context — it only triggers in a running
  sshd-via-systemd-via-liblzma path, which a static demo image never executes. Shipping it is an
  incident-response-exercise artifact, not a live threat, and it is built from public archives.
- The narrative guardrail (no implication of detection/blocking) is enforced in the README and
  the `make` echoes.

## Out of scope (YAGNI)

- Other incidents (Log4Shell, Heartbleed) — one incident, done well.
- Any knock core change: no new transform, no new use case, no SBOM-format change.
- The roadmap's future "SBOM on copied images" — a separate item; this design is built to *not*
  depend on copy-vs-rebuild for the blind spot.
- Re-triggering DT's vuln mirror — already handled by `make dt-vulns`.

## Risks / assumptions to verify in the plan

1. **Fixture hosting mechanism** (build + push to the in-cluster Zot) — the main plumbing
   unknown. Resolve early: pick build-via-buildkitd-and-push vs host-build-and-push.
2. **The rebuild's SBOM captures inherited `xz-utils 5.6.1-1`** (buildkit's syft scan of the
   final filesystem, not just changed layers). Assumed yes; verify against a real rebuild.
3. **Rebuild is triggered by having a transform** (an import with no transform takes the copy
   path → no SBOM). Assumed from `debian-tz` (transforms) vs `busybox` (copy); verify, and ensure
   the incident import carries `setTimezone`.
4. **Sourcing from the local plain-HTTP Zot** works for the policy `source` (insecure-registry
   handling derived from the roster `tls_verify=false`, same as the rebuild push). Verify the
   `source.registry` reference resolves and pulls.
5. **OSV match end-to-end**: confirm the live DT (OSV Debian mirror populated via `make dt-vulns`)
   actually flags `demo/debian-xz` — the spike proved the OSV data; the full chain
   (rebuild SBOM → purl → DT analysis) is confirmed only by a live run.

## File-change summary

New:
- `deploy/.../debian-xz.Dockerfile` (the fixture; exact path a plan detail)
- `docs/examples/incidents/xz-cve-2024-3094/xz.yml` + `README.md` (+ `_category_.json` if needed)

Edited:
- `deploy/base/kustomization.yaml` (`BLAST_REPOS`) and/or the overlay configMap
- `Makefile` (`incident-xz` target; orchestration + narration echoes)
- `deploy/overlays/local/README.md`, `docs/roadmap.md` (note the incident demo)

Untouched: all of `knock/` (no core change), `make reference` output.
