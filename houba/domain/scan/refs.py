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


def registry_host(ref: str) -> str | None:
    """Return the leading registry-host component of an OCI ref, or None when none.

    A ref's first path segment is a registry host only when it looks like one:
    it contains a '.' (DNS name), a ':' (host:port), or is exactly 'localhost'.
    Otherwise the leading segment is a namespace and the host is the implicit
    default registry (docker.io) — which the roster never holds, so we return
    None and the caller falls back to ambient config.
    """
    head = ref.split("/", 1)[0]
    if "/" not in ref:
        return None
    if "." in head or ":" in head or head == "localhost":
        return head
    return None
