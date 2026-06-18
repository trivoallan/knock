"""Drift test for the generated configuration reference table.

Imports _write_config_table from the generator and asserts that it produces
expected rows for well-known fields, without touching the committed docs/.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

# Import the function under test
from scripts.gen_reference import _write_config_table


@pytest.fixture()
def tmp_out(tmp_path: Path) -> Path:
    _write_config_table(tmp_path)
    return tmp_path / "configuration.md"


def test_header_row(tmp_out: Path) -> None:
    assert "| Variable | Type | Default | Description |" in tmp_out.read_text()


def test_label_prefix_row(tmp_out: Path) -> None:
    content = tmp_out.read_text()
    assert "| `HOUBA_LABEL_PREFIX` | string | `io.houba` |" in content


def test_sbom_formats_row(tmp_out: Path) -> None:
    content = tmp_out.read_text()
    assert '| `HOUBA_SBOM_FORMATS` | JSON list | `["spdx-json"]` |' in content


def test_max_concurrency_row(tmp_out: Path) -> None:
    content = tmp_out.read_text()
    assert "| `HOUBA_MAX_CONCURRENCY` | integer | `4` |" in content


def test_registries_row(tmp_out: Path) -> None:
    content = tmp_out.read_text()
    assert "| `HOUBA_REGISTRIES` | JSON object |" in content


def test_config_schema_json_written(tmp_out: Path) -> None:
    schema_path = tmp_out.parent / "config.schema.json"
    assert schema_path.exists()
    import json
    schema = json.loads(schema_path.read_text())
    assert "properties" in schema
