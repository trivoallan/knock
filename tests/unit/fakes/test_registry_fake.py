from houba.ports.registry import Referrer
from tests.fakes.registry import FakeRegistryPort


def test_put_referrer_is_journalled() -> None:
    reg = FakeRegistryPort()
    reg.put_referrer("repo:6.0.0", "application/vnd.houba.lifecycle.pending+json", {"k": "v"})
    assert reg.marked == [
        ("repo:6.0.0", "application/vnd.houba.lifecycle.pending+json", {"k": "v"})
    ]


def test_list_referrers_returns_seeded_referrers() -> None:
    ref = Referrer(
        digest="sha256:ref1",
        artifact_type="application/vnd.houba.lifecycle.pending+json",
        annotations={},
        subject_tag="6.0.0",
    )
    reg = FakeRegistryPort(
        referrers={"repo:6.0.0": [ref]},
    )
    got = reg.list_referrers("repo:6.0.0", "application/vnd.houba.lifecycle.pending+json")
    assert got == [ref]
    # type filter excludes non-matching
    assert reg.list_referrers("repo:6.0.0", "application/vnd.other") == []


def test_delete_referrer_is_journalled() -> None:
    reg = FakeRegistryPort()
    reg.delete_referrer("repo@sha256:ref1")
    assert reg.unmarked == ["repo@sha256:ref1"]
