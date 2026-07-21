"""SBOM referrer facts (sibling of scan/summary.py): the format → OCI media-type
mapping and the `{prefix}.sbom.*` annotation map for an attached SBOM referrer.

Pure: no I/O, no config. The artifact-type used to attach an SBOM referrer is its
media type (so `list_referrers(ref, "application/spdx+json")` finds it).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from knock.errors import UnknownFormatError

# syft output format name → OCI media type (also used as the referrer artifactType).
FORMAT_MEDIA_TYPES: dict[str, str] = {
    "spdx-json": "application/spdx+json",
    "cyclonedx-json": "application/vnd.cyclonedx+json",
}

# syft output format name → canonical in-toto predicateType for the signed SBOM
# attestation. These are cosign's built-in document types (shorthands `spdxjson` /
# `cyclonedx`), so a downstream `cosign verify-attestation --type spdxjson` matches.
SBOM_PREDICATE_TYPES: dict[str, str] = {
    "spdx-json": "https://spdx.dev/Document",
    "cyclonedx-json": "https://cyclonedx.org/bom",
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


def build_sbom_statement(
    *, subject_name: str, subject_digest: str, fmt: str, content: bytes
) -> dict[str, Any]:
    """Wrap an SBOM document as a signing-ready in-toto v1 Statement.

    The predicate IS the SBOM (parsed); the predicateType is the canonical
    document type for `fmt`, so the signed attestation verifies with stock
    `cosign verify-attestation --type spdxjson|cyclonedx`. Pure: the byte-exact
    SBOM still lives in the raw referrer. Raises UnknownFormatError on an
    unrecognized format.
    """
    try:
        predicate_type = SBOM_PREDICATE_TYPES[fmt]
    except KeyError:
        raise UnknownFormatError(
            f"unknown SBOM format {fmt!r}; known: {sorted(SBOM_PREDICATE_TYPES)}"
        ) from None
    algo, sep, value = subject_digest.partition(":")
    digest = {algo: value} if sep else {"sha256": algo}
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": subject_name, "digest": digest}],
        "predicateType": predicate_type,
        "predicate": json.loads(content),
    }
