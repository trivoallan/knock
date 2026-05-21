from datetime import UTC, datetime

from houba.domain.labels import build_labels


def test_required_labels_present() -> None:
    labels = build_labels(
        src_registry="docker.io",
        src_repository="library/busybox",
        src_tag="1.36",
        src_digest="sha256:abc",
        import_date=datetime(2026, 5, 21, 10, 30, tzinfo=UTC),
        harbor="blue",
        eol_product=None,
        eol_date=None,
    )

    assert labels["fr.sncf.h2h.source.registry"] == "docker.io"
    assert labels["fr.sncf.h2h.source.repository"] == "library/busybox"
    assert labels["fr.sncf.h2h.source.tag"] == "1.36"
    assert labels["fr.sncf.h2h.source.digest"] == "sha256:abc"
    assert labels["fr.sncf.h2h.import.date"] == "2026-05-21T10:30:00+00:00"
    assert labels["fr.sncf.h2h.import.harbor"] == "blue"
    assert "fr.sncf.h2h.eol.product" not in labels
    assert "fr.sncf.h2h.eol.date" not in labels


def test_eol_labels_included_when_provided() -> None:
    labels = build_labels(
        src_registry="docker.io",
        src_repository="library/redis",
        src_tag="7.2",
        src_digest="sha256:def",
        import_date=datetime(2026, 5, 21, tzinfo=UTC),
        harbor="both",
        eol_product="redis",
        eol_date="2025-12-31",
    )

    assert labels["fr.sncf.h2h.eol.product"] == "redis"
    assert labels["fr.sncf.h2h.eol.date"] == "2025-12-31"
