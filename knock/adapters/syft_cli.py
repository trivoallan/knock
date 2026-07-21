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

from knock.domain.sbom import media_type_for
from knock.domain.scan.refs import registry_host
from knock.errors import SyftError
from knock.ports.sbom import SbomDocument


class SyftAdapter:
    def __init__(self, binary: str | None = None) -> None:
        self._version: str | None = None  # cached syft version (best-effort, resolved on first use)
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

    def _tool_version(self) -> str:
        # Best-effort, cached: a missing/unparseable version must not fail SBOM generation
        # (the SBOM itself is the product; the version is a provenance nicety).
        if self._version is not None:
            return self._version
        self._version = ""
        try:
            r = subprocess.run(  # noqa: S603
                [self._resolve(), "version", "-o", "json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0:
                self._version = str(json.loads(r.stdout).get("version", ""))
        except (OSError, subprocess.TimeoutExpired, ValueError):
            self._version = ""
        return self._version

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
        with tempfile.TemporaryDirectory(prefix="knock-sbom-") as tmp:
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
            version = self._tool_version()
            return [
                SbomDocument(
                    format=fmt,
                    media_type=media_types[fmt],
                    content=path.read_bytes(),
                    tool_version=version,
                )
                for fmt, path in outputs
            ]
