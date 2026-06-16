#!/usr/bin/env python3
"""Generate the policy + config + CLI reference.

The policy and config pages come from the Pydantic schemas: for each, this writes
a `*.schema.json` (the published, machine-readable contract — editor/CI validation)
and renders a human `*.md` page with `json-schema-for-humans`. The CLI page is
rendered straight from the live Typer app with Typer's own Markdown generator.
Everything is committed; CI re-runs this and fails on any diff, so the reference
can never drift from the models or the CLI definition.

Run via `make reference` (uses the `docs` dependency group).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
import typer.main
from json_schema_for_humans.generate import generate_from_filename
from json_schema_for_humans.generation_configuration import GenerationConfiguration
from typer.cli import get_docs_for_click

from houba.cli.main import app as cli_app
from houba.config import settings_json_schema
from houba.domain.mirror_policy import mirror_policy_json_schema
from houba.domain.scan.attestation import scan_predicate_json_schema

OUT = Path(__file__).resolve().parent.parent / "docs" / "reference"

# slug -> (schema builder, page title, sidebar position).
# The position makes mirror-policy precede config in the Docusaurus sidebar (Reference
# section); without it Docusaurus falls back to alphabetical (config first).
SCHEMAS: dict[str, tuple[Callable[[], dict[str, Any]], str, int]] = {
    "mirror-policy": (mirror_policy_json_schema, "MirrorPolicy", 1),
    "config": (settings_json_schema, "houba configuration (HOUBA_*)", 2),
    "scan-predicate": (scan_predicate_json_schema, "Scan attestation predicate (/scan/v1)", 4),
}

# with_footer=False drops the "Generated on <date>" line, so the Markdown is a
# pure function of the schema (deterministic ⇒ the CI drift check is meaningful).
CONFIG = GenerationConfiguration(
    template_name="md",
    with_footer=False,
    show_toc=True,
    deprecated_from_description=True,
)

# json-schema-for-humans marks headings with HTML anchors (`## <a name="x"></a>Title`)
# and links its TOC to `#x`. Docusaurus derives heading ids from the *text* instead, so
# those `#x` links break. Rewrite each into a Docusaurus explicit heading id
# (`## Title {#x}`) so the in-page TOC and cross-references resolve.
_HEADING_ANCHOR = re.compile(r'^(#{1,6}) <a name="([^"]+)"></a>(.*)$', re.MULTILINE)


def _docusaurus_heading_ids(md: str) -> str:
    return _HEADING_ANCHOR.sub(r"\1 \3 {#\2}", md)


def _write_cli() -> None:
    """Render the CLI command reference from the live Typer app.

    Typer's own Markdown generator keeps the page a pure function of the CLI
    definition (commands, args, options, help strings), so the CI drift check
    covers it like the schema pages. Sidebar position 3 = after mirror-policy and
    config.
    """
    command = typer.main.get_command(cli_app)
    ctx = typer.Context(command, info_name="houba")
    body = get_docs_for_click(obj=command, ctx=ctx, name="houba", title="houba CLI")
    (OUT / "cli.md").write_text(f"---\nsidebar_position: 3\n---\n\n{body.strip()}\n")
    print("wrote cli.md")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, (schema_fn, title, position) in SCHEMAS.items():
        schema = schema_fn()
        schema["title"] = title
        json_path = OUT / f"{slug}.schema.json"
        json_path.write_text(json.dumps(schema, indent=2) + "\n")
        md_path = OUT / f"{slug}.md"
        generate_from_filename(json_path, str(md_path), config=CONFIG)
        body = _docusaurus_heading_ids(md_path.read_text())
        # json-schema-for-humans has no front-matter hook, so prepend the Docusaurus
        # sidebar position after rendering (front matter is honored in CommonMark too).
        md_path.write_text(f"---\nsidebar_position: {position}\n---\n\n{body}")
        print(f"wrote {json_path.name} + {slug}.md")
    _write_cli()


if __name__ == "__main__":
    main()
