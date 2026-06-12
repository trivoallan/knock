from __future__ import annotations

from houba.ports.registry import ImageInfo


class FakeRegistryPort:
    def __init__(
        self,
        tags: dict[str, list[str]] | None = None,
        infos: dict[str, ImageInfo] | None = None,
    ) -> None:
        self._tags = tags or {}
        self._infos = infos or {}
        self.copied: list[tuple[str, str]] = []
        self.annotated: list[tuple[str, dict[str, str]]] = []
        self.deleted: list[str] = []
        self.logins: list[tuple[str, str, bool]] = []
        self.configured: list[tuple[str, bool, str | None]] = []

    def configure_registry(self, host: str, *, tls_verify: bool, ca_cert: str | None) -> None:
        self.configured.append((host, tls_verify, ca_cert))

    def list_tags(self, repo_ref: str) -> list[str]:
        return list(self._tags.get(repo_ref, []))

    def inspect(self, image_ref: str) -> ImageInfo:
        try:
            return self._infos[image_ref]
        except KeyError:
            raise KeyError(f"FakeRegistryPort: no seeded ImageInfo for {image_ref!r}") from None

    def copy(self, src_ref: str, dst_ref: str) -> None:
        self.copied.append((src_ref, dst_ref))

    def annotate(self, image_ref: str, annotations: dict[str, str]) -> None:
        self.annotated.append((image_ref, annotations))

    def delete_tag(self, image_ref: str) -> None:
        self.deleted.append(image_ref)

    def login(self, host: str, *, username: str, password: str, tls_verify: bool) -> None:
        self.logins.append((host, username, tls_verify))
