from datetime import UTC, datetime

from houba.domain.labels import build_labels


def test_required_labels_present() -> None:
    labels = build_labels(
        prefix="io.houba",
        src_registry="docker.io",
        src_repository="library/busybox",
        src_tag="1.36",
        src_digest="sha256:abc",
        import_date=datetime(2026, 5, 21, 10, 30, tzinfo=UTC),
        harbor="blue",
    )

    assert labels["io.houba.source.registry"] == "docker.io"
    assert labels["io.houba.source.repository"] == "library/busybox"
    assert labels["io.houba.source.tag"] == "1.36"
    assert labels["io.houba.source.digest"] == "sha256:abc"
    assert labels["io.houba.import.date"] == "2026-05-21T10:30:00+00:00"
    assert labels["io.houba.import.harbor"] == "blue"


def test_build_labels_with_custom_prefix() -> None:
    labels = build_labels(
        prefix="com.example",
        src_registry="docker.io",
        src_repository="library/busybox",
        src_tag="1.36",
        src_digest="sha256:abc",
        import_date=datetime(2026, 5, 21, 10, 30, tzinfo=UTC),
        harbor="blue",
    )

    assert labels["com.example.source.registry"] == "docker.io"
    assert labels["com.example.source.tag"] == "1.36"
    assert labels["com.example.import.harbor"] == "blue"


def test_build_labels_with_empty_prefix_returns_empty_dict() -> None:
    labels = build_labels(
        prefix="",
        src_registry="docker.io",
        src_repository="library/busybox",
        src_tag="1.36",
        src_digest="sha256:abc",
        import_date=datetime(2026, 5, 21, 10, 30, tzinfo=UTC),
        harbor="blue",
    )

    assert labels == {}
