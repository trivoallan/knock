from __future__ import annotations

from pathlib import Path

import pytest

from houba.errors import BuildkitError
from houba.ports.image_builder import BuildRequest
from tests.fakes.image_builder import FakeImageBuilder


def test_fake_records_build_requests(tmp_path: Path) -> None:
    fake = FakeImageBuilder()
    df = tmp_path / "Dockerfile"
    df.write_text("FROM busybox:1.36\n")
    (tmp_path / "ca.crt").write_text("PEM")
    req = BuildRequest(
        dockerfile_path=df,
        context_dir=tmp_path,
        image_ref="harbor.example.com/lib/busybox:1.36",
        build_args={"VERSION": "1.36"},
    )
    fake.build_and_push(req)
    assert fake.requests == [req]
    assert fake.dockerfiles == ["FROM busybox:1.36\n"]
    assert fake.contexts == [{"Dockerfile": "FROM busybox:1.36\n", "ca.crt": "PEM"}]


def test_fake_simulates_failure() -> None:
    fake = FakeImageBuilder(fail=True)

    with pytest.raises(BuildkitError):
        fake.build_and_push(
            BuildRequest(
                dockerfile_path=Path("/x"),
                context_dir=Path("/x"),
                image_ref="x",
                build_args={},
            )
        )
