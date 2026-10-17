#!/usr/bin/env python3
"""Generate the policy + config + CLI reference.

The policy and scan-predicate pages come from the Pydantic schemas: for each, this writes
a `*.schema.json` (the published, machine-readable contract — editor/CI validation)
and renders a human `*.md` page with `json-schema-for-humans` under docs/reference/schemas/.
The configuration page is a custom Markdown table of KNOCK_* vars derived from the
Settings model. The CLI page is rendered from the live Typer app with Typer's own
Markdown generator.
Everything is committed; CI re-runs this and fails on any diff, so the reference
can never drift from the models or the CLI definition.

Run via `make reference` (uses the `docs` dependency group).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
import typer.main
from typer.cli import get_docs_for_click

from knock.cli.main import app as cli_app
from knock.config import Settings, settings_json_schema
from knock.domain.gate import (
    applied_operations_json_schema,
    reconcile_plan_json_schema,
    staged_rebuilds_json_schema,
)
from knock.domain.mirror_policy import mirror_policy_json_schema
from knock.domain.scan.attestation import scan_predicate_json_schema
from knock.use_cases.audit import coverage_report_json_schema
from knock.use_cases.lint import lint_report_json_schema

OUT = Path(__file__).resolve().parent.parent / "docs" / "reference"
SCHEMAS_OUT = OUT / "schemas"

# slug -> (schema builder, page title).
# json-schema-for-humans marks each heading with an HTML anchor (`## <a name="x"></a>Title`)
# and links its TOC to `#x`; GitHub keeps those anchors, so the pages are written as rendered.
SCHEMAS: dict[str, tuple[Any, str]] = {
    "mirror-policy": (mirror_policy_json_schema, "MirrorPolicy"),
    "scan-predicate": (scan_predicate_json_schema, "Scan attestation predicate (/scan/v1)"),
    "reconcile-plan": (reconcile_plan_json_schema, "ReconcilePlan (the gate's plan file)"),
    "staged-rebuilds": (
        staged_rebuilds_json_schema,
        "StagedRebuilds (the remediated images held in staging)",
    ),
    "applied-operations": (
        applied_operations_json_schema,
        "AppliedOperations (what --apply-plan did with each operation)",
    ),
    "coverage-report": (coverage_report_json_schema, "CoverageReport (knock audit JSON output)"),
    "lint-report": (lint_report_json_schema, "LintReport (knock lint output)"),
}


def _write_schemas() -> None:
    """Render mirror-policy and scan-predicate schemas into docs/reference/schemas/."""
    # json-schema-for-humans is a docs-only dependency; import it lazily so the rest of
    # this module (the config-table generator) imports fine without it — the CI test job
    # syncs without the `docs` group, and tests import `_write_config_table` directly.
    from json_schema_for_humans.generate import generate_from_filename
    from json_schema_for_humans.generation_configuration import GenerationConfiguration

    # with_footer=False drops the "Generated on <date>" line, so the Markdown is a pure
    # function of the schema (deterministic => the CI drift check is meaningful).
    # show_breadcrumbs=False + collapse_long_descriptions=True cut the noisy
    # "anyOf > item N" breadcrumb tree in the rendered output.
    config = GenerationConfiguration(
        template_name="md",
        with_footer=False,
        show_toc=True,
        deprecated_from_description=True,
        show_breadcrumbs=False,
        collapse_long_descriptions=True,
    )

    SCHEMAS_OUT.mkdir(parents=True, exist_ok=True)
    for slug, (schema_fn, title) in SCHEMAS.items():
        schema = schema_fn()
        schema["title"] = title
        json_path = SCHEMAS_OUT / f"{slug}.schema.json"
        json_path.write_text(json.dumps(schema, indent=2) + "\n")
        md_path = SCHEMAS_OUT / f"{slug}.md"
        generate_from_filename(json_path, str(md_path), config=config)
        print(f"wrote schemas/{slug}.schema.json + schemas/{slug}.md")


def _type_label(prop: dict[str, Any], defs: dict[str, Any] | None = None) -> str:
    """Derive a coarse type label from a JSON Schema property entry."""
    # Resolve $ref via $defs to handle enum-backed fields (e.g. DeletionMode)
    if "$ref" in prop and defs is not None:
        ref_name = prop["$ref"].split("/")[-1]
        resolved = defs.get(ref_name, {})
        return _type_label(resolved, defs)
    # Unwrap anyOf [X, {"type": "null"}] (Optional[X])
    if "anyOf" in prop:
        non_null = [v for v in prop["anyOf"] if v.get("type") != "null" and v != {"type": "null"}]
        if len(non_null) == 1:
            return _type_label(non_null[0], defs)
        # Multiple non-null alternatives — treat as JSON object
        return "JSON object"
    t = prop.get("type")
    if t == "string":
        return "string"
    if t == "boolean":
        return "boolean"
    if t == "integer":
        return "integer"
    if t == "array":
        return "JSON list"
    if t == "object":
        return "JSON object"
    # $ref without defs or allOf
    if "$ref" in prop or "allOf" in prop:
        return "JSON object"
    return "JSON object"


def _default_repr(name: str, field: Any) -> str:
    """Render the real default for a Settings field as a backtick-wrapped string."""
    if field.default_factory is not None:  # type: ignore[misc]
        val = field.default_factory()  # type: ignore[misc]
    else:
        val = field.default

    if val is None:
        return "`(unset)`"
    if isinstance(val, bool):
        return f"`{'true' if val else 'false'}`"
    if isinstance(val, dict) and len(val) == 0:
        return "`{}`"
    if isinstance(val, list):
        return f"`{json.dumps(val)}`"
    if isinstance(val, Path):
        return f"`{val}`"
    # Enum
    if hasattr(val, "value"):
        return f"`{val.value}`"
    if val == "":
        return "`(empty)`"
    return f"`{val}`"


def _write_config_table(out_dir: Path) -> None:
    """Write docs/reference/configuration.md and docs/reference/config.schema.json."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Always emit the machine-readable contract (published schema)
    schema = settings_json_schema()
    schema["title"] = "knock configuration (KNOCK_*)"
    json_path = out_dir / "config.schema.json"
    json_path.write_text(json.dumps(schema, indent=2) + "\n")
    print("wrote config.schema.json")

    properties = schema.get("properties", {})
    defs = schema.get("$defs", {})

    rows: list[str] = []
    for field_name, field_info in Settings.model_fields.items():
        var = f"KNOCK_{field_name.upper()}"
        prop = properties.get(field_name, {})
        type_label = _type_label(prop, defs)
        default = _default_repr(field_name, field_info)
        # Escape pipe characters in description so the Markdown table isn't broken
        desc = (field_info.description or "").replace("|", r"\|")
        rows.append(f"| `{var}` | {type_label} | {default} | {desc} |")

    table_header = "| Variable | Type | Default | Description |\n| --- | --- | --- | --- |"
    table = table_header + "\n" + "\n".join(rows)

    intro = (
        "Each field is set as `KNOCK_<FIELD>` (the property name upper-cased). "
        "JSON-typed fields (`registries`, `transform_ca_certs`, `transform_package_mirrors`, "
        "`retention`) take a JSON value whose shape is documented in the "
        "[schemas](schemas/README.md) section. The machine-readable contract is "
        "[`config.schema.json`](config.schema.json)."
    )

    content = f"# Configuration\n\n{intro}\n\n{table}\n"
    (out_dir / "configuration.md").write_text(content)
    print("wrote configuration.md")


def _write_cli() -> None:
    """Render the CLI command reference from the live Typer app.

    Typer's own Markdown generator keeps the page a pure function of the CLI
    definition (commands, args, options, help strings), so the CI drift check
    covers it like the schema pages.
    """
    command = typer.main.get_command(cli_app)
    ctx = typer.Context(command, info_name="knock")
    body = get_docs_for_click(obj=command, ctx=ctx, name="knock", title="Command Line Interface")
    (OUT / "command-line-interface.md").write_text(f"{body.strip()}\n")
    print("wrote command-line-interface.md")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _write_schemas()
    _write_config_table(OUT)
    _write_cli()


if __name__ == "__main__":
    main()
