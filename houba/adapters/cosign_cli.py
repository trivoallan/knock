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
from houba.domain.attestation import build_signing_config
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

    def _key_args(self) -> list[str]:
        # A key reference is NOT a "service URL", so it stays a flag (kms/key).
        # keyless emits no --key: the identity comes from the signing-config / ambient OIDC.
        cfg = self._config
        if cfg.signer in ("kms", "key"):
            return ["--key", cfg.key_ref]
        return []

    def attest(self, subject_ref: str, statement: dict[str, Any]) -> AttestationRef:
        cfg = self._config
        predicate_type = str(statement.get("predicateType", ""))
        predicate = statement.get("predicate", {})
        signing_config = build_signing_config(
            fulcio_url=cfg.fulcio_url,
            rekor_url=cfg.rekor_url,
            operator=cfg.builder_id or "houba",
        )
        with tempfile.TemporaryDirectory(prefix="houba-attest-") as tmp:
            pred_path = Path(tmp) / "predicate.json"
            pred_path.write_text(json.dumps(predicate, sort_keys=True))
            scfg_path = Path(tmp) / "signing-config.json"
            scfg_path.write_text(json.dumps(signing_config, sort_keys=True))
            args = [
                "attest",
                "--yes",
                "--type",
                predicate_type,
                "--predicate",
                str(pred_path),
                *self._key_args(),
                "--signing-config",
                str(scfg_path),
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
        m = _DIGEST_RE.search(r.stderr) or _DIGEST_RE.search(r.stdout)
        return AttestationRef(
            predicate_type=predicate_type,
            referrer_digest=m.group(0) if m else "",
        )
