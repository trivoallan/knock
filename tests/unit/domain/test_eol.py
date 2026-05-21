from pathlib import Path

import pytest

from hub2hub.domain.eol import (
    EolEntry,
    parse_markdown_table,
    resolve_eol_for_tag,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "synthetic" / "eol_kubernetes.md"


def test_parse_markdown_table_returns_rows() -> None:
    entries = parse_markdown_table(FIXTURE.read_text())

    assert entries == [
        EolEntry(release_cycle="1.28", eol="2024-10-28"),
        EolEntry(release_cycle="1.29", eol="2025-02-28"),
        EolEntry(release_cycle="1.30", eol="2026-06-30"),
        EolEntry(release_cycle="1.31", eol="false"),
    ]


def test_parse_markdown_table_empty_input() -> None:
    assert parse_markdown_table("") == []


@pytest.mark.parametrize(
    "tag,expected",
    [
        ("1.28.5", "2024-10-28"),
        ("v1.29.10", "2025-02-28"),
        ("1.30.0", "2026-06-30"),
        ("1.31.0", None),  # eol=false → pas de date
        ("1.32.0", None),  # cycle inconnu
        ("latest", None),
    ],
)
def test_resolve_eol_for_tag(tag: str, expected: str | None) -> None:
    entries = parse_markdown_table(FIXTURE.read_text())
    assert resolve_eol_for_tag(tag, entries) == expected
