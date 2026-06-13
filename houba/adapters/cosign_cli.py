"""Wrapper subprocess autour de cosign : signe une attestation in-toto (DSSE) et
l'attache comme referrer OCI au digest sujet.

Fail-fast comme regctl/buildctl (CLAUDE.md : aucune logique de retry dans les
adapters — cosign gère ses propres retries réseau en interne). Le modèle de
confiance (keyless | kms | key) est une *configuration* du même port.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from houba.config import AttestSettings
from houba.errors import CosignError
from houba.ports.attestor import AttestationRef

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}(?![0-9a-f])")


class CosignAdapter:
    def __init__(self, config: AttestSettings, binary: str | None = None) -> None:
        self._config = config
        # Résolution différée (cf. buildkit/regctl) : ne bloque pas la construction
        # du Container dans un environnement sans cosign.
        if binary is not None:
            if not Path(binary).is_file():
                raise CosignError(f"cosign binary not found: {binary}")
            self._bin: str | None = binary
        else:
            self._bin = None

    def _resolve(self) -> str:
        if self._bin is not None:
            return self._bin
        resolved = shutil.which("cosign")
        if not resolved:
            raise CosignError("cosign binary not found in PATH")
        self._bin = resolved
        return self._bin

    def _signing_args(self) -> list[str]:
        cfg = self._config
        args: list[str] = []
        if cfg.signer in ("kms", "key"):
            args += ["--key", cfg.key_ref]
        elif cfg.fulcio_url:  # keyless
            args += ["--fulcio-url", cfg.fulcio_url]
        # Transparency log: a URL => upload there; blank => no log entry (air-gapped).
        if cfg.rekor_url:
            args += ["--rekor-url", cfg.rekor_url]
        else:
            args += ["--tlog-upload=false"]
        return args

    def attest(self, subject_ref: str, statement: dict[str, Any]) -> AttestationRef:
        predicate_type = str(statement.get("predicateType", ""))
        predicate = statement.get("predicate", {})
        with tempfile.TemporaryDirectory(prefix="houba-attest-") as tmp:
            pred_path = Path(tmp) / "predicate.json"
            pred_path.write_text(json.dumps(predicate, sort_keys=True))
            args = [
                "attest",
                "--yes",
                "--type",
                predicate_type,
                "--predicate",
                str(pred_path),
                *self._signing_args(),
                subject_ref,
            ]
            try:
                r = subprocess.run(  # noqa: S603
                    [self._resolve(), *args],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                raise CosignError(str(e)) from e
        if r.returncode != 0:
            raise CosignError(f"cosign attest failed: {r.stderr.strip()}")
        # Best-effort: surface the pushed attestation digest if cosign printed one.
        m = _DIGEST_RE.search(r.stderr) or _DIGEST_RE.search(r.stdout)
        return AttestationRef(
            predicate_type=predicate_type,
            referrer_digest=m.group(0) if m else "",
        )
