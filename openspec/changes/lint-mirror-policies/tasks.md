# Plan — lint-mirror-policies

Implements `specs/policy-lint/spec.md` as decided in `design.md` (D1–D9). Strict TDD throughout: write
the failing test, run it red, write the minimal code, run it green, then commit. Fast loop is
`uv run pytest <path> -v --no-cov`. Commits follow Conventional Commits with a mandatory scope.

## Plan de documentation

| Chemin | Quadrant | Destinataire | Geste |
| --- | --- | --- | --- |
| `docs/reference/command-line-interface.md` | référence | intégrateur de la CI d'un dépôt de politiques | modifiée (générée par `make reference`) |
| `docs/reference/schemas/lint-report.schema.json` et `lint-report.md` | référence | outil qui consomme le rapport de lint | créées (générées par `make reference`) |
| `docs/how-to/lint-policies-in-ci.md` | guide | mainteneur d'un dépôt de politiques qui veut bloquer un merge cassé | créée |
| `docs/how-to/README.md` | guide | lecteur qui cherche un guide | modifiée (une entrée) |
| `docs/explanation/how-it-works.md` | explication | contributeur qui découvre l'architecture | modifiée (verbe `lint` et module `use_cases/lint` dans la carte des modules) |
| `docs/roadmap.md` | explication | contributeur qui oriente le produit | modifiée (liste des verbes) |
| `CLAUDE.md` | — | agent de code travaillant dans knock | modifiée (liste des verbes, chargeur collecteur) |
| `docs/architecture/decisions/0058-knock-lint-offline-policy-validation.md` | explication | contributeur qui revisite la décision | créée (pendant ce découpage) |

## ADR

- ADR review completed for this change. All ADRs in `docs/architecture/decisions/` were read at the
  status line, and the supersession links were followed (0008 and 0022 are superseded by 0023, 0027
  by 0039, and 0018, 0029, 0037 and 0048 in part). knock has no top-level `adr/` folder: its ADRs live
  in `docs/architecture/decisions/`, and the new one follows that convention. `docs/adr/SDR-*` are the
  inherited method ADRs, read during the proposal detection.
- Read in body: 0001 (the Pydantic model is the single source of truth and the schema is derived; lint
  reuses the model), 0003 (two-stream output and published report; `LintReport` follows it), 0014
  (read-only reporting verb with a versioned report; the closest precedent).
- Created: [0058 — `knock lint`, offline validation of a policy tree](../../../docs/architecture/decisions/0058-knock-lint-offline-policy-validation.md).

## 1. Located policy errors (D2)

- [x] 1.1 Branch from the latest `main`: `git switch main && git pull --rebase && git switch -c feat/lint-mirror-policies`
- [x] 1.2 `knock/errors.py`: give `PolicyValidationError` an `issues: list[tuple[tuple[str | int, ...], str]]` attribute, defaulting to `[((), str(message))]`, set through `__init__(self, message: str, issues: ... | None = None)`; its `str()` stays the message. Test in `tests/unit/test_errors.py`: `PolicyValidationError("x").issues == [((), "x")]`, and `exit_code_for` still returns 1
- [x] 1.3 `knock/domain/mirror_policy.py:parse_mirror_policy`: on `ValidationError`, pass `issues=[(tuple(err["loc"]), err["msg"]) for err in e.errors()]`. Test in `tests/unit/domain/test_mirror_policy.py`: a policy with an unknown field under `spec.imports[0]` raises with an issue whose `loc` starts with `("spec", "imports", 0)`
- [x] 1.4 Run `uv run pytest tests/unit -q --no-cov`; expected: all pass, no change to any existing message assertion
- [x] 1.5 Commit: `feat(policy): locate each policy validation issue`

## 2. Collecting loader (D1)

- [x] 2.1 `knock/use_cases/loader.py`: add frozen dataclasses `LoadedPolicy(path: str, policy: MirrorPolicy)` and `LoadIssue(path: str, loc: tuple[str | int, ...], message: str)`, and `load_policy_files(directory: Path) -> tuple[list[LoadedPolicy], list[LoadIssue]]`. It uses the same walk as today (`sorted(directory.rglob("*"))`, suffix `.yml`/`.yaml`, `is_file()`), with `path` relative to `directory` in POSIX form, and records one `LoadIssue` per `PolicyValidationError.issues` entry instead of raising
- [x] 2.2 Rewrite `load_policy_dir` on top of `load_policy_files`: raise `PolicyValidationError(f"{directory / first.path}: {first.message}")` on the first issue, else return the policies. Verify the three existing tests in `tests/unit/use_cases/test_loader.py` pass unchanged
- [x] 2.3 Tests in `tests/unit/use_cases/test_loader.py`: two broken files (`a.yaml` with an unknown field, `b.yaml` invalid YAML) give issues for both paths, sorted, and no policy; `notes.txt` is ignored; a valid file next to a broken one is returned as a `LoadedPolicy`
- [x] 2.4 Run `uv run pytest tests/unit/use_cases/test_loader.py tests/integration/test_cli_reconcile.py -v --no-cov`; expected: all pass
- [x] 2.5 Commit: `feat(policy): load a policy tree collecting every error`

## 3. Offline alias overlaps (D3)

- [ ] 3.1 `knock/domain/collision.py`: add `AliasClaim(dest_repo: str, alias: str, origin: str)`, `Overlap(dest_repo: str, alias: str, origins: tuple[str, str], certain: bool)` and `find_alias_overlaps(claims: list[AliasClaim]) -> list[Overlap]`. A claim is literal when `"{" not in alias`. Two literal claims with the same `(dest_repo, alias)` give a certain overlap. Two template claims on the same `dest_repo`, from different origins, give a possible overlap (`alias` holds the two templates joined by ` / `). Leave `detect_alias_collisions` untouched
- [ ] 3.2 Tests in `tests/unit/domain/test_collision.py`: same `latest` into one repo is certain; `latest` into two repos gives nothing; `{major}` twice into one repo is possible; `{major}` and `1` give nothing (documented limit, D3); the same origin claiming twice gives nothing
- [ ] 3.3 Run `uv run pytest tests/unit/domain/test_collision.py -v --no-cov`; expected: all pass
- [ ] 3.4 Commit: `feat(policy): detect alias overlaps knowable without upstream tags`

## 4. Lint use case and report (D4, D5, D7, D8, D9)

- [ ] 4.1 `knock/use_cases/lint.py`: Pydantic `Finding(level: Literal["N1","N2","N3"], path: str, loc: list[str | int] | None, message: str, related: list[str] = [])`, `Skipped(level: str, reason: str)` and `LintReport(api_version="knock.io/v1alpha1", kind="LintReport", errors, warnings, skipped)` with the same camelCase envelope convention as `CoverageReport` (`knock/use_cases/audit.py`), plus `lint_report_json_schema()` and `lint_exit_code(report) -> int` (0 without errors, else 1)
- [ ] 4.2 `lint_policies(directory: Path, *, roster: dict[str, RegistryConfig], ca_certs: dict[str, CACertSource], package_mirrors: dict[str, PackageMirror]) -> LintReport`. If no `.yml`/`.yaml` file exists, add one N1 error `no policy file found under <dir>`. Otherwise map every `LoadIssue` to an N1 error
- [ ] 4.3 N2 steps (D9): for each loaded policy, each `resolve_imports(policy.spec)` entry and each of its variants, validate every `transform` step with `DEFAULT_REGISTRY.get(step.name).params_model` and every `remediate` step with `.policy_model()`, as `_resolve_transform` / `_resolve_remediation` do in `knock/use_cases/reconcile_registry.py`; each `PolicyValidationError` or `ValidationError` becomes an N2 error naming the import and step. Collect the `resource_refs` for N3
- [ ] 4.4 N2 aliases (D3, D4): build one `AliasClaim` per `(destination, alias template)` of each resolved import (registry source: `tags.aliases`; git source: `source.ref`), with `dest_repo` = resolved host path when `roster` is non-empty, else `f"{dest.registry or '<default>'}/{dest.project}/{dest.repository}"`, and `origin` = `f"{path}#{import name}"`. Certain overlaps are N2 errors and possible ones are N2 warnings, both with `related` holding the other path
- [ ] 4.5 N3 (D5): when `roster` is empty, append `Skipped(level="N3", reason="KNOCK_REGISTRIES not set")`. Otherwise call `resolve_registry` for each destination, `resolve_ca_certs` and `resolve_mirror` for each collected `ResourceRef`, and read each `CACertSource.path`; each `ConfigError` or `OSError` becomes an N3 error on the policy file
- [ ] 4.6 Tests in `tests/unit/use_cases/test_lint.py`, one per spec scenario, over `tmp_path` trees: valid tree gives 0 errors; two broken files give two N1 errors; empty dir gives the "no policy" error; `injectCa` gives an N2 error; a bad `injectCA` param gives an N2 error; same `latest` into one repo gives an error naming both files; `{major}` overlap gives a warning only; unknown registry `quay` with roster `{harbor}` gives an N3 error; no roster gives `skipped == [N3]` and no N3 error; an unreadable CA path gives an N3 error; `lint_exit_code` is 0 for warnings only and 1 with an error
- [ ] 4.7 Run `uv run pytest tests/unit/use_cases/test_lint.py -v --no-cov`; expected: all pass
- [ ] 4.8 Commit: `feat(lint): validate a policy tree offline and report every finding`

## 5. CLI verb (D5, D6)

- [ ] 5.1 `knock/cli/lint.py`: `lint(directory: Annotated[Path, typer.Argument(help=...)])`. If `directory` does not exist or is not a directory, raise `ConfigError` (exit 3). Build `Settings()` only, never `build_container()`, then `configure(format_=..., level=...)`. Call `lint_policies` with `settings.registries`, `settings.transform_ca_certs` and `settings.transform_package_mirrors`. Render JSON (`model_dump_json(by_alias=True)`) when `settings.log_format == "json"`; otherwise print a first line `skipped: N3 (KNOCK_REGISTRIES not set)` when skipped, then one `ERROR <path> <loc>: <message>` / `WARN <path> <loc>: <message>` line per finding, then `lint  errors=<n> warnings=<n>`. Finish with `raise typer.Exit(lint_exit_code(report))`. The docstring names `KNOCK_LOG_FORMAT=json` and says to point at the policies directory, not the repository root (review findings 5 and 6)
- [ ] 5.2 `knock/cli/main.py`: `app.command(name="lint")(lint_cmd)` after `verify`
- [ ] 5.3 `tests/integration/test_cli_lint.py` with `CliRunner`, without `fake_bin_path` (no tool may be called): valid tree exits 0; broken tree with `KNOCK_LOG_FORMAT=json` exits 1 and stdout validates against `lint_report_json_schema()` with `jsonschema`; missing dir exits 3; `KNOCK_REGISTRIES='not json'` exits 3; text mode without roster prints the skipped line first
- [ ] 5.4 Run `uv run pytest tests/integration/test_cli_lint.py -v --no-cov`; expected: all pass
- [ ] 5.5 Commit: `feat(cli): add knock lint`

## 6. Published schema and reference

- [ ] 6.1 `scripts/gen_reference.py`: add `"lint-report": (lint_report_json_schema, "LintReport (knock lint output)")` to `SCHEMAS`
- [ ] 6.2 Run `make reference`; expected: `git status --short docs/reference` lists `lint-report.schema.json`, `lint-report.md` (new) and `command-line-interface.md` (modified) only
- [ ] 6.3 Run `uv run pytest tests/unit/test_published_schemas.py tests/unit/test_readme_module_map.py -v --no-cov`. Expected: the schema test passes. The module map test fails until task 7.2
- [ ] 6.4 Commit: `docs(reference): publish the lint report schema and CLI reference`

## 7. Prose

- [ ] 7.1 `docs/how-to/lint-policies-in-ci.md` (how-to): run `knock lint policies/` in a merge-request job with `KNOCK_LOG_FORMAT=json`; what N3 needs and what its skip means; why to point at the policies directory; the offline collision limits (D3, D4) and that `reconcile` stays the backstop. Add its entry to `docs/how-to/README.md`
- [ ] 7.2 `docs/explanation/how-it-works.md`: add `lint` to the `cli/` verbs and `lint` to `use_cases/` in the module map; add a `knock lint` bullet to the verb list. Run `uv run pytest tests/unit/test_readme_module_map.py -v --no-cov`; expected: pass
- [ ] 7.3 `CLAUDE.md` and `docs/roadmap.md`: add `lint` to the CLI verbs line; in `CLAUDE.md`, name `load_policy_files` as the collecting loader that `load_policy_dir` wraps
- [ ] 7.4 Commit: `docs(lint): explain how to lint a policy repository in CI`

## 8. Gate and close

- [ ] 8.1 Run `make lint`; expected: ruff, mypy strict and the reference drift check all pass
- [ ] 8.2 Run `make test`; expected: pass, global branch coverage ≥ 90 %
- [ ] 8.3 Run `openspec validate lint-mirror-policies --type change --strict`; expected: `Change 'lint-mirror-policies' is valid`
- [ ] 8.4 Check every scenario of `specs/policy-lint/spec.md` against a test from tasks 2–5, and every finding of `review.md` against its treatment
- [ ] 8.5 Run `openspec archive lint-mirror-policies --yes` on the branch, then commit: `chore(openspec): archive lint-mirror-policies`
