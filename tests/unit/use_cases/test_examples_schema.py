"""Every shipped example policy must validate against the published JSON Schema.

This closes the examples-drift gap generically: instead of a bespoke per-file parse
test, it globs *every* ``docs/examples/**/*.yml`` and validates it against
``mirror_policy_json_schema()`` — the same schema editors/CI use. A newly added
example is therefore covered automatically, with no hand-written test.
"""

from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest
import yaml

from houba.domain.mirror_policy import mirror_policy_json_schema

# Repo root: tests/unit/use_cases/<this file> → parents[3].
_REPO_ROOT = Path(__file__).resolve().parents[3]
_EXAMPLES_DIR = _REPO_ROOT / "docs" / "examples"

EXAMPLE_FILES = sorted(_EXAMPLES_DIR.glob("**/*.yml"))


def test_examples_were_discovered() -> None:
    """Guard: an empty glob would make the parametrized test vacuously pass."""
    assert EXAMPLE_FILES, f"no example policies found under {_EXAMPLES_DIR}"


@pytest.mark.parametrize(
    "example",
    EXAMPLE_FILES,
    ids=[str(p.relative_to(_EXAMPLES_DIR)) for p in EXAMPLE_FILES],
)
def test_example_validates_against_schema(example: Path) -> None:
    document = yaml.safe_load(example.read_text())
    jsonschema.validate(instance=document, schema=mirror_policy_json_schema())
