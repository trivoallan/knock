"""Render a RunReport to a stream: `json` (machine contract) or `text` (human recap).

Result goes to stdout; the structlog journal goes to stderr. `--verbose` unfolds
targets/variants/operations under each policy."""

from __future__ import annotations

from typing import TextIO

from houba.use_cases.report import Operation, RunReport


def _op_line(op: Operation) -> str:
    src = f"  ⇐ {op.src_tag}" if op.src_tag else ""
    planned = "" if op.applied else "  (planned)"
    return f"        {op.kind:<9}{op.out_tag}{src}{planned}\n"


def render_report(report: RunReport, *, fmt: str, verbose: bool, stream: TextIO) -> None:
    if fmt == "json":
        stream.write(report.model_dump_json() + "\n")
        return

    for p in report.policies:
        if p.status == "failed":
            assert p.error is not None  # status=failed always carries an error
            stream.write(f"✗ {p.name}  FAILED: {p.error.type}: {p.error.message}\n")
        else:
            t = p.totals
            stream.write(
                f"✓ {p.name}  imported={t.imported} updated={t.updated} "
                f"deleted={t.deleted} aliased={t.aliased} skipped={t.skipped}\n"
            )
        if verbose:
            for tgt in p.targets:
                stream.write(f"    → {tgt.dest_repo}\n")
                for v in tgt.variants:
                    for op in v.operations:
                        stream.write(_op_line(op))
                for op in tgt.operations:
                    stream.write(_op_line(op))

    t = report.totals
    failed = sum(1 for p in report.policies if p.status == "failed")
    stream.write(
        f"reconcile [{report.mode}] status={report.status}  "
        f"imported={t.imported} updated={t.updated} deleted={t.deleted} "
        f"aliased={t.aliased} skipped={t.skipped} failed_policies={failed}\n"
    )
