"""Port d'accès à endoflife.date (lecture seulement)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EolEntry:
    """Une entrée de cycle EOL pour un produit.

    `eol` peut être une date ISO (`"2027-06-01"`) ou une string booléenne renvoyée
    par endoflife.date (`"false"`, `"true"`). On garde la valeur brute ; le
    parsing est dans `domain/eol.py`.
    """

    cycle: str
    eol: str
    latest: str = ""
    lts: bool = False


class EolSourcePort(Protocol):
    def fetch_eol(self, product: str) -> list[EolEntry]: ...
