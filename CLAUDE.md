# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What houba is

houba is **not an image mirror** (that miscategorization is what `skopeo sync` / Harbor replication do — byte-for-byte copy). It is a **stamper / single front door** for external container images: it rebuilds them through a hardening policy (internal CAs, internal package mirrors) and stamps them with standardized, portable provenance so that, when a CVE drops, blast-radius becomes one query in the org's observability stack. Read [docs/roadmap.md](docs/roadmap.md) before doing product or architecture work — it carries the live product thesis ("the label is the product", "coverage gates value") and the re-scoped Phase C ordering, which deliberately overrides the inherited Groovy use-case order. [docs/architecture/design.md](docs/architecture/design.md) has the architecture rationale.

houba and `regis` (which carries the removed EOL feature) are sibling tools sharing the same engineering conventions.

Current maturity: the full hexagon is delivered (released 0.3.0, plus merged PRs #24–#32). The use-case layer (`houba/use_cases/` — `loader`, the `reconcile_policies` orchestrator, `report`, and the `audit` coverage walk), **both** the copy path and the rebuild / derive-and-stamp path, the pluggable transform engine (`houba/domain/transforms/`), and the OCI-standard + `io.houba.*` provenance stamp (`houba/domain/stamp.py`) are all built. The roadmap's remaining items are refinements (e.g. freezing the provenance schema, a coverage audit), not missing foundations.

## Commands

Everything runs through `uv` (the project manager — non-negotiable, no pip/poetry fallback).

```bash
uv sync                          # install deps into .venv (do NOT rm -rf .venv; recreate via uv sync if needed)
uv run pytest                    # full suite
uv run pytest tests/unit/domain/test_selection.py::test_exclude_regex_drops_matches -v   # single test
uv run pytest tests/integration -v                                                       # integration only
uv run ruff check .              # lint
uv run ruff format .             # format (use --check in CI)
uv run mypy houba                # strict type check
docker build -t houba:dev .      # runtime image (bundles regctl + buildctl; ~5 min, pulls 2 upstream images)
```

Coverage gates (enforced in CI, must stay green): **≥ 80 % global, ≥ 90 % on `houba.domain`**.

```bash
uv run pytest --cov=houba --cov-report=term-missing --cov-fail-under=80
uv run pytest tests/unit/domain --cov=houba.domain --cov-fail-under=90
```

## Architecture — hexagonal, and the rules are load-bearing

The layering is the whole point of the project (it is an extraction from a Groovy Jenkins shared library, done specifically to decouple business logic from the orchestrator). Violating the layer rules defeats the reason houba exists.

```
cli/ (Typer, thin)  →  use_cases/ (orchestration)  →  domain/ (pure)
                                  ↘ ports/ (typing.Protocol)  ←  adapters/ (I/O)
```

- **`domain/`** — pure functions on dataclasses/pydantic models. **No `httpx`, no `requests`, no `subprocess`, no `os.environ`, no file I/O, no retry logic.** Coverage ≥ 90 %. The tag logic is split across two pure modules: `domain/selection.py` (`select_tags` — applies the include/exclude regex and semver-only filtering to the upstream tag list) and `domain/reconcile.py` (`reconcile_variant` / `reconcile_import` — turns source vs. mirror state into the import/update/delete plan, including the 7-day digest-stability window: `DEFAULT_GRACE = timedelta(days=7)`). `clock` is a port so `now()` is injectable.
- **`ports/`** — `typing.Protocol` interfaces only. **Must never import from `houba.adapters.*`.** Each port has a frozen-dataclass data model alongside it. The ports are `RegistryPort` (with `ImageInfo`), `ImageBuilderPort` (with `BuildRequest`), `Reporter` (with `Counts` / `ErrorInfo` / `OperationEvent`), `ClockPort`, `AttestorPort` (with `AttestationRef`), and `UsageOraclePort` (with `UsageQuery` / `UsageObservation`).
- **`adapters/`** — concrete I/O. **There is no HTTP layer** — every adapter is a `subprocess` wrapper or stdlib: `regctl_cli` (`RegctlAdapter`, drives `regctl` for all registry operations — list / inspect / copy / annotate / delete / login / get-annotations — and replaces both skopeo and the old Harbor HTTP adapter), `buildkit_cli` (`BuildkitAdapter`, drives `buildctl`), `structlog_reporter` (`StructlogReporter`, emits structured events to stderr), `system_clock` (`SystemClock`), `cosign_cli` (`CosignAdapter`, drives `cosign` to sign in-toto attestations — keyless / kms / key), and `command_usage` (`CommandUsageAdapter`, shells out to `HOUBA_USAGE_ORACLE_CMD` — the prod-usage oracle `purge` consults). **There is no retry logic anywhere** — an adapter raises its own error type (`RegctlError`, `BuildkitError`, `CosignError`, `UsageOracleError`) on failure.
- **`cli/`** — parse args → build composition root (`cli/_di.py`) → call use case → map exception to exit code. `_di.py` is excluded from coverage (it is wiring).
- **`config.py`** — the **only** place `os.environ` is read (via Pydantic Settings). All vars are `HOUBA_*`. There is a single `Settings` class (`env_prefix="HOUBA_"`); nested config is carried as **JSON inside a single env var**, not as separate env prefixes. The registry roster is `HOUBA_REGISTRIES`, a JSON object parsed into `dict[str, RegistryConfig]`; likewise `HOUBA_TRANSFORM_CA_CERTS` (→ `dict[str, CACertSource]`) and `HOUBA_TRANSFORM_PACKAGE_MIRRORS` (→ `dict[str, PackageMirror]`). Other key vars: `HOUBA_LABEL_PREFIX`, `HOUBA_BUILD_PLATFORM`, `HOUBA_WORK_DIR`, `HOUBA_LOG_FORMAT` / `HOUBA_LOG_LEVEL`, `HOUBA_DRY_RUN_TAGS` / `HOUBA_DRY_RUN_DELETIONS`. Any other code needing config takes it as an explicit parameter.

When adding a new external dependency, the pattern is always: **port (Protocol + dataclass) → fake (in `tests/fakes/`) → adapter (in `houba/adapters/`) → wire into `cli/_di.py`**.

## Errors & exit codes

`houba/errors.py` defines the `HoubaError` hierarchy. `exit_code_for(exc)` walks the MRO: `DomainError`→1, `AdapterError`→2, `ConfigError`→3, `InternalError`→4; anything unrelated to `HoubaError` →4. The concrete leaves are `PolicyValidationError` / `ScanReportError` / `UnknownFormatError` (under `DomainError`) and `RegctlError` / `BuildkitError` / `CosignError` / `UsageOracleError` (under `AdapterError`). Pydantic `ValidationError` (and `pydantic_settings` `SettingsError`) are caught in `cli/main.py` and mapped to 3 (config). When adding an error, hang it under the correct branch — the exit code is derived from the base class, not declared per-class.

## Testing conventions

- **Unit tests** (`tests/unit/`) cover `domain/` (pure) and the fakes. Ports are faked in-memory in `tests/fakes/` — one fake per port (`registry`, `image_builder`, `reporter`, `clock`, `attestor`, `usage_oracle`). The fakes **journal calls** (e.g. `FakeRegistryPort.copied` / `.deleted` / `.annotated`) so use-case tests can assert "X was called", and seed read data via constructor args.
- **Integration tests** (`tests/integration/`) exercise the CLI-tool adapters in isolation with **fake-bin shell scripts** (there are no HTTP adapters). The `fake_bin_path` fixture (in `tests/conftest.py`) puts `tests/fake-bins/` (currently `regctl`, `buildctl`, `cosign`, `oracle`) at the head of `PATH`; those scripts branch on `FAKE_<TOOL>_SCENARIO` and append their argv to `FAKE_<TOOL>_LOG` so tests can assert on the exact arguments. New CLI-tool adapter ⇒ new fake-bin (and `chmod +x` it).
- Strict TDD: failing test → run it red → minimal impl → green → commit, one behavior per commit.

## Craftsmanship & engineering standards

**Spec-driven, composable workflows.** Use Claude Code skills as stacked building blocks: the Superpowers skills supply engineering discipline (`brainstorming` → `writing-plans` → `subagent-driven-development` → `test-driven-development` → `finishing-a-development-branch`). **Plans never land on `main`** — `docs/superpowers/plans/` is gitignored, so a plan is a local working artifact for the duration of its feature branch only (never committed, never merged). Specs *do* persist, under `docs/superpowers/specs/`. When a recurring task lacks a skill, author one rather than re-improvising.

**Architecture docs stay in sync with specs (C4).** The C4 model lives in `docs/architecture/workspace.dsl` (Structurizr DSL) — one model with five structural views (**System Landscape**, **System Context**, **Container**, **Hexagon** — a synthetic component overview —, **Component**) plus one **Deployment** view per worked example and a production blueprint (render + rationale in `docs/architecture/README.md`; the Mermaid exports are committed under `docs/architecture/_export/` and must be refreshed when the DSL changes). It is the source of truth for the context and landscape levels; the **Container**, **Hexagon**, and **Component** views additionally document houba's internal structure — the hexagonal layers, ports, and adapters — as built. Whenever a spec adds or changes an **actor**, an **external system**, or an **integration** — anything visible at context or landscape level — update `workspace.dsl` **in the same change as the spec**; likewise, when the code's internal structure shifts (a new port/adapter pair, a new domain concern, a changed layer boundary), keep the **Container**/**Component** views in step. A spec under `docs/superpowers/specs/` that shifts the architecture is not complete until the C4 model reflects it, and each spec is mirrored as a thin ADR under `docs/architecture/decisions/` (linking to the full spec) — the workspace embeds `docs/architecture/design.md` as its Documentation pane and those ADRs as its Decisions pane. The model must never drift from the specs.

**Examples stay in sync with specs.** When a spec designs or changes a user-facing feature, update `docs/examples/` **in the same change** — add or revise an example (a `MirrorPolicy` + the README walkthrough) demonstrating it. If the feature isn't implemented yet, add the example marked as such: it documents the design now and becomes runnable when the feature lands. Examples must never drift from the specs.

**Architecture philosophy.**
- Prefer declarative specs over imperative code paths — the product policy is the Pydantic `MirrorPolicy` schema; extend that schema before adding ad-hoc Python branching.
- **JSON Schema, systematically, wherever a declarative contract exists** (config, the policy schema, structured payloads). Derive it from the Pydantic models (`model_json_schema()`) — never hand-write it; publish it so policy files get editor/CI validation, and validate inputs against it. Extend the schema before adding imperative parsing.
- Choose established libraries over building from scratch (pydantic, pydantic-settings, typer, structlog, pyyaml).
- Type hints required for all new functions and classes; `domain/` and `ports/` stay fully `mypy --strict`. `adapters.*` and `cli.*` are intentionally laxer (`disallow_untyped_calls = false`) because they touch untyped I/O libraries — do not relax `domain/` to match.

## Git workflow & commits

- Feature/bug branches flow to a PR against `main`; never start implementation directly on `main`/`master` without explicit consent.
- **Always rebase feature branches on the latest `main` — never merge `main` back into them.**
- **Conventional Commits**, and **scopes are mandatory**. Scope is the layer or area touched: `domain`, `ports`, `adapters`, `cli`, `config`, `errors`, `image` (Dockerfile), `ci`, `deps`, `docs`, `tests`. Example: `feat(adapters): RegctlAdapter copy with provenance annotations`.
- Favor the functional aspect in the subject; technical detail goes in the body.
- End commit messages with the trailer `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Gotchas

- **OCI provenance** is stamped by `domain/stamp.build_stamp_annotations(prefix=...)`. The immutable build facts use **OCI-standard annotation keys** (`org.opencontainers.image.source` / `.revision` / `.base.name` / `.base.digest` / `.created`) so any scanner reads them for free; `{prefix}.*` carries the houba-specific facts (artifact type, the three-level `policy` / `import` / `variant` identity, `owner.team`, and `transform.steps` / `transform.version` lineage). The prefix comes from `HOUBA_LABEL_PREFIX` (default `io.houba`); an empty prefix ⇒ only the OCI-standard keys are emitted. No location fact is ever stamped — the same digest can live in many registries.
- This is the public open-source repo: **keep it generic — no organization-specific references** (internal hostnames, registries, credentials, legacy product names) anywhere in code, config, or docs. Org-specific hardening must become *configuration* of generic primitives, never hardcoded behavior.
