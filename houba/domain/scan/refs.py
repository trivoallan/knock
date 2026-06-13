"""Pure OCI-reference helpers for the attach path. No I/O."""

from __future__ import annotations


def pin_to_digest(ref: str, digest: str) -> str:
    """Return `ref` rewritten to point at `digest` (drops any existing tag/digest).

    Handles a registry host with a port (the colon before the last `/` is not a tag
    separator) and an already-digest-pinned ref.
    """
    base = ref.split("@", 1)[0]
    slash = base.rfind("/")
    colon = base.rfind(":")
    if colon > slash:  # a `:tag` after the last path separator
        base = base[:colon]
    return f"{base}@{digest}"
