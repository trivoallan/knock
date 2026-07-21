"""Unit coverage for _ref_matches — the DLQ selector predicate. Pure, no Redis."""

from knock.adapters.redis_streams import _ref_matches


def test_full_digest_matches():
    assert _ref_matches("repo@sha256:abc123", "sha256:abc123") is True


def test_bare_hex_matches():
    assert _ref_matches("repo@sha256:abc123", "abc123") is True


def test_all_selector_matches_everything():
    assert _ref_matches("repo@sha256:abc123", "--all") is True
    assert _ref_matches("anything-without-at", "--all") is True


def test_empty_selector_matches_nothing():
    assert _ref_matches("repo@sha256:abc123", "") is False


def test_non_matching_selector_is_false():
    assert _ref_matches("repo@sha256:abc123", "sha256:deadbeef") is False
    assert _ref_matches("repo@sha256:abc123", "deadbeef") is False


def test_ref_without_digest_never_matches_a_selector():
    assert _ref_matches("repo-with-no-digest", "abc123") is False
