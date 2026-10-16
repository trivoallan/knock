"""OCI platform strings (`os/arch[/variant]`): validation, matching, comparison. Pure.

`arm64` without a variant is `arm64/v8` (the OCI image-index spec's default), so the two
spellings name one platform. A requested platform without a variant matches any variant of
its os/arch; one with a variant matches that variant only.
"""

from __future__ import annotations

from collections.abc import Iterable

PLATFORM_PATTERN = r"^[a-z0-9_]+/[a-z0-9_]+(/[a-z0-9_]+)?$"


def normalize(platform: str) -> str:
    """Canonical spelling: lowercase, `arm64/v8` folded into `arm64`."""
    p = platform.strip().lower()
    return p.removesuffix("/v8") if p.endswith("/arm64/v8") else p


def _carries(available: Iterable[str], wanted: str) -> bool:
    w = normalize(wanted)
    have = {normalize(a) for a in available}
    if w in have:
        return True
    # "linux/arm" asked, "linux/arm/v7" present: a variant-less request takes any variant.
    return w.count("/") == 1 and any(h.startswith(w + "/") for h in have)


def missing(available: Iterable[str], wanted: Iterable[str]) -> list[str]:
    """The requested platforms `available` does not carry, in request order."""
    have = list(available)
    return [w for w in wanted if not _carries(have, w)]


def same_set(a: Iterable[str], b: Iterable[str]) -> bool:
    return {normalize(p) for p in a} == {normalize(p) for p in b}
