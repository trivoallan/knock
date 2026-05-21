"""Wrapper subprocess autour de skopeo (lectures uniquement)."""

from __future__ import annotations

import json
import shutil
import subprocess

from hub2hub.errors import SkopeoError
from hub2hub.ports.source_registry import SourceImage


class SkopeoAdapter:
    def __init__(self, binary: str | None = None) -> None:
        resolved = binary or shutil.which("skopeo")
        if not resolved:
            raise SkopeoError("skopeo binary not found in PATH")
        self._bin = resolved

    def list_tags(self, image_ref: str) -> list[str]:
        out = self._run(["list-tags", f"docker://{image_ref}"])
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as e:
            raise SkopeoError(f"invalid JSON from skopeo list-tags: {e}") from e
        return list(payload.get("Tags", []))

    def inspect(self, image_ref: str) -> SourceImage:
        out = self._run(["inspect", f"docker://{image_ref}"])
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as e:
            raise SkopeoError(f"invalid JSON from skopeo inspect: {e}") from e
        return SourceImage(
            digest=payload["Digest"],
            architecture=payload.get("Architecture", ""),
            os=payload.get("Os", ""),
        )

    def _run(self, args: list[str]) -> str:
        try:
            r = subprocess.run(  # noqa: S603
                [self._bin, *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise SkopeoError(str(e)) from e
        if r.returncode != 0:
            raise SkopeoError(f"skopeo {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout
