"""Resolve derived moving-tag aliases from templates (spec §5.2).

A template is a string with placeholders: `{major}` / `{minor}` / `{patch}`
(semver components), or `{name}` (a named capture group of the include regex).
`render_template` fills one template for one tag; `resolve_aliases` groups the
imported tags by rendered value and points each alias at the highest in its group.
"""

from __future__ import annotations

import re

from houba.domain.semver import parse_semver

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class _Unfillable(Exception):
    """Raised internally when a placeholder cannot be filled for a tag."""


def render_template(template: str, tag: str, include_regex: str | None) -> str | None:
    """Render `template` for `tag`, or None if a placeholder cannot be filled."""
    semver = parse_semver(tag)
    captures: dict[str, str] = {}
    if include_regex is not None:
        m = re.match(include_regex, tag)
        if m is not None:
            captures = {k: v for k, v in m.groupdict().items() if v is not None}

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in ("major", "minor", "patch"):
            if semver is None:
                raise _Unfillable
            return str(getattr(semver, key))
        if key in captures:
            return captures[key]
        raise _Unfillable

    try:
        return _PLACEHOLDER.sub(_sub, template)
    except _Unfillable:
        return None
