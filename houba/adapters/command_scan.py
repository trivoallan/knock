"""Generic vuln-evaluator adapter: run an operator-supplied command, SBOM in / SARIF out.

Contract (HOUBA_SCAN_EVALUATOR_CMD): a command template containing `{sbom}`, replaced
with a temp file holding the SBOM bytes; SARIF (2.1.0) is read from stdout.
  exit 0 = answered; non-zero / timeout / empty stdout => ScanEvaluatorError (fail-closed).
houba stays on its subprocess-or-stdlib grain — no scanner SDK, no CVE DB in-tree.
"""

from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path

from houba.errors import ScanEvaluatorError
from houba.ports.sbom import SbomDocument
from houba.ports.vuln import ScanResult


class CommandScanAdapter:
    def __init__(self, command: str, timeout: int = 600) -> None:
        if "{sbom}" not in command:
            raise ScanEvaluatorError("HOUBA_SCAN_EVALUATOR_CMD must contain the {sbom} placeholder")
        self._command = command
        self._timeout = timeout

    def evaluate(self, sbom: SbomDocument) -> ScanResult:
        with tempfile.TemporaryDirectory(prefix="houba-scan-") as tmp:
            path = Path(tmp) / "sbom.json"
            path.write_bytes(sbom.content)
            argv = shlex.split(self._command.format(sbom=str(path)))
            try:
                r = subprocess.run(  # noqa: S603
                    argv, check=False, capture_output=True, text=True, timeout=self._timeout
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                raise ScanEvaluatorError(str(e)) from e
            if r.returncode != 0:
                raise ScanEvaluatorError(f"evaluator failed: {r.stderr.strip()}")
            if not r.stdout.strip():
                raise ScanEvaluatorError("evaluator produced no SARIF on stdout")
            return ScanResult(sarif=r.stdout.encode())
