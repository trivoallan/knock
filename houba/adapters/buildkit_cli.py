"""Wrapper subprocess autour de buildctl (BuildKit) pour build + push d'images OCI."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from houba.errors import BuildkitError
from houba.ports.image_builder import BuildRequest


class BuildkitAdapter:
    def __init__(self, binary: str | None = None) -> None:
        # Résolution différée : on valide seulement si binary explicite est fourni.
        # La résolution PATH se fait au premier appel (lazy) pour ne pas bloquer
        # la construction du Container dans des environnements sans buildctl.
        if binary is not None:
            if not Path(binary).is_file():
                raise BuildkitError(f"buildctl binary not found: {binary}")
            self._bin: str | None = binary
        else:
            self._bin = None

    def _resolve(self) -> str:
        if self._bin is not None:
            return self._bin
        resolved = shutil.which("buildctl")
        if not resolved:
            raise BuildkitError("buildctl binary not found in PATH")
        self._bin = resolved
        return self._bin

    def build_and_push(self, request: BuildRequest) -> None:
        args = [
            "build",
            "--frontend=dockerfile.v0",
            f"--local=context={request.context_dir}",
            f"--local=dockerfile={request.dockerfile_path.parent}",
            f"--opt=filename={request.dockerfile_path.name}",
            f"--output=type=image,name={request.image_ref},push=true",
        ]
        if request.platform:
            args.append(f"--opt=platform={request.platform}")
        for k, v in sorted(request.build_args.items()):
            args.append(f"--opt=build-arg:{k}={v}")
        try:
            r = subprocess.run(  # noqa: S603
                [self._resolve(), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=1800,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise BuildkitError(str(e)) from e
        if r.returncode != 0:
            raise BuildkitError(f"buildctl {' '.join(args)} failed: {r.stderr.strip()}")
