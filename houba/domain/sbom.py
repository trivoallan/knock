"""SBOM referrer facts (sibling of scan/summary.py): the format → OCI media-type
mapping and the `{prefix}.sbom.*` annotation map for an attached SBOM referrer.

Pure: no I/O, no config. The artifact-type used to attach an SBOM referrer is its
media type (so `list_referrers(ref, "application/spdx+json")` finds it).
"""

from __future__ import annotations

from datetime import datetime

from houba.errors import UnknownFormatError

# syft output format name → OCI media type (also used as the referrer artifactType).
FORMAT_MEDIA_TYPES: dict[str, str] = {
    "spdx-json": "application/spdx+json",
    "cyclonedx-json": "application/vnd.cyclonedx+json",
}


def media_type_for(fmt: str) -> str:
    """Map a syft format name to its OCI media type; raise on an unknown format."""
    try:
        return FORMAT_MEDIA_TYPES[fmt]
    except KeyError:
        raise UnknownFormatError(
            f"unknown SBOM format {fmt!r}; known: {sorted(FORMAT_MEDIA_TYPES)}"
        ) from None


def build_sbom_annotations(
    *,
    prefix: str,
    subject_digest: str,
    fmt: str,
    tool: str,
    tool_version: str,
    timestamp: datetime,
) -> dict[str, str]:
    """The `{prefix}.sbom.*` annotation map for the referrer manifest.

    Honors an empty prefix (⇒ no annotations), mirroring stamp.py / scan/summary.py.
    """
    if not prefix:
        return {}
    out: dict[str, str] = {
        f"{prefix}.sbom.tool": tool,
        f"{prefix}.sbom.format": fmt,
        f"{prefix}.sbom.timestamp": timestamp.isoformat(),
        f"{prefix}.sbom.subject": subject_digest,
    }
    if tool_version:
        out[f"{prefix}.sbom.tool.version"] = tool_version
    return out
