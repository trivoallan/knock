"""Port: evaluate an SBOM for vulnerabilities, returning SARIF.

houba runs the evaluator (unlike attach, which ingests a report) but owns no CVE
database — the adapter shells a configured command. Like every port: a
typing.Protocol + a frozen data model, never importing from houba.adapters.*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from houba.ports.sbom import SbomDocument


@dataclass(frozen=True)
class ScanResult:
    sarif: bytes  # the SARIF (2.1.0) report, fed to the existing SarifMapper
    db_version: str | None = None  # vuln-DB version if the evaluator surfaces it; else omitted


class VulnEvaluatorPort(Protocol):
    def evaluate(self, sbom: SbomDocument) -> ScanResult:
        """Run the configured evaluator on `sbom`; return its SARIF (and DB version if known)."""
        ...
