"""Pure coverage predicate: does an image carry knock's provenance stamp? (roadmap ④)

Sibling of `stamp.py` (which WRITES the stamp); this READS it back to answer the
coverage-gap question. Pure — no I/O.
"""

from __future__ import annotations

BASE_DIGEST_KEY = "org.opencontainers.image.base.digest"


def is_stamped(annotations: dict[str, str], *, prefix: str) -> bool:
    """True iff the image carries knock's provenance lineage.

    With a non-empty `prefix` (default "io.knock"), the definitive knock signal is the
    namespaced lineage key `{prefix}.policy`. With an empty prefix, knock emits only
    OCI-standard keys, so fall back to the `base.digest` idempotency key knock always
    writes. (base.digest is OCI-standard, not knock-exclusive — the empty-prefix path is
    a documented heuristic; see the spec.)
    """
    if prefix:
        return f"{prefix}.policy" in annotations
    return BASE_DIGEST_KEY in annotations
