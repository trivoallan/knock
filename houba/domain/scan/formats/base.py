"""The per-format scan-report mapper contract. Pure: report bytes -> ScanSummary."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from houba.domain.scan.summary import ScanSummary


class ScanFormatMapper(ABC):
    """One pluggable scan-report format. Pure: parse + summarize, no I/O."""

    name: ClassVar[str]
    report_media_type: ClassVar[str]
    fact_keys: ClassVar[tuple[str, ...]]

    @abstractmethod
    def recognizes(self, doc: dict[str, Any]) -> bool:
        """True if a parsed JSON document looks like this format (for auto-detection)."""

    @abstractmethod
    def summarize(self, report_bytes: bytes) -> ScanSummary:
        """Parse the raw report and return the normalized summary.

        Raise ScanReportError on bad input.
        """
