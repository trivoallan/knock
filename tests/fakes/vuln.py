from __future__ import annotations

from houba.errors import ScanEvaluatorError
from houba.ports.sbom import SbomDocument
from houba.ports.vuln import ScanResult


class FakeVulnEvaluatorPort:
    """Return a seeded SARIF; journal every call. `fail=True` raises (fail-closed)."""

    def __init__(
        self,
        sarif: bytes = b'{"runs":[]}',
        *,
        db_version: str | None = None,
        fail: bool = False,
    ) -> None:
        self._sarif = sarif
        self._db_version = db_version
        self._fail = fail
        self.evaluated: list[SbomDocument] = []

    def evaluate(self, sbom: SbomDocument) -> ScanResult:
        self.evaluated.append(sbom)
        if self._fail:
            raise ScanEvaluatorError("fake evaluator failure")
        return ScanResult(sarif=self._sarif, db_version=self._db_version)
