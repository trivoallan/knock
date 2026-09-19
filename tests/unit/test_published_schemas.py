"""Drift test for the published JSON Schemas under docs/reference/schemas/.

Runs without the `docs` dependency group, so a model change that is not followed by
`make reference` fails `uv run pytest`, not only the CI reference diff.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from scripts.gen_reference import SCHEMAS, SCHEMAS_OUT


@pytest.mark.parametrize("slug", sorted(SCHEMAS))
def test_committed_schema_matches_the_model(slug: str) -> None:
    schema_fn, title, _position = SCHEMAS[slug]
    expected: dict[str, Any] = {**schema_fn(), "title": title}
    committed = json.loads((SCHEMAS_OUT / f"{slug}.schema.json").read_text())
    assert committed == expected, f"{slug}.schema.json is stale — run 'make reference'"


def test_coverage_report_schema_is_published() -> None:
    assert "coverage-report" in SCHEMAS
