# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What houba is

houba is **not an image mirror** (that miscategorization is what `skopeo sync` / Harbor replication do — byte-for-byte copy). It is a **stamper / single front door** for external container images: it rebuilds them through a hardening policy (internal CAs, internal package mirrors) and stamps them with standardized, portable provenance so that, when a CVE drops, blast-radius becomes one query in the org's observability stack. Read [docs/roadmap.md](docs/roadmap.md) before doing product or architecture work — it carries the live product thesis ("the label is the product", "coverage gates value") and the re-scoped Phase C ordering, which deliberately overrides the inherited Groovy use-case order. [docs/design.md](docs/design.md) has the architecture rationale.

houba and `regis` (which carries the removed EOL feature) are sibling tools sharing the same engineering conventions.

Current maturity: Phase A + B delivered (foundations, full `domain/`, all I/O adapters). The use-case layer (`use_cases/`) and the derive-and-stamp engine are **not yet built** — that is Phase C.

## Commands

Everything runs through `uv` (the project manager — non-negotiable, no pip/poetry fallback).

```bash
uv sync                          # install deps into .venv (do NOT rm -rf .venv; recreate via uv sync if needed)
uv run pytest                    # full suite
uv run pytest tests/unit/domain/test_tag_filter.py::test_exclude_regex_filters -v   # single test
uv run pytest tests/integration -v                                                  # integration only
uv run ruff check .              # lint
uv run ruff format .             # format (use --check in CI)
uv run mypy houba                # strict type check
docker build -t houba:dev .      # runtime image (bundles skopeo + buildctl + git; ~5 min, pulls 2 upstream images)
```

Coverage gates (enforced in CI, must stay green): **≥ 80 % global, ≥ 90 % on `houba.domain`**.

```bash
uv run pytest --cov=houba --cov-report=term-missing --cov-fail-under=80
uv run pytest tests/unit/domain --cov=houba.domain --cov-fail-under=90
```

## Architecture — hexagonal, and the rules are load-bearing

The layering is the whole point of the project (it is an extraction from a Groovy Jenkins shared library, done specifically to decouple business logic from the orchestrator). Violating the layer rules defeats the reason houba exists.

```
cli/ (Typer, thin)  →  use_cases/ (Phase C, not built)  →  domain/ (pure)
                                  ↘ ports/ (typing.Protocol)  ←  adapters/ (I/O)
```

- **`domain/`** — pure functions on dataclasses/pydantic models. **No `httpx`, no `requests`, no `subprocess`, no `os.environ`, no file I/O, no retry logic.** Coverage ≥ 90 %. The core logic lives in `tag_filter.compute_tags_to_import` (pure function: `(src_tags, properties, harbor_state, now) → import/update/delete sets`, including the 7-day digest-stability window). `clock` is a port so `now()` is injectable.
- **`ports/`** — `typing.Protocol` interfaces only. **Must never import from `houba.adapters.*`.** Each port has a frozen-dataclass data model alongside it.
- **`adapters/`** — concrete I/O. HTTP adapters (`harbor_http`, `gitlab_http`, `teams_webhook`) use `httpx` + `tenacity`; CLI-tool adapters (`skopeo_cli`, `buildkit_cli`, `git_cli`) wrap `subprocess`. **Retry lives only here** — a private `_Transient` subclass of the relevant error triggers tenacity retry on 5xx/network; non-transient failures raise immediately.
- **`cli/`** — parse args → build composition root (`cli/_di.py`) → call use case → map exception to exit code. `_di.py` is excluded from coverage (it is wiring).
- **`config.py`** — the **only** place `os.environ` is read (via Pydantic Settings). All vars are `HOUBA_*`. Sub-blocks (`HarborSettings`, `GitLabSettings`) each set their own `env_prefix` so the contract stays single-underscore (`HOUBA_HARBOR_URL`, not `HOUBA_HARBOR__URL`). Any other code needing config takes it as an explicit parameter.

When adding a new external dependency, the pattern is always: **port (Protocol + dataclass) → fake (in `tests/fakes/`) → adapter (in `houba/adapters/`) → wire into `cli/_di.py`**.

## Errors & exit codes

`houba/errors.py` defines the `HoubaError` hierarchy. `exit_code_for(exc)` walks the MRO: `DomainError`→1, `AdapterError`→2, `ConfigError`→3, `InternalError`→4; anything unrelated to `HoubaError` →4. Pydantic `ValidationError` maps to 3 (config). When adding an error, hang it under the correct branch — the exit code is derived from the base class, not declared per-class.

## Testing conventions

- **Unit tests** (`tests/unit/`) cover `domain/` (pure) and the fakes. Ports are faked in-memory in `tests/fakes/` — write fakes that **journal calls** (e.g. `FakeHarborPort.calls.deleted_artifacts`) so use-case tests can assert "X was called", and seed read data via constructor dicts.
- **Integration tests** (`tests/integration/`) exercise adapters in isolation: **`respx`** for HTTP adapters, **fake-bin shell scripts** for CLI-tool adapters. The `fake_bin_path` fixture (in `tests/conftest.py`) puts `tests/fake-bins/` at the head of `PATH`; those scripts branch on `FAKE_<TOOL>_SCENARIO` and append their argv to `FAKE_<TOOL>_LOG` so tests can assert on the exact arguments. New CLI-tool adapter ⇒ new fake-bin (and `chmod +x` it).
- Strict TDD: failing test → run it red → minimal impl → green → commit, one behavior per commit.

## Craftsmanship & engineering standards

**Spec-driven, composable workflows.** Use Claude Code skills as stacked building blocks: the Superpowers skills supply engineering discipline (`brainstorming` → `writing-plans` → `subagent-driven-development` → `test-driven-development` → `finishing-a-development-branch`). **Plans never land on `main`** — `docs/superpowers/plans/` is gitignored, so a plan is a local working artifact for the duration of its feature branch only (never committed, never merged). Specs *do* persist, under `docs/superpowers/specs/`. When a recurring task lacks a skill, author one rather than re-improvising.

**Architecture philosophy.**
- Prefer declarative specs over imperative code paths — the product policy is a Pydantic `properties.yml` schema; extend that schema before adding ad-hoc Python branching.
- **JSON Schema, systematically, wherever a declarative contract exists** (config, the policy schema, structured payloads). Derive it from the Pydantic models (`model_json_schema()`) — never hand-write it; publish it so policy files get editor/CI validation, and validate inputs against it. Extend the schema before adding imperative parsing.
- Choose established libraries over building from scratch (httpx, tenacity, pydantic, typer, structlog).
- Type hints required for all new functions and classes; `domain/` and `ports/` stay fully `mypy --strict`. `adapters.*` and `cli.*` are intentionally laxer (`disallow_untyped_calls = false`) because they touch untyped I/O libraries — do not relax `domain/` to match.

## Git workflow & commits

- Feature/bug branches flow to a PR against `main`; never start implementation directly on `main`/`master` without explicit consent.
- **Always rebase feature branches on the latest `main` — never merge `main` back into them.**
- **Conventional Commits**, and **scopes are mandatory**. Scope is the layer or area touched: `domain`, `ports`, `adapters`, `cli`, `config`, `errors`, `image` (Dockerfile), `ci`, `deps`, `docs`, `tests`. Example: `feat(adapters): HarborHttpAdapter write methods`.
- Favor the functional aspect in the subject; technical detail goes in the body.
- End commit messages with the trailer `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Gotchas

- **Harbor double-encodes repository names** in URL paths (`foo/bar` → `foo%252Fbar`). This is an intentional reproduction of upstream Harbor behavior — see `_encode_repo` in `harbor_http.py`. Don't "fix" it.
- **OCI labels** are built by `domain/labels.build_labels(prefix=...)`. The prefix comes from `HOUBA_LABEL_PREFIX` (default `io.houba`); empty prefix ⇒ no labels. Per the roadmap, the standard provenance facts should migrate to OCI-standard annotation keys (`org.opencontainers.image.*`), reserving `io.houba.*` only for transformation lineage — keep that direction in mind when touching this module.
- This is the public open-source repo: **no SNCF / `hub2hub` / `h2h` references** anywhere in code, config, or docs. The org-specific hardening scripts are meant to become *configuration* of generic primitives, never hardcoded behavior.
