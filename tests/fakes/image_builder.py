from __future__ import annotations

from houba.errors import BuildkitError
from houba.ports.image_builder import BuildRequest


class FakeImageBuilder:
    def __init__(self, *, fail: bool = False) -> None:
        self.requests: list[BuildRequest] = []
        self._fail = fail

    def build_and_push(self, request: BuildRequest) -> None:
        if self._fail:
            raise BuildkitError("fake builder configured to fail")
        self.requests.append(request)
