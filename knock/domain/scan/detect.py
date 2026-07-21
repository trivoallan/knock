"""Detect / resolve the scan-report format from content (with a --format override). Pure."""

from __future__ import annotations

import json
from typing import Any

from knock.domain.scan.formats.registry import DEFAULT_REGISTRY, Registry
from knock.errors import UnknownFormatError


def detect_format(report_bytes: bytes, registry: Registry = DEFAULT_REGISTRY) -> str | None:
    """Sniff the format by asking each registered mapper to recognize the parsed JSON.

    Returns the format name, or None if the bytes are not JSON / not recognized.
    """
    try:
        doc: Any = json.loads(report_bytes)
    except json.JSONDecodeError:
        return None
    if not isinstance(doc, dict):
        return None
    for mapper in registry.mappers():
        if mapper.recognizes(doc):
            return mapper.name
    return None


def resolve_format(
    report_bytes: bytes, override: str | None, registry: Registry = DEFAULT_REGISTRY
) -> str:
    """Validate an explicit --format, else auto-detect. Raise UnknownFormatError on failure."""
    if override is not None:
        if override not in registry.names():
            raise UnknownFormatError(
                f"unknown scan format {override!r}; allowed: {sorted(registry.names())}"
            )
        return override
    detected = detect_format(report_bytes, registry)
    if detected is None:
        raise UnknownFormatError(
            f"could not detect scan format; pass --format (one of {sorted(registry.names())})"
        )
    return detected
