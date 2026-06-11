"""Resolve derived moving-tag aliases from templates (spec §5.2).

A template is a string with placeholders: `{major}` / `{minor}` / `{patch}`
(semver components), or `{name}` (a named capture group of the include regex).
`render_template` fills one template for one tag; `resolve_aliases` groups the
imported tags by rendered value and points each alias at the highest in its group.
"""

from __future__ import annotations

import re

from houba.domain.semver import parse_semver, sort_semver

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class _Unfillable(Exception):
    """Raised internally when a placeholder cannot be filled for a tag."""


def render_template(template: str, tag: str, include_regex: str | None) -> str | None:
    """Render `template` for `tag`, or None if a placeholder cannot be filled."""
    semver = parse_semver(tag)
    captures: dict[str, str] = {}
    if include_regex is not None:
        m = re.search(include_regex, tag)
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


def _highest(tags: list[str]) -> str:
    """Highest tag: semver descending if the top is semver, else lexical max."""
    by_semver = sort_semver(tags, reverse=True)
    if parse_semver(by_semver[0]) is not None:
        return by_semver[0]
    return max(tags)


def resolve_aliases(
    templates: list[str],
    concrete_tags: list[str],
    include_regex: str | None = None,
) -> dict[str, str]:
    """Map each derived alias to the concrete tag it should point at."""
    aliases: dict[str, str] = {}
    for template in templates:
        groups: dict[str, list[str]] = {}
        if template == "latest":
            if concrete_tags:
                groups["latest"] = list(concrete_tags)
        else:
            for tag in concrete_tags:
                rendered = render_template(template, tag, include_regex)
                if rendered is not None:
                    groups.setdefault(rendered, []).append(tag)
        for alias_name, members in groups.items():
            aliases[alias_name] = _highest(members)
    return aliases
