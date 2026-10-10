# TODOS

## Transforms / placement

### `knock verify --require repaired-since <epoch>`

**What:** A `verify` requirement that reads `steps[].params.epoch` of the `upgradePackages` step in the signed `transform/v1` predicate and fails (exit 1) when the image was not repaired, or was repaired at an earlier epoch than the one asked for.

**Why:** It turns the repair into a promotion rule any gate can check, alongside `scan-pass`, `--max-severity` and `--max-age`, without depending on a particular evaluator.

**Context:** Deferred when the step was added: nothing consumed the answer before staging existed (ADR 0055). Nothing needs preparing, the predicate already carries the epoch in the step's params. Epochs are opaque strings to knock, so the design must say how two epochs compare (lexical order of ISO dates is the obvious convention; state it). Likely files: `knock/cli/verify.py`, `knock/use_cases/verify.py`, one test per case (absent, older, equal, newer).

**Effort:** S
**Priority:** P3
**Depends on:** None (staging exists since ADR 0055)

### A third act for the kind demo: repair

**What:** One more step in the on-demand kind demo: a public image carrying a fixable OS-package CVE, a policy with `rewritePackageSources` then `upgradePackages { epoch }`, a scan before and after, and a drift guard on the vulnerability databases like the one the first act has.

**Why:** The repair has an example policy and unit tests, and one manual end-to-end run recorded in the change. A demo act replays it on every validation of the demo.

**Context:** Deferred until an image is chosen. The manual run (see `openspec/changes/upgrade-packages-step/tasks.md`, task 6.1) is the seed and shows what to avoid: `redis:7.2.0` keeps fixable findings on its own binary and on bundled Go modules, which the step cannot touch, so it makes a confusing demo; `alpine:3.18.0` and `ubuntu:jammy-20230308` go fully clean on fixable findings. An image on an end-of-life base fails the upgrade. Existing workflow: `.github/workflows/demo-mongobleed.yml` (`workflow_dispatch` only).

**Effort:** M
**Priority:** P3
**Depends on:** None

## Completed

### Two-phase placement

**Completed:** staging registry and `knock promote` (ADR 0055, OpenSpec change `stage-and-promote-rebuilds`), 2026-10-10. The open point about who owns a private staging project went away: staging is any registry of the roster, an ephemeral one in the simplest form.

