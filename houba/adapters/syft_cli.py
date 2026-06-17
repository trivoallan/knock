"""subprocess wrapper around syft: generate package-level SBOM(s) for a placed image.

Fail-fast like the other adapters (CLAUDE.md: no retry logic). Registry auth/TLS
travel through a syft config file (JSON is valid YAML) so the adapter never touches
os.environ — config.py stays the sole reader. Binary resolution is lazy (cf.
buildkit/cosign): constructing the Container is not blocked where syft is absent.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from houba.domain.sbom import media_type_for
from houba.domain.scan.refs import registry_host
from houba.errors import SyftError
from houba.ports.sbom import SbomDocument


class SyftAdapter:
    def __init__(self, binary: str | None = None) -> None:
        if binary is not None:
            if not Path(binary).is_file():
                raise SyftError(f"syft binary not found: {binary}")
            self._bin: str | None = binary
        else:
            self._bin = None

    def _resolve(self) -> str:
        if self._bin is not None:
            return self._bin
        resolved = shutil.which("syft")
        if not resolved:
            raise SyftError("syft binary not found in PATH")
        self._bin = resolved
        return self._bin

    def _registry_config(
        self,
        image_ref: str,
        *,
        tls_verify: bool,
        username: str | None,
        password: str | None,
        ca_cert: str | None,
    ) -> dict[str, Any]:
        reg: dict[str, Any] = {}
        if not tls_verify:
            reg["insecure-use-http"] = True
            reg["insecure-skip-tls-verify"] = True
        if ca_cert:
            reg["ca-cert"] = ca_cert
        if username and password:
            reg["auth"] = [
                {
                    "authority": registry_host(image_ref),
                    "username": username,
                    "password": password,
                }
            ]
        return {"registry": reg}

    def generate(
        self,
        image_ref: str,
        formats: list[str],
        *,
        tls_verify: bool = True,
        username: str | None = None,
        password: str | None = None,
        ca_cert: str | None = None,
    ) -> list[SbomDocument]:
        # Validate formats up front (raises UnknownFormatError before any subprocess).
        media_types = {fmt: media_type_for(fmt) for fmt in formats}
        with tempfile.TemporaryDirectory(prefix="houba-sbom-") as tmp:
            # JSON is valid YAML; the .yaml extension routes viper to its YAML parser.
            cfg = Path(tmp) / "syft.yaml"
            cfg.write_text(
                json.dumps(
                    self._registry_config(
                        image_ref,
                        tls_verify=tls_verify,
                        username=username,
                        password=password,
                        ca_cert=ca_cert,
                    )
                )
            )
            outputs: list[tuple[str, Path]] = []
            args = ["scan", f"registry:{image_ref}", "-c", str(cfg)]
            for fmt in formats:
                path = Path(tmp) / f"sbom-{fmt}.json"
                args += ["-o", f"{fmt}={path}"]
                outputs.append((fmt, path))
            try:
                r = subprocess.run(  # noqa: S603
                    [self._resolve(), *args],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                raise SyftError(str(e)) from e
            if r.returncode != 0:
                raise SyftError(f"syft {' '.join(args)} failed: {r.stderr.strip()}")
            return [
                SbomDocument(format=fmt, media_type=media_types[fmt], content=path.read_bytes())
                for fmt, path in outputs
            ]
