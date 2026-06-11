"""Cross-policy alias-collision detection (spec §5.2).

Aliases (moving tags) must be unique per destination repository. Any two that
would write the same alias name into the same repo collide — reconcile fails fast
during the load-and-validate phase (§8), never last-wins.
"""

from __future__ import annotations

from dataclasses import dataclass

from houba.errors import PolicyValidationError


@dataclass(frozen=True)
class AliasTarget:
    dest_repo: str
    alias: str
    target: str


def detect_alias_collisions(entries: list[AliasTarget]) -> None:
    seen: dict[tuple[str, str], str] = {}
    for e in entries:
        key = (e.dest_repo, e.alias)
        if key in seen:
            raise PolicyValidationError(
                f"alias collision: {e.alias!r} written twice into {e.dest_repo!r} "
                f"(targets {seen[key]!r} and {e.target!r})"
            )
        seen[key] = e.target
