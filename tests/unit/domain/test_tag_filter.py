from datetime import UTC, datetime, timedelta

import pytest

from hub2hub.domain.properties import Properties, parse_properties
from hub2hub.domain.tag_filter import HarborTagState, TagsDecision, compute_tags_to_import


def _props(yaml: str) -> Properties:
    return parse_properties(yaml)


BASE_YAML = """
source:
  registry: docker.io
  repository: library/busybox
destination:
  harbor: blue
  project: lib
  repository: busybox
tags:
  semver_only: true
"""

NOW = datetime(2026, 5, 21, 12, 0, tzinfo=UTC)


def test_all_new_tags_imported() -> None:
    decision = compute_tags_to_import(
        src_tags=["1.36", "1.37"],
        src_digests={
            "1.36": ("sha256:a", NOW - timedelta(days=30)),
            "1.37": ("sha256:b", NOW - timedelta(days=30)),
        },
        properties=_props(BASE_YAML),
        harbor_state={},
        now=NOW,
    )

    assert decision == TagsDecision(to_import=["1.36", "1.37"], to_update=[], to_delete=[])


def test_already_present_with_same_digest_skipped() -> None:
    harbor_state = {
        "1.36": HarborTagState(digest="sha256:a", push_time=NOW - timedelta(days=10)),
    }

    decision = compute_tags_to_import(
        src_tags=["1.36"],
        src_digests={"1.36": ("sha256:a", NOW - timedelta(days=30))},
        properties=_props(BASE_YAML),
        harbor_state=harbor_state,
        now=NOW,
    )

    assert decision.to_import == []
    assert decision.to_update == []


def test_digest_changed_recently_waits_7_days() -> None:
    harbor_state = {
        "1.36": HarborTagState(digest="sha256:old", push_time=NOW - timedelta(days=30)),
    }
    src_digests = {"1.36": ("sha256:new", NOW - timedelta(days=3))}

    decision = compute_tags_to_import(
        src_tags=["1.36"],
        src_digests=src_digests,
        properties=_props(BASE_YAML),
        harbor_state=harbor_state,
        now=NOW,
    )

    assert "1.36" not in decision.to_import
    assert "1.36" not in decision.to_update


def test_digest_changed_more_than_7_days_updates() -> None:
    harbor_state = {
        "1.36": HarborTagState(digest="sha256:old", push_time=NOW - timedelta(days=30)),
    }
    src_digests = {"1.36": ("sha256:new", NOW - timedelta(days=10))}

    decision = compute_tags_to_import(
        src_tags=["1.36"],
        src_digests=src_digests,
        properties=_props(BASE_YAML),
        harbor_state=harbor_state,
        now=NOW,
    )

    assert "1.36" in decision.to_update


def test_exclude_regex_filters() -> None:
    yaml = BASE_YAML + "\n  exclude_regex:\n    - '-rc'\n    - '-beta'\n"
    tags = ["1.36", "1.37-rc1", "1.37-beta"]
    decision = compute_tags_to_import(
        src_tags=tags,
        src_digests={t: ("sha256:x", NOW - timedelta(days=30)) for t in tags},
        properties=_props(yaml),
        harbor_state={},
        now=NOW,
    )

    assert decision.to_import == ["1.36"]


def test_semver_only_drops_non_semver_tags() -> None:
    decision = compute_tags_to_import(
        src_tags=["1.36", "latest", "edge"],
        src_digests={t: ("sha256:x", NOW - timedelta(days=30)) for t in ["1.36", "latest", "edge"]},
        properties=_props(BASE_YAML),
        harbor_state={},
        now=NOW,
    )

    assert decision.to_import == ["1.36"]


def test_include_regex_keeps_only_matches() -> None:
    yaml = BASE_YAML + "\n  include_regex: '^1\\.36$'\n"
    decision = compute_tags_to_import(
        src_tags=["1.36", "1.37"],
        src_digests={t: ("sha256:x", NOW - timedelta(days=30)) for t in ["1.36", "1.37"]},
        properties=_props(yaml),
        harbor_state={},
        now=NOW,
    )

    assert decision.to_import == ["1.36"]


def test_to_delete_when_tag_absent_from_source() -> None:
    harbor_state = {
        "1.35": HarborTagState(digest="sha256:gone", push_time=NOW - timedelta(days=90)),
        "1.36": HarborTagState(digest="sha256:a", push_time=NOW - timedelta(days=10)),
    }
    decision = compute_tags_to_import(
        src_tags=["1.36"],
        src_digests={"1.36": ("sha256:a", NOW - timedelta(days=30))},
        properties=_props(BASE_YAML),
        harbor_state=harbor_state,
        now=NOW,
    )

    assert "1.35" in decision.to_delete


@pytest.mark.parametrize("bad_regex", ["[unclosed", "*invalid"])
def test_invalid_regex_raises(bad_regex: str) -> None:
    from hub2hub.errors import PropertiesValidationError

    yaml = BASE_YAML + f"\n  include_regex: '{bad_regex}'\n"
    with pytest.raises(PropertiesValidationError):
        compute_tags_to_import(
            src_tags=["1.36"],
            src_digests={"1.36": ("sha256:x", NOW - timedelta(days=30))},
            properties=_props(yaml),
            harbor_state={},
            now=NOW,
        )
