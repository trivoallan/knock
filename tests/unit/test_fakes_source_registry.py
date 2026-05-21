from houba.ports.source_registry import SourceImage
from tests.fakes.source_registry import FakeSourceRegistryPort


def test_list_tags() -> None:
    src = FakeSourceRegistryPort(tags={"docker.io/rancher/k3s": ["v1.28.5", "v1.29.0"]})
    assert src.list_tags("docker.io/rancher/k3s") == ["v1.28.5", "v1.29.0"]


def test_inspect_returns_image() -> None:
    image = SourceImage(digest="sha256:abc", architecture="amd64", os="linux")
    src = FakeSourceRegistryPort(images={"docker.io/rancher/k3s:v1.29.0": image})
    assert src.inspect("docker.io/rancher/k3s:v1.29.0") == image
