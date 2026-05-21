from houba.ports.harbor import Artifact, Repository
from tests.fakes.harbor import FakeHarborPort


def test_get_repositories_returns_seeded() -> None:
    repos = [Repository(name="rancher/k3s", project_id=1)]
    harbor = FakeHarborPort(repositories={"04228.proxy.docker.io": repos})

    assert harbor.get_repositories("04228.proxy.docker.io") == repos


def test_get_artifacts_returns_seeded() -> None:
    arts = [Artifact(digest="sha256:abc", tags=["v1.0.0"], push_time="2026-01-01T00:00:00Z")]
    harbor = FakeHarborPort(artifacts={("04228.proxy.docker.io", "rancher/k3s"): arts})

    assert harbor.get_artifacts("04228.proxy.docker.io", "rancher/k3s") == arts


def test_get_artifacts_unknown_returns_empty() -> None:
    harbor = FakeHarborPort()
    assert harbor.get_artifacts("p", "r") == []
