from __future__ import annotations

from houba.ports.source_registry import SourceImage


class FakeSourceRegistryPort:
    def __init__(
        self,
        tags: dict[str, list[str]] | None = None,
        images: dict[str, SourceImage] | None = None,
    ) -> None:
        self._tags = tags or {}
        self._images = images or {}

    def list_tags(self, image_ref: str) -> list[str]:
        return list(self._tags.get(image_ref, []))

    def inspect(self, image_ref: str) -> SourceImage:
        return self._images[image_ref]
