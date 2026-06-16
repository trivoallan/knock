#!/usr/bin/env python3
"""Generate the policy + config reference from the Pydantic schemas.

For each schema this writes a `*.schema.json` (the published, machine-readable
contract — editor/CI validation) and renders a human `*.md` page with
`json-schema-for-humans`. Both are committed; CI re-runs this and fails on any
diff, so the reference can never drift from the models.

Run via `make reference` (uses the `docs` dependency group).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from json_schema_for_humans.generate import generate_from_filename
from json_schema_for_humans.generation_configuration import GenerationConfiguration

from houba.config import settings_json_schema
from houba.domain.mirror_policy import mirror_policy_json_schema

OUT = Path(__file__).resolve().parent.parent / "docs" / "reference"

# slug -> (schema builder, page title, sidebar position).
# The position makes mirror-policy precede config in the Docusaurus sidebar (Reference
# section); without it Docusaurus falls back to alphabetical (config first).
SCHEMAS: dict[str, tuple[Callable[[], dict[str, Any]], str, int]] = {
    "mirror-policy": (mirror_policy_json_schema, "MirrorPolicy", 1),
    "config": (settings_json_schema, "houba configuration (HOUBA_*)", 2),
}

# with_footer=False drops the "Generated on <date>" line, so the Markdown is a
# pure function of the schema (deterministic ⇒ the CI drift check is meaningful).
CONFIG = GenerationConfiguration(
    template_name="md",
    with_footer=False,
    show_toc=True,
    deprecated_from_description=True,
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, (schema_fn, title, position) in SCHEMAS.items():
        schema = schema_fn()
        schema["title"] = title
        json_path = OUT / f"{slug}.schema.json"
        json_path.write_text(json.dumps(schema, indent=2) + "\n")
        md_path = OUT / f"{slug}.md"
        generate_from_filename(json_path, str(md_path), config=CONFIG)
        # json-schema-for-humans has no front-matter hook, so prepend the Docusaurus
        # sidebar position after rendering (front matter is honored in CommonMark too).
        md_path.write_text(f"---\nsidebar_position: {position}\n---\n\n{md_path.read_text()}")
        print(f"wrote {json_path.name} + {slug}.md")


if __name__ == "__main__":
    main()
