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
class AliasOverlap:
    """Two imports writing aliases into one repo.

    `certain` is True when they surely collide, False when they only may.
    """

    dest_repo: str
    alias: str
    origins: tuple[str, str]
    certain: bool


def _is_literal(alias: str) -> bool:
    return "{" not in alias


def find_alias_overlaps(claims: list[AliasClaim]) -> list[AliasOverlap]:
    """Collect alias overlaps knowable offline, without upstream tags (design D3).

    An alias is literal when it contains no `{`; `latest` is literal, since its
    name is fixed and the name is what collides.

    Per destination repo and per pair of distinct origins (imports), report:
    - one certain overlap for each literal alias both origins claim;
    - at most one possible overlap if both origins claim templates (rendering
      depends on upstream tags). Its `alias` lists the earlier origin's
      templates, then the later origin's, each without duplicates within an
      origin, in input order, joined by ` / `.

    `origins` is (earlier, later) by first appearance in `claims`. Overlaps are
    ordered by the first claim that completes them, so output is deterministic.
    Documented limit (D3): a template and a literal that could meet (`{major}`
    and `1`) are NOT flagged. One origin never overlaps itself.
    """
    # dest_repo -> origin -> aliases in input order (with input index)
    repos: dict[str, dict[str, list[tuple[int, str]]]] = {}
    for i, c in enumerate(claims):
        repos.setdefault(c.dest_repo, {}).setdefault(c.origin, []).append((i, c.alias))

    found: list[tuple[int, AliasOverlap]] = []
    for repo, by_origin in repos.items():
        origins = list(by_origin)
        for n, first in enumerate(origins):
            for second in origins[n + 1 :]:
                pair = (first, second)
                lits1, tpls1 = _split(by_origin[first])
                lits2, tpls2 = _split(by_origin[second])
                for alias, idx1 in lits1.items():
                    if alias in lits2:
                        found.append(
                            (max(idx1, lits2[alias]), AliasOverlap(repo, alias, pair, certain=True))
                        )
                if tpls1 and tpls2:
                    alias = " / ".join([*tpls1, *tpls2])
                    done = max(next(iter(tpls1.values())), next(iter(tpls2.values())))
                    found.append((done, AliasOverlap(repo, alias, pair, certain=False)))
    found.sort(key=lambda f: f[0])
    return [o for _, o in found]


def _split(
    entries: list[tuple[int, str]],
) -> tuple[dict[str, int], dict[str, int]]:
    """Distinct literals and distinct templates, each mapped to its first input index."""
    literals: dict[str, int] = {}
    templates: dict[str, int] = {}
    for idx, alias in entries:
        target = literals if _is_literal(alias) else templates
        target.setdefault(alias, idx)
    return literals, templates


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
