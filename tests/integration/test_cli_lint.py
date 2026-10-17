from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic_settings import SettingsError
from typer.testing import CliRunner

from knock.cli.main import _run, app
from knock.errors import ConfigError
from knock.use_cases.lint import lint_report_json_schema

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for var in (
        "KNOCK_REGISTRIES",
        "KNOCK_LOG_FORMAT",
        "KNOCK_TRANSFORM_CA_CERTS",
        "KNOCK_TRANSFORM_PACKAGE_MIRRORS",
    ):
        monkeypatch.delenv(var, raising=False)
    # No external tool may be called: an empty PATH proves it.
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


def _policy(
    name: str = "nginx", registry: str | None = None, **import_extra: Any
) -> dict[str, Any]:
    dest: dict[str, Any] = {"project": "lib", "repository": name}
    if registry is not None:
        dest["registry"] = registry
    imp: dict[str, Any] = {"name": "v", "tags": {}, "destinations": [dest]}
    imp.update(import_extra)
    return {
        "apiVersion": "knock.io/v1alpha1",
        "kind": "MirrorPolicy",
        "metadata": {"name": name},
        "spec": {
            "artifactType": "image",
            "source": {"registry": "docker.io", "repository": f"library/{name}"},
            "imports": [imp],
        },
    }


def _write(directory: Path, name: str, doc: dict[str, Any]) -> None:
    (directory / name).write_text(json.dumps(doc))


def test_valid_tree_exits_0(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _policy())
    result = runner.invoke(app, ["lint", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "lint  errors=0 warnings=0" in result.stdout


def test_broken_tree_json_exits_1_and_matches_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KNOCK_LOG_FORMAT", "json")
    _write(tmp_path, "a.yaml", _policy(bogus=1))
    result = runner.invoke(app, ["lint", str(tmp_path)])
    assert result.exit_code == 1, result.output
    data = json.loads(result.stdout)
    jsonschema.validate(data, lint_report_json_schema())
    assert data["errors"][0]["level"] == "N1"


def test_missing_directory_is_a_config_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["lint", str(tmp_path / "nope")])
    assert isinstance(result.exception, ConfigError)


def test_file_instead_of_directory_is_a_config_error(tmp_path: Path) -> None:
    f = tmp_path / "a.yaml"
    f.write_text("x")
    result = runner.invoke(app, ["lint", str(f)])
    assert isinstance(result.exception, ConfigError)


def test_malformed_roster_is_a_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KNOCK_REGISTRIES", "not json")
    result = runner.invoke(app, ["lint", str(tmp_path)])
    assert isinstance(result.exception, SettingsError)


def test_text_mode_without_roster_prints_skipped_line_first(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _policy(bogus=1))
    result = runner.invoke(app, ["lint", str(tmp_path)])
    assert result.exit_code == 1
    lines = result.stdout.splitlines()
    assert lines[0] == "skipped: N3 (KNOCK_REGISTRIES not set)"
    assert lines[1].startswith("ERROR a.yaml spec.imports[0].bogus: ")
    assert lines[-1] == "lint  errors=1 warnings=0"


def test_text_mode_error_without_loc_and_with_related(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("not: a: valid: policy")
    result = runner.invoke(app, ["lint", str(tmp_path)])
    assert result.exit_code == 1
    assert any(
        ln.startswith("ERROR a.yaml: ") and "spec." not in ln for ln in result.stdout.splitlines()
    )


def test_ownership_collision_lists_related_files(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _policy("nginx"))
    other = _policy("other")
    other["spec"]["imports"][0]["destinations"][0]["repository"] = "nginx"
    _write(tmp_path, "b.yaml", other)
    result = runner.invoke(app, ["lint", str(tmp_path)])
    assert result.exit_code == 1
    assert "(also: " in result.stdout


def _warning_policy() -> dict[str, Any]:
    doc = _policy()
    doc["spec"]["imports"] = [
        {
            "name": n,
            "tags": {"aliases": ["{major}"]},
            "destinations": [{"project": "lib", "repository": "nginx"}],
        }
        for n in ("v1", "v2")
    ]
    return doc


def test_warning_only_tree_exits_0_with_warn_line(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _warning_policy())
    result = runner.invoke(app, ["lint", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "WARN a.yaml: " in result.stdout
    assert result.stdout.splitlines()[-1] == "lint  errors=0 warnings=1"


def test_errors_are_printed_before_warnings(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _warning_policy())
    _write(tmp_path, "b.yaml", _policy("other", bogus=1))
    result = runner.invoke(app, ["lint", str(tmp_path)])
    lines = [ln for ln in result.stdout.splitlines() if ln.startswith(("ERROR", "WARN"))]
    assert [ln.split()[0] for ln in lines] == ["ERROR", "WARN"]


def test_unknown_registry_with_roster_is_n3_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KNOCK_REGISTRIES", json.dumps({"harbor": {"host": "harbor.example.com"}}))
    monkeypatch.setenv("KNOCK_LOG_FORMAT", "json")
    _write(tmp_path, "a.yaml", _policy(registry="quay"))
    result = runner.invoke(app, ["lint", str(tmp_path)])
    assert result.exit_code == 1, result.output
    data = json.loads(result.stdout)
    assert data["errors"][0]["level"] == "N3"
    assert data["skipped"] == []


def test_run_maps_missing_directory_to_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["knock", "lint", str(tmp_path / "nope")])
    with pytest.raises(SystemExit) as exc:
        _run()
    assert exc.value.code == 3


def test_run_maps_unreadable_configuration_to_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "a.yaml", _policy())
    monkeypatch.setenv("KNOCK_REGISTRIES", "not json")
    monkeypatch.setattr(sys, "argv", ["knock", "lint", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        _run()
    assert exc.value.code == 3
