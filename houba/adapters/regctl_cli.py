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
        # Résolution différée : on valide seulement si binary explicite est fourni.
        # La résolution PATH se fait au premier appel (lazy) pour ne pas bloquer
        # la construction du Container dans des environnements sans regctl.
        if binary is not None:
            if not Path(binary).is_file():
                raise RegctlError(f"regctl binary not found: {binary}")
            self._bin: str | None = binary
        else:
            self._bin = None

    def _resolve(self) -> str:
        if self._bin is not None:
            return self._bin
        resolved = shutil.which("regctl")
        if not resolved:
            raise RegctlError("regctl binary not found in PATH")
        self._bin = resolved
        return self._bin

    def list_tags(self, repo_ref: str) -> list[str]:
        try:
            out = self._run(["tag", "ls", repo_ref])
        except RegctlError as e:
            # A never-pushed repo → dist-spec NAME_UNKNOWN; that means "no tags", not a
            # hard error (else the first reconcile of an empty mirror would always fail).
            msg = str(e).lower()
            if "name_unknown" in msg or "not known to registry" in msg:
                return []
            raise
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

    def copy(self, src_ref: str, dst_ref: str) -> None:
        self._run(["image", "copy", src_ref, dst_ref])

    def annotate(self, image_ref: str, annotations: dict[str, str]) -> None:
        args = ["image", "mod", image_ref, "--replace"]
        for key, value in annotations.items():
            args += ["--annotation", f"{key}={value}"]
        self._run(args)

    def delete_tag(self, image_ref: str) -> None:
        self._run(["tag", "rm", image_ref])

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

    def configure_registry(self, host: str, *, tls_verify: bool, ca_cert: str | None) -> None:
        args = ["registry", "set", host, "--tls", "enabled" if tls_verify else "disabled"]
        if ca_cert:
            args += ["--cacert", ca_cert]
        self._run(args)

    def login(self, host: str, *, username: str, password: str, tls_verify: bool) -> None:
        args = ["registry", "login", "--user", username, "--pass-stdin"]
        if not tls_verify:
            args += ["--tls", "disabled"]
        args.append(host)
        self._run(args, stdin=password)

    def _run(self, args: list[str], *, stdin: str | None = None) -> str:
        try:
            r = subprocess.run(  # noqa: S603
                [self._resolve(), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
                input=stdin,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RegctlError(str(e)) from e
        if r.returncode != 0:
            raise RegctlError(f"regctl {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout
