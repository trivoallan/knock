"""Cross-policy alias-collision detection (spec §5.2).

Aliases (moving tags) must be unique per destination repository. Any two that
would write the same alias name into the same repo collide — reconcile fails fast
during the load-and-validate phase (§8), never last-wins.
"""

from __future__ import annotations

from dataclasses import dataclass

from knock.errors import PolicyValidationError


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


def detect_dest_repo_collisions(owners: list[tuple[str, str]]) -> None:
    """Each destination repository must be owned by exactly one policy.

    `owners` is a list of (dest_repo, policy_name). Two *different* policies
    writing the same repo would mutually delete each other's tags (reconcile is
    authoritative per repo), so this is forbidden — and it is the invariant that
    makes horizontal sharding (one writer per repo) safe. Fails fast, before any
    mutation. The same (repo, policy) appearing twice (e.g. two imports of one
    policy into one repo) is fine.
    """
    by_repo: dict[str, set[str]] = {}
    for repo, policy in owners:
        by_repo.setdefault(repo, set()).add(policy)
    for repo, policies in by_repo.items():
        if len(policies) > 1:
            raise PolicyValidationError(
                f"dest-repo {repo!r} is claimed by multiple policies "
                f"({sorted(policies)}); each repository must be owned by exactly one policy"
            )
