"""Boundary test: the `knock scan` sub-app must be importable and show help
even when redis-py is absent; commands that need Redis must print the install hint."""

from __future__ import annotations

import subprocess
import sys


def _run(args_line: str) -> subprocess.CompletedProcess:
    code = (
        "import builtins; _imp=builtins.__import__\n"
        "def block(name,*a,**k):\n"
        "    if name=='redis': raise ModuleNotFoundError('blocked')\n"
        "    return _imp(name,*a,**k)\n"
        "builtins.__import__=block\n"
        "from typer.testing import CliRunner\n"
        "from knock.cli.main import app\n"
        f"r=CliRunner().invoke(app, {args_line})\n"
        "import sys as _s; print('EXIT', r.exit_code); print(r.output); _s.exit(0)\n"
    )
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)


def test_scan_help_works_without_redis():
    result = _run("['scan','--help']")
    out = result.stdout
    assert "EXIT 0" in out
    # worker is gone; reserve, attach, enqueue, reaper must be listed
    assert "reserve" in out
    assert "attach" in out
    assert "enqueue" in out
    assert "reaper" in out
    # the install-missing error hint must NOT appear on help (only on actual commands)
    assert "redis-py is not installed" not in out


def test_scan_reserve_without_redis_prints_install_hint():
    result = _run("['scan','reserve']")
    out = result.stdout
    # CliRunner mixes stderr (where the err=True hint goes) into r.output by design.
    assert "pip install knock-oci[scan]" in out
    assert "EXIT 3" in out
