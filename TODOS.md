# TODOS

## Transforms / placement

### Design and ADR for two-phase placement, then move it from Medium to Small

**What:** Write the design and the ADR for two-phase placement: place a rebuild into a private staging area, let an external verdict judge the rebuilt output, then promote the digest with its attestations to the destination. Once accepted, move the item from "Medium, design and ADR only" to "Small" in `docs/roadmap.md`.

**Why:** A rebuild is pushed to its destination before anything has judged its output (ADR 0051's stated limit). Until staging exists, `upgradePackages` (ADR 0054) produces repaired images that nothing evaluates before they are served, so it should not be turned on for policies that serve production.

**Context:** ADR 0054 added the repair step and deliberately left staging out: it changes the placement model, which the roadmap reserves for a design and an ADR first. The plan/apply seam (`--plan-out` / `--apply-plan`, ADR 0051) is the gate; staging is the place where a rebuilt output can be gated. Open points to settle in the design: who owns the private staging project in the registry, how promotion carries the referrers (SBOM, attestations, signature) across, and retention of refused digests. Start with the ADR, then a Deployment view in the C4 model.

**Effort:** S (design only)
**Priority:** P2
**Depends on:** a registry operator agreeing to a private, consumer-less project

### `knock verify --require repaired-since <epoch>`

**What:** A `verify` requirement that reads `steps[].params.epoch` of the `upgradePackages` step in the signed `transform/v1` predicate and fails (exit 1) when the image was not repaired, or was repaired at an earlier epoch than the one asked for.

**Why:** It turns the repair into a promotion rule any gate can check, alongside `scan-pass`, `--max-severity` and `--max-age`, without depending on a particular evaluator.

**Context:** Deferred when the step was added: nothing consumes the answer until staging exists. Nothing needs preparing, the predicate already carries the epoch in the step's params. Epochs are opaque strings to knock, so the design must say how two epochs compare (lexical order of ISO dates is the obvious convention; state it). Likely files: `knock/cli/verify.py`, `knock/use_cases/verify.py`, one test per case (absent, older, equal, newer).

**Effort:** S
**Priority:** P3
**Depends on:** two-phase placement (above), for a consumer to exist

### A third act for the kind demo: repair

**What:** One more step in the on-demand kind demo: a public image carrying a fixable OS-package CVE, a policy with `rewritePackageSources` then `upgradePackages { epoch }`, a scan before and after, and a drift guard on the vulnerability databases like the one the first act has.

**Why:** The repair has an example policy and unit tests, and one manual end-to-end run recorded in the change. A demo act replays it on every validation of the demo.

**Context:** Deferred until an image is chosen. The manual run (see `openspec/changes/upgrade-packages-step/tasks.md`, task 6.1) is the seed and shows what to avoid: `redis:7.2.0` keeps fixable findings on its own binary and on bundled Go modules, which the step cannot touch, so it makes a confusing demo; `alpine:3.18.0` and `ubuntu:jammy-20230308` go fully clean on fixable findings. An image on an end-of-life base fails the upgrade. Existing workflow: `.github/workflows/demo-mongobleed.yml` (`workflow_dispatch` only).

**Effort:** M
**Priority:** P3
**Depends on:** None

## Completed
