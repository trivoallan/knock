from __future__ import annotations

import hashlib

from houba.errors import RegctlError
from houba.ports.registry import ImageInfo, Referrer


class FakeRegistryPort:
    def __init__(
        self,
        tags: dict[str, list[str]] | None = None,
        infos: dict[str, ImageInfo] | None = None,
        fail_copy: set[str] | None = None,
        fail_put: set[str] | None = None,
        copy_barrier: object | None = None,  # threading.Barrier; typed loosely to avoid an import
        referrers: dict[str, list[Referrer]] | None = None,
    ) -> None:
        self._tags = tags or {}
        self._infos = infos or {}
        self._fail_copy = fail_copy or set()
        self._fail_put = fail_put or set()
        self._copy_barrier = copy_barrier
        self._referrers = referrers or {}
        self.copied: list[tuple[str, str]] = []
        self.annotated: list[tuple[str, dict[str, str]]] = []
        self.deleted: list[str] = []
        self.logins: list[tuple[str, str, bool]] = []
        self.configured: list[tuple[str, bool, str | None]] = []
        self.marked: list[tuple[str, str, dict[str, str]]] = []
        self.unmarked: list[str] = []

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
        if self._copy_barrier is not None:
            self._copy_barrier.wait()  # type: ignore[attr-defined]
        if dst_ref in self._fail_copy:
            raise RegctlError(f"fake copy failure for {dst_ref}")
        self.copied.append((src_ref, dst_ref))

    def annotate(self, image_ref: str, annotations: dict[str, str]) -> str:
        self.annotated.append((image_ref, annotations))
        # deterministic synthetic post-annotate digest (distinct per ref)
        return f"sha256:{hashlib.sha256(image_ref.encode()).hexdigest()}"

    def delete_tag(self, image_ref: str) -> None:
        self.deleted.append(image_ref)

    def login(self, host: str, *, username: str, password: str, tls_verify: bool) -> None:
        self.logins.append((host, username, tls_verify))

    def list_referrers(self, image_ref: str, artifact_type: str) -> list[Referrer]:
        return [
            r for r in self._referrers.get(image_ref, []) if r.artifact_type == artifact_type
        ]

    # Journals only; _referrers is a read-fixture seeded via the constructor (see list_referrers).
    def put_referrer(
        self, image_ref: str, artifact_type: str, annotations: dict[str, str]
    ) -> None:
        if image_ref in self._fail_put:
            raise RegctlError(f"fake put_referrer failure for {image_ref}")
        self.marked.append((image_ref, artifact_type, annotations))

    def delete_referrer(self, referrer_ref: str) -> None:
        self.unmarked.append(referrer_ref)
