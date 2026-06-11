from __future__ import annotations

from datetime import UTC, datetime

import pytest

from houba.ports.registry import ImageInfo
from tests.fakes.registry import FakeRegistryPort


def _info(digest: str) -> ImageInfo:
    return ImageInfo(digest=digest, created=datetime(2026, 1, 1, tzinfo=UTC), annotations={})


def test_fake_list_tags_seeded() -> None:
    fake = FakeRegistryPort(tags={"docker.io/redis": ["7.2.0", "7.3.0"]})
    assert fake.list_tags("docker.io/redis") == ["7.2.0", "7.3.0"]
    assert fake.list_tags("unknown") == []


def test_fake_inspect_seeded() -> None:
    fake = FakeRegistryPort(infos={"docker.io/redis:7.2.0": _info("sha256:a")})
    assert fake.inspect("docker.io/redis:7.2.0").digest == "sha256:a"


def test_fake_journals_writes() -> None:
    fake = FakeRegistryPort()
    fake.copy("src:1", "dst:1")
    fake.annotate("dst:1", {"org.opencontainers.image.base.digest": "sha256:a"})
    fake.delete_tag("dst:old")
    assert fake.copied == [("src:1", "dst:1")]
    assert fake.annotated == [("dst:1", {"org.opencontainers.image.base.digest": "sha256:a"})]
    assert fake.deleted == ["dst:old"]


def test_fake_inspect_unseeded_raises_clear_keyerror() -> None:
    with pytest.raises(KeyError, match="no seeded ImageInfo"):
        FakeRegistryPort().inspect("missing:1")
