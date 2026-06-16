"""subprocess wrapper around buildctl (BuildKit) for OCI image build and push."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from houba.errors import BuildkitError
from houba.ports.image_builder import BuildRequest


class BuildkitAdapter:
    def __init__(self, binary: str | None = None) -> None:
        # Lazy resolution: only validate if an explicit binary is provided.
        # PATH resolution happens on the first call (lazy) so that constructing
        # the Container is not blocked in environments without buildctl.
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
        output = f"--output=type=image,name={request.image_ref},push=true"
        if not request.tls_verify:
            # Plain-HTTP registry: tell BuildKit's pusher to skip TLS, mirroring
            # regctl's `--tls disabled`. Without it the push speaks HTTPS to an
            # HTTP registry and fails ("server gave HTTP response to HTTPS client").
            output += ",registry.insecure=true"
        args = [
            "build",
            "--frontend=dockerfile.v0",
            f"--local=context={request.context_dir}",
            f"--local=dockerfile={request.dockerfile_path.parent}",
            f"--opt=filename={request.dockerfile_path.name}",
            output,
        ]
        if request.platform:
            args.append(f"--opt=platform={request.platform}")
        if request.provenance:
            # BuildKit emits + attaches its own slsa.dev/provenance/v1 referrer at push;
            # houba only enables it (mode=max captures the full build trace).
            args.append("--opt=attest:provenance=mode=max")
        if request.sbom:
            # BuildKit generates an SPDX SBOM via its syft-based scanner and attaches it
            # at push (an index attestation manifest); houba only enables it.
            args.append("--opt=attest:sbom=true")
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
