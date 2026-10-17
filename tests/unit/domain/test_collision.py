from __future__ import annotations

import pytest

from knock.domain.collision import (
    AliasClaim,
    AliasTarget,
    Overlap,
    detect_alias_collisions,
    detect_dest_repo_collisions,
    find_alias_overlaps,
)
from knock.errors import PolicyValidationError


def test_no_collision_distinct_aliases() -> None:
    detect_alias_collisions(
        [
            AliasTarget(dest_repo="eu/lib/redis", alias="7.2", target="7.2.1"),
            AliasTarget(dest_repo="eu/lib/redis", alias="latest", target="7.3.0"),
        ]
    )


def test_same_alias_different_repo_ok() -> None:
    detect_alias_collisions(
        [
            AliasTarget(dest_repo="eu/lib/redis", alias="latest", target="7.3.0"),
            AliasTarget(dest_repo="us/lib/redis", alias="latest", target="7.3.0"),
        ]
    )


def test_collision_same_repo_same_alias_raises() -> None:
    with pytest.raises(PolicyValidationError, match="alias collision"):
        detect_alias_collisions(
            [
                AliasTarget(dest_repo="eu/lib/redis", alias="latest", target="7.3.0"),
                AliasTarget(dest_repo="eu/lib/redis", alias="latest", target="8.0.0"),
            ]
        )


def test_collision_detected_even_when_same_target() -> None:
    with pytest.raises(PolicyValidationError, match="alias collision"):
        detect_alias_collisions(
            [
                AliasTarget(dest_repo="eu/lib/redis", alias="latest", target="7.3.0"),
                AliasTarget(dest_repo="eu/lib/redis", alias="latest", target="7.3.0"),
            ]
        )


def test_dest_repo_collision_raises_when_two_policies_share_a_repo() -> None:
    owners = [
        ("harbor.corp/lib/redis", "redis"),
        ("harbor.corp/lib/redis", "redis-clone"),  # same repo, different policy
    ]
    with pytest.raises(PolicyValidationError, match=r"harbor\.corp/lib/redis"):
        detect_dest_repo_collisions(owners)


def test_dest_repo_collision_passes_when_disjoint() -> None:
    owners = [
        ("harbor.corp/lib/redis", "redis"),
        ("harbor.corp/lib/nginx", "nginx"),
        ("harbor.corp/lib/redis", "redis"),  # same (repo, policy) is fine
    ]
    detect_dest_repo_collisions(owners)  # must not raise


def test_overlap_same_literal_same_repo_is_certain() -> None:
    claims = [
        AliasClaim("eu/lib/redis", "latest", "a.yaml#0"),
        AliasClaim("eu/lib/redis", "latest", "b.yaml#0"),
    ]
    assert find_alias_overlaps(claims) == [
        Overlap("eu/lib/redis", "latest", ("a.yaml#0", "b.yaml#0"), certain=True)
    ]


def test_overlap_same_literal_two_repos_gives_nothing() -> None:
    claims = [
        AliasClaim("eu/lib/redis", "latest", "a.yaml#0"),
        AliasClaim("us/lib/redis", "latest", "b.yaml#0"),
    ]
    assert find_alias_overlaps(claims) == []


def test_overlap_two_templates_same_repo_is_possible() -> None:
    claims = [
        AliasClaim("eu/lib/redis", "{major}", "a.yaml#0"),
        AliasClaim("eu/lib/redis", "{major}", "b.yaml#0"),
    ]
    assert find_alias_overlaps(claims) == [
        Overlap("eu/lib/redis", "{major} / {major}", ("a.yaml#0", "b.yaml#0"), certain=False)
    ]


def test_overlap_distinct_templates_joined_in_alias() -> None:
    claims = [
        AliasClaim("r", "{major}", "a"),
        AliasClaim("r", "{major}.{minor}", "b"),
    ]
    assert find_alias_overlaps(claims) == [
        Overlap("r", "{major} / {major}.{minor}", ("a", "b"), certain=False)
    ]


def test_overlap_template_and_literal_not_flagged_documented_limit() -> None:
    # Design D3: a template and a literal that could meet are not flagged.
    claims = [
        AliasClaim("r", "{major}", "a"),
        AliasClaim("r", "1", "b"),
    ]
    assert find_alias_overlaps(claims) == []


def test_overlap_same_origin_twice_gives_nothing() -> None:
    assert (
        find_alias_overlaps([AliasClaim("r", "latest", "a"), AliasClaim("r", "latest", "a")]) == []
    )
    assert (
        find_alias_overlaps([AliasClaim("r", "{major}", "a"), AliasClaim("r", "{minor}", "a")])
        == []
    )


def test_overlap_three_origins_give_three_pairs_in_order() -> None:
    claims = [AliasClaim("r", "latest", o) for o in ("a", "b", "c")]
    assert [o.origins for o in find_alias_overlaps(claims)] == [("a", "b"), ("a", "c"), ("b", "c")]


def test_overlap_output_is_deterministic() -> None:
    claims = [
        AliasClaim("r", "latest", "a"),
        AliasClaim("r", "{major}", "a"),
        AliasClaim("r", "latest", "b"),
        AliasClaim("r", "{major}", "b"),
    ]
    first = find_alias_overlaps(claims)
    assert first == find_alias_overlaps(list(claims))
    assert [o.certain for o in first] == [True, False]
