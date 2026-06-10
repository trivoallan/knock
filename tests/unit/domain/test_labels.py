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
        eol_product=None,
        eol_date=None,
    )

    assert labels["io.houba.source.registry"] == "docker.io"
    assert labels["io.houba.source.repository"] == "library/busybox"
    assert labels["io.houba.source.tag"] == "1.36"
    assert labels["io.houba.source.digest"] == "sha256:abc"
    assert labels["io.houba.import.date"] == "2026-05-21T10:30:00+00:00"
    assert labels["io.houba.import.harbor"] == "blue"
    assert "io.houba.eol.product" not in labels
    assert "io.houba.eol.date" not in labels


def test_eol_labels_included_when_provided() -> None:
    labels = build_labels(
        prefix="io.houba",
        src_registry="docker.io",
        src_repository="library/redis",
        src_tag="7.2",
        src_digest="sha256:def",
        import_date=datetime(2026, 5, 21, tzinfo=UTC),
        harbor="both",
        eol_product="redis",
        eol_date="2025-12-31",
    )

    assert labels["io.houba.eol.product"] == "redis"
    assert labels["io.houba.eol.date"] == "2025-12-31"


def test_build_labels_with_default_prefix() -> None:
    labels = build_labels(
        prefix="io.houba",
        src_registry="docker.io",
        src_repository="library/busybox",
        src_tag="1.36",
        src_digest="sha256:abc",
        import_date=datetime(2026, 5, 21, 10, 30, tzinfo=UTC),
        harbor="blue",
        eol_product=None,
        eol_date=None,
    )

    assert labels["io.houba.source.registry"] == "docker.io"
    assert labels["io.houba.source.repository"] == "library/busybox"
    assert labels["io.houba.source.tag"] == "1.36"
    assert labels["io.houba.source.digest"] == "sha256:abc"
    assert labels["io.houba.import.date"] == "2026-05-21T10:30:00+00:00"
    assert labels["io.houba.import.harbor"] == "blue"
    assert "io.houba.eol.product" not in labels
    assert "io.houba.eol.date" not in labels


def test_build_labels_with_empty_prefix_returns_empty_dict() -> None:
    labels = build_labels(
        prefix="",
        src_registry="docker.io",
        src_repository="library/busybox",
        src_tag="1.36",
        src_digest="sha256:abc",
        import_date=datetime(2026, 5, 21, 10, 30, tzinfo=UTC),
        harbor="blue",
        eol_product="busybox",
        eol_date="2027-01-01",
    )

    assert labels == {}
