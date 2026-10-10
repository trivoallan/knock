## 1. The plan says what knock builds

- [x] 1.1 Failing tests: the schema carries `transformed` as an optional boolean; an entry
  round-trips with it; the gate key ignores it (`tests/unit/domain/test_gate.py`); `--plan-out`
  writes true for a policy with a transform and false for a copy
  (`tests/unit/use_cases/test_reconcile_gate.py`)
- [x] 1.2 `PlannedOperation.transformed: bool = False`, outside `key()` (`knock/domain/gate.py`)
- [x] 1.3 Fill it where the plan is written, with the expression that decides staging
  (`knock/use_cases/reconcile_registry.py`)
- [x] 1.4 `make reference`; update `docs/examples/gate/plan.json` and
  `docs/reference/examples/gate.md`
- [x] 1.5 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy knock`, and the domain coverage gate all pass
- [x] 1.6 `openspec validate plan-says-transformed --strict`
