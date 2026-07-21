# Coverage audit — design (roadmap ④, the verifiable front door)

> **Status:** approved design, pre-implementation. Builds on the provenance *annotation*
> stamp (`knock/domain/stamp.py`) and the catalog-walk pattern proven by `knock purge`
> (`use_cases/purge.py`). The terminal step after this spec is `writing-plans`.

## 1. Context & motivation

knock is a **stamper / single front door** for external OCI images. The roadmap's product
thesis has two load-bearing claims: *"the label is the product"* (frozen by roadmap ① — the
provenance schema + SLSA/in-toto attestation, now shipped) and *"coverage gates value"* — a
stamp on 40 % of the fleet yields a blast-radius query with blind spots, useless in an
incident. knock's value is proportional to it being the **mandatory** path for external images.

Roadmap ④ makes that measurable: *"Show me the images in the registry that do **not** carry
knock's stamp"* — a coverage-gap report. This is what makes the front door **verifiable**, and
therefore **enforceable**: without it, "mandatory front door" is a wish. `knock audit` is that
report.

## 2. Decisions taken (the four forks)

| Fork | Decision | Why |
|---|---|---|
| **Frame of reference** | **Whole-registry sweep** | The roadmap's literal ask — walk the registry and surface *every* image lacking the stamp, including unmanaged / rogue ones. A policy-anchored diff (expected vs actual for declared repos) is blind to images outside the policy set, so it cannot answer "is the front door actually mandatory?". Reuses the `purge` catalog-walk. |
| **What "covered" means** | **The annotation stamp** | The universal mark knock writes on *every* processed image (copy **and** rebuild). Directly answers "which images lack the stamp". One read per image, a pure predicate. The signed-attestation layer (rebuild-only today) becomes a stricter coverage *tier* later — auditing it now would flag most legitimate knock (copy) images as "uncovered". |
| **Exit-code / gating** | **Report-only by default + opt-in `--fail-on-uncovered`** | A whole-registry sweep always contains legitimately-unstamped third-party images, so failing on any gap is a bad default (fails almost always). Default exit 0 (a visibility report); opt-in gating turns it into a CI gate when the org wants to enforce. |
| **Read primitive at scale** | **A lightweight `RegistryPort.get_annotations`** | A whole-registry sweep over thousands of tags makes per-image cost matter. Reusing `inspect` is 3 `regctl` calls/image (`image digest` + `manifest get` + `image config`), two of them useless here. A dedicated `get_annotations` is **one** `manifest get` — ~3× fewer subprocess spawns — at the cost of one new port method. Chosen over bare reuse because the sweep is the hot path. |

## 3. Scope (v1)

**In:**
- A new **read-only** verb `knock audit [--registry NAME] [--fail-on-uncovered]`.
- A **whole-registry catalog walk** over the configured roster (or a single `--registry`),
  reusing the `purge` pattern: configure/login once per host → `list_repositories` →
  `list_tags` → read annotations → classify.
- A **pure coverage predicate** `domain/coverage.py:is_stamped(annotations, *, prefix)`.
- A new **lightweight read** `RegistryPort.get_annotations(image_ref) -> dict[str, str]`
  (one `regctl manifest get`), with its adapter, fake, and fake-bin branch.
- A **`CoverageReport`** contract (per-image outcomes + counts), rendered text + JSON via the
  existing render layer, and an `audit_exit_code` (0 default; opt-in gating; per-image read
  errors redden it).

**Out (deferred / explicitly not v1):**
- **Attestation-coverage tier** (signed vs unsigned). A natural follow-up once the copy path is
  also attested; until then most knock images are unsigned-but-stamped, so a signed-coverage
  audit would mislead. (Resolved: annotation-stamp only in v1.)
- **Concurrency.** The walk is **sequential** in v1, exactly like `purge`. Parallelising the
  reads (a `ThreadPoolExecutor`, as in `reconcile`) is a focused scale-up follow-up.
- **Repo / prefix filters** beyond `--registry`. The roster + `--registry` is the v1 selector.
- **Dedup by digest.** The unit of "an image in the registry" is the **tag**; the report is
  per `repo:tag`. (A multi-tagged digest appears once per tag — acceptable for v1.)
- **Any mutation.** `knock audit` never writes — no stamping, no deletion, no referrers.

## 4. Architecture — hexagonal placement

The standard knock layering, mirroring `purge` (which is the closest sibling: a read-only
catalog walk that classifies each image and emits a report + exit code).

```
cli/audit.py  (thin: build container → walk → render → exit)
      │
      ▼
use_cases/audit.py   audit_coverage(...) -> CoverageReport
      │  depends only on ports (RegistryPort) + config roster
      ├──────────────► domain/coverage.py   is_stamped(annotations, prefix) -> bool   (pure)
      ▼
ports/registry.py    + get_annotations(image_ref) -> dict[str, str]   (new read)
      ▲
adapters/regctl_cli.py   RegctlAdapter.get_annotations  (one `regctl manifest get`)
```

- **`domain/coverage.py`** (pure; ≥ 90 % coverage; `mypy --strict`). `is_stamped(annotations:
  dict[str, str], *, prefix: str) -> bool`: an image carries knock's stamp iff it shows the
  lineage knock writes. With a non-empty `prefix` (default `io.knock`), the definitive signal is
  the knock-namespaced lineage key **`{prefix}.policy`**. With an **empty** prefix (knock emits
  only OCI-standard keys), fall back to **`org.opencontainers.image.base.digest`** — the
  idempotency key knock writes in every case. Pure, no I/O.
  - *Known limitation (documented):* `org.opencontainers.image.base.digest` is an OCI-standard
    key, not knock-exclusive — a non-knock tool could in principle set it, so the empty-prefix
    fallback is a heuristic. The `{prefix}.policy` key (the default path) is the strong,
    knock-specific signal. This is acceptable: empty-prefix deployments deliberately trade the
    knock namespace away.

- **`ports/registry.py`** — add one method to the `RegistryPort` Protocol:
  `def get_annotations(self, image_ref: str) -> dict[str, str]: ...` — return the OCI
  manifest/index annotations for a ref (the stamp sits on the **index** for a multi-arch image).
  No new data model.

- **`adapters/regctl_cli.py`** — `RegctlAdapter.get_annotations`: run
  `regctl manifest get <ref> --format "{{json .}}"`, parse the JSON, return its `annotations`
  map (`{}` when absent). This is the annotation-extraction half of the existing `inspect`,
  without the `image digest` / `image config` calls. Raises `RegctlError` on failure (existing
  pattern). `FakeRegistryPort.get_annotations` seeds from a constructor-supplied
  `annotations: dict[str, dict[str, str]]` map. New fake-bin branch: `regctl` already handles
  `manifest get` — extend its scenarios so a tag can return stamped vs unstamped annotations.

- **`use_cases/audit.py`** — `audit_coverage(*, registry, roster, only_registry, label_prefix)
  -> CoverageReport`. No clock dependency (unlike `purge`, the audit has no time window).
  Structurally identical to `purge_marks`: resolve targets (one
  `--registry` or the whole roster), `configure_registry` + `login` once per host, then
  `for repo in list_repositories(host): for tag in list_tags(repo): classify(get_annotations(...))`.
  Each image is processed in isolation — a read failure on one tag becomes a recorded error
  outcome and the walk continues (continue-and-collect, like purge). Sequential v1. Depends only
  on ports.

- **`cli/audit.py`** — Typer command `knock audit`, options `--registry NAME` (restrict to one
  roster entry; default = all) and `--fail-on-uncovered` (opt-in gating). Builds the composition
  root, runs `audit_coverage`, renders the report, raises `typer.Exit(audit_exit_code(...))`.
  Registered in `cli/main.py` alongside `reconcile` / `purge` / `attach`.

## 5. The contract — `CoverageReport`

A Pydantic model in `use_cases/audit.py` (sibling of `PurgeReport`):

```
CoverageOutcome:
    image_ref: str                 # "<host>/<repo>:<tag>"
    covered: bool                  # is_stamped(...)
    policy: str | None = None      # {prefix}.policy when covered & present (audit context)
    error: ErrorInfo | None = None # set => a hard failure reading this image

CoverageCounts:
    scanned: int                   # outcomes attempted
    covered: int
    uncovered: int
    errored: int

CoverageReport:
    registries: list[str]          # hosts walked
    counts: CoverageCounts
    outcomes: list[CoverageOutcome]
```

`audit_exit_code(report, *, fail_on_uncovered: bool) -> int`:
- the worst per-image **read-error** exit code if any outcome errored (≥ 2, via `exit_code_for`);
- else **1** if `fail_on_uncovered` **and** `counts.uncovered > 0` (the gate fired);
- else **0**.

Rendered through the existing render layer (text + JSON, switched by `KNOCK_LOG_FORMAT`): a text
summary line (`audit  scanned=N covered=C uncovered=U errored=E`) plus the uncovered (and
errored) `image_ref`s; the full structured `CoverageReport` in JSON mode. (Extend
`cli/render.py` with an `audit` renderer, matching how it renders the reconcile / purge reports.)

## 6. Errors & exit codes

No new error type. A registry read failure while inspecting one image is caught per-image,
recorded as `ErrorInfo(type, message, exit_code=exit_code_for(exc))` on that outcome, and the
walk continues — a flaky registry degrades the report, it never aborts the sweep. `audit_exit_code`
surfaces the worst such code. Config problems (unknown `--registry`, empty roster) surface as
`ConfigError` (exit 3) **before** the walk, via the existing `resolve_registry`.

## 7. Cross-cutting sync obligations (CLAUDE.md — part of the same change)

- **C4 / `docs/architecture/workspace.dsl`** — `knock audit` adds **no external system** (it
  reads the same Destination Registries via `regctl`), so the Context / Landscape views are
  unchanged. Add the internal components in lockstep: `cli audit` (CLI group), `ucAudit`
  (use-case group, "Catalog-walks the registry and reports images missing the provenance
  stamp"), `domCoverage` (domain group, "Pure stamp-presence predicate"), and the
  `get_annotations` read on `RegistryPort`; wire `cliAudit → ucAudit`, `ucAudit → portRegistry`,
  `ucAudit → domCoverage`. Refresh the committed Mermaid exports (`structurizr validate` +
  `inspect -s error,warning` clean, then `export`).
- **`docs/examples/`** — add a `knock audit` walkthrough to `docs/examples/README.md` (run it
  against the local `registry:2` after a reconcile; show a covered vs uncovered listing and the
  `--fail-on-uncovered` gate).
- **ADR** — a thin ADR under `docs/architecture/decisions/` linking to this spec.
- **`CLAUDE.md`** — extend the inventory: the `audit` verb / use case, `domain/coverage.py`, and
  the new `RegistryPort.get_annotations` read.
- **JSON Schema** — `CoverageReport` is a Pydantic model; publish its derived schema
  (`*_json_schema()` helper) like `run_report_json_schema`, with a stable-and-serializable test.

## 8. Testing

- **Unit — `tests/unit/domain/test_coverage.py`** (`is_stamped`): stamped via `{prefix}.policy`;
  unstamped (bare/empty annotations); empty-prefix fallback to `base.digest` present/absent;
  a non-default prefix.
- **Unit — `tests/unit/use_cases/test_audit.py`** (`audit_coverage` + `audit_exit_code`): a
  `FakeRegistryPort` seeded with a mix of stamped/unstamped tags across repos → assert per-image
  outcomes, the counts, and `configure_registry`/`login`-once-per-host; `--registry` restricts to
  one host; a seeded read failure on one tag → recorded error outcome + walk continues + exit ≥ 2;
  `--fail-on-uncovered` → exit 1 when `uncovered>0`, exit 0 otherwise.
- **Integration — `tests/integration/test_regctl_cli.py`** (extend): `get_annotations` against the
  `regctl` fake-bin returns the manifest annotations for a stamped vs unstamped scenario; failure
  → `RegctlError`.
- **CLI — `tests/integration/test_cli_audit.py`**: `knock audit` end-to-end against the fake-bin
  (report rendered; exit 0; `--fail-on-uncovered` flips the exit when an unstamped tag is present).

Coverage gates unchanged: ≥ 80 % global, ≥ 90 % on `knock.domain`.

## 9. Resolved decisions (carried into `writing-plans`)

- **Q1 — scope = whole-registry sweep**, not policy-anchored (blind spots are the point).
- **Q2 — "covered" = annotation stamp** (`{prefix}.policy`, or `base.digest` when prefix empty);
  attestation-coverage tier deferred.
- **Q3 — report-only by default; `--fail-on-uncovered` opt-in gate**; per-image read errors redden
  the exit independently.
- **Q4 — add `RegistryPort.get_annotations`** (one `manifest get`) rather than reuse the heavier
  `inspect`; sequential v1 walk; concurrency deferred.
