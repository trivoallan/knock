"""Parsing du tableau Markdown retourné par endoflife.date et résolution EOL par tag.

Référence : vars/importProduct.groovy:1509-1606.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CYCLE_RE_CACHE: dict[str, re.Pattern[str]] = {}


@dataclass(frozen=True)
class EolEntry:
    release_cycle: str
    eol: str  # "YYYY-MM-DD" ou "false" ou autre chaîne brute


def parse_markdown_table(text: str) -> list[EolEntry]:
    """Extrait les lignes (releaseCycle, eol) d'un tableau Markdown.

    Tolère colonnes supplémentaires. Ignore les lignes vides et la ligne séparateur.
    """
    if not text.strip():
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []

    header_cells = [c.strip().lower() for c in lines[0].strip("|").split("|")]
    try:
        i_cycle = header_cells.index("releasecycle")
        i_eol = header_cells.index("eol")
    except ValueError:
        return []

    entries: list[EolEntry] = []
    for line in lines[2:]:  # skip header + séparateur
        cells = [c.strip() for c in line.strip("|").split("|")]
        if max(i_cycle, i_eol) >= len(cells):
            continue
        entries.append(EolEntry(release_cycle=cells[i_cycle], eol=cells[i_eol]))
    return entries


def resolve_eol_for_tag(tag: str, entries: list[EolEntry]) -> str | None:
    """Retourne la date EOL (YYYY-MM-DD) pour un tag, ou None si inconnue ou désactivée."""
    normalized = tag.lstrip("v")
    for entry in entries:
        if entry.eol in ("", "false", "False"):
            continue
        pattern = _CYCLE_RE_CACHE.setdefault(
            entry.release_cycle,
            re.compile(rf"^{re.escape(entry.release_cycle)}(\.|$)"),
        )
        if pattern.match(normalized):
            return entry.eol
    return None
