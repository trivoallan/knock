from scripts.scan_streams import ref_matches


def test_ref_matches_full_digest():
    assert ref_matches("repo@sha256:deadbeef", "sha256:deadbeef")


def test_ref_matches_bare_hex():
    # the form an operator naturally copies from `scan-dlq list`
    assert ref_matches("repo@sha256:deadbeef", "deadbeef")


def test_ref_matches_all():
    assert ref_matches("repo@sha256:anything", "--all")


def test_ref_matches_rejects_non_match_and_empty():
    assert not ref_matches("repo@sha256:deadbeef", "cafef00d")
    assert not ref_matches("repo@sha256:deadbeef", "")  # empty never matches (no silent match-all)
    assert not ref_matches("no-at-sign-here", "deadbeef")
