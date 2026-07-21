# Attach scan result — design (`knock attach`)

> **Status:** pre-implementation design, all forks resolved (§2, §10). Builds on the provenance
> *annotation* stamp (`knock/domain/stamp.py`) and the OCI **referrers** model. The terminal step
> after this spec is `writing-plans`.

## 1. Context & motivation

knock is a **stamper / single front door** for external OCI images. The roadmap's thesis is *"the
label is the product"* and *"coverage gates value"*: the payoff lands at incident time, when a
critical CVE drops and a consistent, portable stamp turns *"what's our blast radius?"* into one
query in the observability stack the org already runs.

A **vulnerability / EOL scan result** is a high-value provenance fact in exactly that sense: *"which
images carry a scan showing CVE-X"* or *"which images are past end-of-life"* should be one query,
not a fleet-wide re-scan. So knock should carry the scan result in its stamp.

But knock is a **stamper, not a scanner**. *Running* a scanner is a commodity — CI pipelines already
run Trivy, registries (Harbor) ship native scanners, cloud scan services exist — and embedding it
would couple knock to scanner orchestration (the tool binary, a vulnerability DB to keep fresh,
registry-pull auth, runtime-image bloat, one CLI adapter per tool) and drift past the thesis
boundary. That is the same boundary that delegates end-of-life awareness to the sibling tool
`regis` and puts runtime/fleet watching explicitly out of scope.

**Therefore: the scan runs upstream; knock ingests its result and stamps it** as a portable,
standardized OCI referrer. The scan is the commodity; the stamp is the product. Even for images
knock *rebuilds* (a fresh digest no upstream CI has seen), the orchestration `reconcile → scan →
attach` belongs to the **pipeline around** knock, not inside it.

Two mutability facts force the shape:

1. A scan result is a **mutable observation over time** — the same digest yields new findings next
   week as CVEs are disclosed — unlike immutable build provenance (*"immutable build facts on the
   artifact; mutable org facts stay out"*, `stamp.py`).
2. **Annotating an image manifest changes its digest** (`RegistryPort.annotate` returns the
   post-annotate digest).

⇒ Results live on **referrers** (attached to the subject *digest* without changing it), not baked
into the image manifest; and the operation is a **standalone, re-runnable verb**, not folded into
reconcile's build-time stamp. Re-attaching accumulates referrers — scan history is a feature.

## 2. Decisions taken (the load-bearing forks)

| Fork | Decision | Why |
|---|---|---|
| **Execution model** | **Ingest-only — knock never runs a scanner.** | Thesis (stamper, not scanner). Removes all scanner-orchestration coupling; standardized input formats make it tool-agnostic. |
| **Trigger / lifecycle** | **Standalone, re-runnable verb** (not reconcile-integrated). | Scan results are mutable observations; "by digest" is the natural input; re-attaching builds history. |
| **Storage** | **OCI referrers** on the subject digest. | Digest-stable (annotating would mutate it); discoverable via the Referrers API; accumulation = history. |
| **Artifact** | **Raw report blob in v1; signing optional & deferred.** | Additive, off by default, no blocking dependency on the approved-but-unbuilt `AttestorPort` (SLSA spec). |
| **Normalization** | **Common envelope + per-format pure mappers.** | `domain/` stays pure & ≥ 90 %. Adding a format = mapper + registry entry, no core change. Standard formats (SARIF) cover many tools at once. |
| **Verdict** | **Informational; exit 0** (gating deferred). | Matches "run + store"; gating/admission is downstream / a fast-follow. |
| **Verb name** | **`knock attach`** — flat, no subcommand for now. | Honest: knock *attaches* an externally-produced result. `scan` as a verb would misrepresent (knock does not scan). Subcommand structure deferred until a second artifact kind needs it. |

## 3. Scope (v1)

**In:**

- A new verb **`knock attach <ref> --report <file|-> [--format <fmt>]`** that ingests a scan report
  produced upstream and attaches it as a stamped OCI referrer on the image's digest.
- **Pure domain** (`domain/scan/`): the annotation envelope (`build_scan_annotations`), the
  `ScanSummary` model, **format auto-detection** (`detect_format`), and a registry of **per-format
  pure mappers** (`report bytes → ScanSummary`).
- **One format mapper in v1: SARIF.** SARIF is the standardized, portable findings format and covers
  any SARIF-emitting tool (Trivy via `trivy image --format sarif`, Grype, etc.) — leaning fully into
  the thesis's *standardized & portable*. The single-entry registry is justified by the planned
  fast-follows (Trivy-native, CycloneDX, EOL), each a drop-in mapper — not by needing two now.
- **`RegistryPort.put_referrer(...)`** + its `regctl` adapter implementation (`regctl artifact put`).
- **A `knock.attach` use case** returning a `ScanOutcome`, and a thin `cli/attach.py` command wired
  in `cli/_di.py`.
- New errors `ScanReportError`, `UnknownFormatError` (both `DomainError`, exit 1).
- **Cross-cutting sync** (§9): `workspace.dsl` (upstream-scanner external system + report ingest),
  a `docs/examples/` walkthrough, the published JSON Schema / annotation-key vocabulary. **No Trivy
  in the runtime `Dockerfile`** (explicitly noted — ingest needs no scanner binary).

**Out / deferred (by design, not omission):**

- **EOL / `regis`** as a third format mapper — a fast-follow; the registry accepts it with no core
  change (`io.knock.scan.eol.*`). This is the proof that the per-format design generalizes.
- **CycloneDX VEX** mapper — fast-follow.
- **Trivy-native JSON** mapper — fast-follow, for teams preferring Trivy's richer native output
  (it carries the vuln-DB version and the scanned image digest, which plain SARIF omits).
- **Gating** (`--fail-on <severity>`, exit non-zero) — fast-follow; v1 is informational.
- **Signing** the referrer (route through `AttestorPort`) — a designed-for seam (§11), not v1.
- **Referrer GC / retention** — v1 accumulates; pruning old scan referrers is future.
- **Multiple reports in one invocation** — v1 is one report per call; repeat the verb for more.
- **The downstream blast-radius query** — assembled in the org's observability stack from the
  referrers; not knock's job (roadmap: knock stamps, it does not watch).
- **Scan-at-import inside `reconcile`** — the pipeline orchestrates it around knock.

## 4. Architecture — hexagonal placement

The house pattern. Ingest + normalization is **pure domain** (a sibling of `stamp.py` + a registry
like `transforms/`); attaching the referrer is the one I/O step (an extension of the existing
registry adapter — the only place retry lives). **No new port for execution** (there is none).

```
cli/attach.py ─▶ use_cases/attach.py ─▶ domain/scan/        (pure)
                       │                 ├─ summary.py   ScanSummary, build_scan_annotations
                       │                 ├─ detect.py    detect_format(bytes) / resolve_format(bytes, override)
                       │                 └─ formats/     per-format mappers + registry
                       │                      base.py    ScanFormatMapper (ABC)
                       │                      sarif.py    SarifMapper          (v1)
                       │                      registry.py BUILTIN_FORMATS, Registry.get/names
                       │                      # trivy.py / cyclonedx.py — fast-follows, drop-in
                       └─ RegistryPort.put_referrer ─▶ adapters/regctl_cli.py  (regctl artifact put)
                          (deferred seam) AttestorPort ─▶ cosign   # signs the referrer iff configured
```

### Data flow

1. `knock attach <ref> --report <file|-> [--format <fmt>]`.
2. CLI reads the report **bytes** (file or stdin), mirroring how policy YAML is loaded — file I/O
   stays at the CLI/use-case boundary, never in `domain/`.
3. `registry.inspect(<ref>)` resolves the **subject digest**; the use case pins `subject = <repo>@<digest>`
   so the referrer attaches to the immutable digest even when invoked with a tag.
4. `domain/scan.detect.resolve_format(bytes, override)` → a format name (sniffed from content;
   `--format` overrides). Unknown ⇒ `UnknownFormatError`.
5. `Registry.get(format).summarize(bytes)` → `ScanSummary{tool, tool_version, facts}`. Malformed /
   unexpected schema ⇒ `ScanReportError`.
6. *(best-effort integrity, per format)* a mapper MAY expose the report's target digest; the domain
   then verifies it equals the resolved subject digest (mismatch ⇒ `ScanReportError`, guarding
   against stamping a report onto the wrong image). Plain SARIF generally omits the image digest, so
   in v1 this is a no-op and `attach` trusts the operator's report/ref pairing; the check activates
   when a digest-carrying mapper (Trivy-native) lands.
7. `build_scan_annotations(summary, prefix=…, subject_digest=…, format=…, timestamp=clock.now())`
   → the `io.knock.scan.*` annotation map.
8. `registry.put_referrer(subject, artifact_type=SCAN_RESULT_ARTIFACT_TYPE,
   media_type=<native report media type>, blob=bytes, annotations=…)` → referrer digest.
9. Return `ScanOutcome`; the CLI renders it (human summary or `--output json`); **exit 0**.

### The referrer

- **`artifactType` = `application/vnd.knock.scan.result.v1`** — a stable filter key so consumers can
  list referrers of an image filtered to knock scan results (the query path). Versioned, generic,
  no org reference.
- **Blob (layer) media type = the report's native type** — `application/sarif+json` in v1; other
  media types (e.g. `application/vnd.aquasec.trivy.report.v1+json`) arrive with their mappers. The
  blob is the **untouched** upstream report.
- **Annotations on the referrer manifest** carry the cheap, queryable summary (below). The subject
  image's own manifest and digest are **never modified**.

### Annotation key scheme (on the referrer manifest)

Honors `KNOCK_LABEL_PREFIX` (default `io.knock`); empty prefix ⇒ the report blob is still attached
but no `io.knock.scan.*` summary is written — consistent with `stamp.py`'s "empty prefix ⇒ no
labels".

**Common (the envelope — same shape for every format):**

| Key | Example | Source |
|---|---|---|
| `{prefix}.scan.tool` | `trivy` | the report (`runs[].tool.driver.name` for SARIF) |
| `{prefix}.scan.tool.version` | `0.50.1` | the report, where present |
| `{prefix}.scan.format` | `sarif` \| `trivy` | the resolved ingest format |
| `{prefix}.scan.timestamp` | `2026-06-12T…Z` | `clock.now()` (when knock attached it) |
| `{prefix}.scan.subject` | `sha256:…` | the resolved subject digest |

**Per-finding-type facts (the mapper's contribution — namespaced by *finding type*, not by tool):**

- vulnerability: `{prefix}.scan.vuln.critical`, `.high`, `.medium`, `.low`, `.unknown`. The SARIF
  mapper buckets findings by the `security-severity` property (CVSS 0–10 → critical ≥ 9.0 / high ≥
  7.0 / medium ≥ 4.0 / low < 4.0) where present, falling back to the SARIF `level`
  (error/warning/note). `{prefix}.scan.db.version` and `.fixable` are emitted only by formats that
  carry them (Trivy-native; plain SARIF omits both).
- *(deferred)* end-of-life: `{prefix}.scan.eol.status`, `.date`, `.cycle`.

Namespacing by **finding type** (`vuln.*`), not by tool, is deliberate: `io.knock.scan.vuln.critical`
is tool-agnostic, so a blast-radius query works whether Trivy or Grype produced it. The tool is a
separate fact (`scan.tool`).

## 5. CLI surface

```
knock attach <ref> --report <path|->  [--format sarif]  [--output text|json]
```

- `<ref>` — image reference (tag or digest); resolved to a digest before attaching.
- `--report` — path to the upstream scan report, or `-` for stdin.
- `--format` — optional override of auto-detection.
- `--output` — `text` (default; a short human summary: tool, severity counts, referrer digest) or
  `json` (the full `ScanOutcome`, for CI).
- **Exit codes** via the existing `exit_code_for` mapping: `DomainError` 1 (bad report / unknown
  format), `AdapterError` 2 (`regctl` failure), `ConfigError` 3, else 4. Success is **0** regardless
  of findings (informational).

No `Reporter` port is used — that protocol is reconcile-specific (`operation_applied`,
`OperationEvent`, `Counts`). The use case returns a `ScanOutcome{subject_digest, referrer_digest,
tool, tool_version, format, facts, timestamp}` that the thin CLI renders.

## 6. Error model (`knock/errors.py`)

| New error | Base | Exit | Raised when |
|---|---|---|---|
| `ScanReportError` | `DomainError` | 1 | a mapper cannot parse the report, hits an unexpected schema, or detects a subject-digest mismatch |
| `UnknownFormatError` | `DomainError` | 1 | format detection fails and no valid `--format` was given (mirrors `PolicyValidationError` for unknown transform steps) |

No new `AdapterError` subclass is needed: there is **no scanner subprocess**; the only I/O failure
mode is `regctl artifact put`, already covered by the existing `RegctlError`.

## 7. Config

**No new config block in v1.** Format is auto-detected (with `--format` as an explicit override),
and registry access (host, credentials, TLS, CA) reuses the existing `RegistryConfig` consumed by
the `regctl` adapter. If a later need appears (a default format, signing settings), a `ScanSettings`
sub-block (`KNOCK_SCAN_*`, own `env_prefix`, JSON-Schema-published) is the additive home — but YAGNI
keeps it out of v1.

## 8. Testing

- **Unit / domain (≥ 90 %):**
  - `build_scan_annotations` — common keys present; per-type facts mapped; empty prefix ⇒ no summary.
  - `detect_format` — recognizes SARIF (`$schema` / `version` / `runs`); unrecognized ⇒
    `UnknownFormatError`; `--format` override path. (Sniffing generalizes as mappers are added.)
  - `SarifMapper.summarize` — over fixtures: with findings (security-severity bucketing + `level`
    fallback), with none, malformed ⇒ `ScanReportError`, tool/version extraction from
    `runs[].tool.driver`.
  - format registry `get` / unknown name.
- **Fakes:** add a journaling `put_referrer` to `tests/fakes/registry.py` (e.g.
  `calls.put_referrers`) so the use-case test asserts *"`put_referrer` called with `subject=@<digest>`,
  `artifactType=application/vnd.knock.scan.result.v1`, annotations including
  `io.knock.scan.vuln.critical`"*. No scanner fake is needed (no scanner port).
- **Integration:** add a `artifact put` scenario to the existing `tests/fake-bins/regctl` (branch on
  `FAKE_REGCTL_SCENARIO`, append argv to the log) and assert the exact `regctl` argv. **No Trivy
  fake-bin** — knock runs no scanner.
- Strict TDD: failing test → red → minimal impl → green → commit, one behavior per commit.

## 9. Cross-cutting sync obligations (CLAUDE.md — same change, not follow-ups)

- **C4 / `docs/architecture/workspace.dsl`** — add, at context level, an external system *"Upstream
  vulnerability scanner (CI / registry-native / scan service)"* that **produces the report knock
  ingests**, and the integration *knock → registry (attach referrer)*. Re-render + update the
  rationale in `docs/architecture/README.md`. (Note the direction of the new edge: the scanner feeds
  knock an artifact; knock does **not** call the scanner.)
- **`docs/examples/`** — add a `knock attach` walkthrough: a sample SARIF/Trivy report, the command,
  and the resulting referrer + `io.knock.scan.*` annotations. Mark *"requires the attach path"*
  until it lands.
- **Runtime image (`Dockerfile`)** — **nothing to add.** Explicitly recorded: ingest needs no
  scanner binary, so the runtime image stays skopeo + buildctl + git (+ cosign per the SLSA spec).
- **JSON Schema** — publish the derived annotation-key vocabulary: the common envelope keys plus
  each mapper's declared `fact_keys`, so consumers/editors know the `io.knock.scan.*` contract.

## 10. Resolved decisions & deferred fast-follows

All forks in §2 are settled; the plan starts from them, not from options. Carried decisions worth
restating:

- **Q (verb name) — `knock attach`, flat.** No subcommand now; if a second artifact kind appears
  (SBOM, VEX, EOL), revisit a `knock attach <kind>` grouping then, not pre-emptively.
- **Q (format set v1) — SARIF only.** Trivy-native JSON, CycloneDX VEX, and `regis`/EOL are
  fast-follows, each a new mapper + registry entry with **zero** change to `domain/scan/summary.py`,
  the use case, the port, or the CLI — the design's central claim. Trivy users emit SARIF via
  `trivy image --format sarif`, so Trivy is already covered functionally in v1.
- **Q (re-attach semantics) — accumulate.** Each `attach` produces a distinct referrer (its
  `timestamp` and report content disambiguate); history is a feature, retention is future.
- **Q (config) — none in v1.** Auto-detect + `--format`; registry config reused.

## 11. Future seam — signing (deferred, designed-for)

The use case accepts `attestor: AttestorPort | None = None`. v1 wires `None` ⇒ a plain
`put_referrer` of the raw report. When the `AttestorPort` lands (SLSA spec) and a future
`KNOCK_SCAN_SIGN`-style switch is set, the same report is signed (DSSE) and attached via the
attestor instead of / in addition to the plain put — purely additive, no rework. This mirrors the
SLSA spec's *"empty signer ⇒ no attestation"* and keeps the verifiable-provenance story open without
blocking v1 on unbuilt work.
