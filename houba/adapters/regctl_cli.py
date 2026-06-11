"""Wrapper subprocess autour de regctl (lectures + écritures OCI)."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from houba.errors import RegctlError
from houba.ports.registry import ImageInfo


class RegctlAdapter:
    def __init__(self, binary: str | None = None) -> None:
        if binary is not None:
            if not Path(binary).is_file():
                raise RegctlError(f"regctl binary not found: {binary}")
            self._bin = binary
            return
        resolved = shutil.which("regctl")
        if not resolved:
            raise RegctlError("regctl binary not found in PATH")
        self._bin = resolved

    def list_tags(self, repo_ref: str) -> list[str]:
        out = self._run(["tag", "ls", repo_ref])
        return [line.strip() for line in out.splitlines() if line.strip()]

    def inspect(self, image_ref: str) -> ImageInfo:
        digest = self._run(["image", "digest", image_ref]).strip()
        manifest = self._json(["manifest", "get", image_ref, "--format", "{{json .}}"])
        config = self._json(["image", "config", image_ref, "--format", "{{json .}}"])
        raw_annotations = manifest.get("annotations")
        annotations = dict(raw_annotations) if isinstance(raw_annotations, dict) else {}
        created_raw = config.get("created")
        created = self._parse_time(created_raw) if isinstance(created_raw, str) else None
        return ImageInfo(digest=digest, created=created, annotations=annotations)

    def _parse_time(self, value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _json(self, args: list[str]) -> dict[str, object]:
        out = self._run(args)
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as e:
            raise RegctlError(f"invalid JSON from regctl {' '.join(args)}: {e}") from e
        if not isinstance(payload, dict):
            raise RegctlError(f"expected JSON object from regctl {' '.join(args)}: {payload!r}")
        return payload

    def _run(self, args: list[str]) -> str:
        try:
            r = subprocess.run(  # noqa: S603
                [self._bin, *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RegctlError(str(e)) from e
        if r.returncode != 0:
            raise RegctlError(f"regctl {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout
