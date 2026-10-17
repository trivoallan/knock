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


@dataclass(frozen=True)
class AliasClaim:
    """One alias (name or template) an import writes into a destination repo."""

    dest_repo: str
    alias: str
    origin: str


@dataclass(frozen=True)
class Overlap:
    """Two claims that collide (`certain`) or may collide (`possible`)."""

    dest_repo: str
    alias: str
    origins: tuple[str, str]
    certain: bool


def find_alias_overlaps(claims: list[AliasClaim]) -> list[Overlap]:
    """Collect alias overlaps knowable offline, without upstream tags (design D3).

    An alias is literal when it contains no `{`; `latest` is literal, since its
    name is fixed and the name is what collides. Two literal claims with the
    same `(dest_repo, alias)` from different origins are a certain overlap. Two
    template claims on the same `dest_repo` from different origins are a
    possible overlap (`alias` holds both templates joined by ` / `), because
    rendering depends on upstream tags.

    Documented limit (D3): a template and a literal that could meet (`{major}`
    and `1`) are NOT flagged. One origin never overlaps itself. Each unordered
    pair of origins is reported once, in input order of the pair's second claim.
    """
    overlaps: list[Overlap] = []
    for i, second in enumerate(claims):
        second_literal = "{" not in second.alias
        for first in claims[:i]:
            if first.dest_repo != second.dest_repo or first.origin == second.origin:
                continue
            first_literal = "{" not in first.alias
            if first_literal and second_literal:
                if first.alias == second.alias:
                    overlaps.append(
                        Overlap(
                            second.dest_repo,
                            second.alias,
                            (first.origin, second.origin),
                            certain=True,
                        )
                    )
            elif not first_literal and not second_literal:
                overlaps.append(
                    Overlap(
                        second.dest_repo,
                        f"{first.alias} / {second.alias}",
                        (first.origin, second.origin),
                        certain=False,
                    )
                )
    return overlaps


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
