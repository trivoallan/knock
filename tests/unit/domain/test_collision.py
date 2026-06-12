from __future__ import annotations

import pytest

from houba.domain.collision import AliasTarget, detect_alias_collisions, detect_dest_repo_collisions
from houba.errors import PolicyValidationError


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
