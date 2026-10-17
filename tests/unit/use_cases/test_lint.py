"""`lint_policies`: offline validation of a policy tree (spec policy-lint, design D1-D9)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from knock.config import CACertSource, PackageMirror, RegistryConfig
from knock.domain.transforms.base import ResourceRef
from knock.errors import InternalError, PolicyValidationError
from knock.use_cases.lint import (
    Finding,
    LintReport,
    Skipped,
    _check_refs,
    lint_exit_code,
    lint_policies,
    lint_report_json_schema,
)
from knock.use_cases.loader import load_policy_dir

HARBOR = {"harbor": RegistryConfig(host="harbor.example.com")}


def _import(name: str = "v", **extra: Any) -> dict[str, Any]:
    imp: dict[str, Any] = {
        "name": name,
        "tags": {},
        "destinations": [{"project": "lib", "repository": "nginx"}],
    }
    imp.update(extra)
    return imp


def _policy(name: str = "nginx", imports: list[dict[str, Any]] | None = None, **spec: Any) -> str:
    body: dict[str, Any] = {
        "artifactType": "image",
        "source": {"registry": "docker.io", "repository": f"library/{name}"},
        "imports": imports if imports is not None else [_import()],
    }
    body.update(spec)
    # JSON is valid YAML, so a policy built as a dict is written as JSON text.
    return json.dumps(
        {
            "apiVersion": "knock.io/v1alpha1",
            "kind": "MirrorPolicy",
            "metadata": {"name": name},
            "spec": body,
        }
    )


def _lint(
    directory: Path,
    *,
    roster: dict[str, RegistryConfig] | None = None,
    ca_certs: dict[str, CACertSource] | None = None,
    package_mirrors: dict[str, PackageMirror] | None = None,
) -> LintReport:
    return lint_policies(
        directory,
        roster=roster or {},
        ca_certs=ca_certs or {},
        package_mirrors=package_mirrors or {},
    )


def _dest(repository: str, registry: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {"project": "lib", "repository": repository}
    if registry is not None:
        d["registry"] = registry
    return d


# --- N1: loading -----------------------------------------------------------------------


def test_valid_tree_has_no_error(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(_policy("nginx"))
    sub = tmp_path / "team"
    sub.mkdir()
    (sub / "b.yml").write_text(_policy("redis", [_import(destinations=[_dest("redis")])]))
    report = _lint(tmp_path)
    assert report.errors == []
    assert report.warnings == []
    assert lint_exit_code(report) == 0


def test_non_policy_files_are_not_read(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(_policy())
    (tmp_path / "README.md").write_text("not: a: policy")
    report = _lint(tmp_path)
    assert report.errors == []


def test_two_broken_files_give_two_errors(tmp_path: Path) -> None:
    broken = json.loads(_policy())
    broken["spec"]["imports"][0]["bogus"] = 1
    (tmp_path / "a.yaml").write_text(json.dumps(broken))
    (tmp_path / "b.yaml").write_text("not: a: valid: policy")
    report = _lint(tmp_path)
    assert [(f.level, f.path) for f in report.errors] == [("N1", "a.yaml"), ("N1", "b.yaml")]
    assert report.errors[0].loc == ["spec", "imports", 0, "bogus"]
    assert report.errors[1].loc is None
    assert lint_exit_code(report) == 1


def test_directory_without_policy_reports_one_error(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello")
    report = _lint(tmp_path)
    assert len(report.errors) == 1
    assert report.errors[0].level == "N1"
    assert report.errors[0].message == f"no policy file found under {tmp_path}"
    assert lint_exit_code(report) == 1


def test_semantic_rule_outside_schema_is_reported(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(_policy(artifactType="skill"))
    report = _lint(tmp_path)
    assert [f.level for f in report.errors] == ["N1"]
    assert "requires a git source" in report.errors[0].message


@pytest.mark.parametrize(
    "text",
    [
        _policy(),
        _policy(artifactType="skill"),
        "not: a: valid: policy",
        "- a list\n",
        _policy().replace("MirrorPolicy", "Other"),
    ],
)
def test_same_verdict_as_reconcile_loading(tmp_path: Path, text: str) -> None:
    (tmp_path / "a.yaml").write_text(text)
    try:
        load_policy_dir(tmp_path)
        refused = False
    except PolicyValidationError:
        refused = True
    report = _lint(tmp_path)
    assert any(f.level == "N1" for f in report.errors) is refused


def test_unreadable_policy_file_is_an_n1_error(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_bytes(b"\xff\xfe\x00bad")
    report = _lint(tmp_path)
    assert [(f.level, f.path) for f in report.errors] == [("N1", "a.yaml")]


# --- N2: steps -------------------------------------------------------------------------


def test_misspelled_transform_step_is_an_n2_error(tmp_path: Path) -> None:
    imp = _import(transform=[{"name": "injectCa", "params": {"certs": ["corp"]}}])
    (tmp_path / "a.yaml").write_text(_policy(imports=[imp]))
    report = _lint(tmp_path)
    assert [(f.level, f.path) for f in report.errors] == [("N2", "a.yaml")]
    assert "'v'" in report.errors[0].message
    assert "'injectCa'" in report.errors[0].message


def test_bad_params_of_known_step_is_an_n2_error(tmp_path: Path) -> None:
    imp = _import(transform=[{"name": "injectCA", "params": {"certs": []}}])
    (tmp_path / "a.yaml").write_text(_policy(imports=[imp]))
    report = _lint(tmp_path)
    assert [f.level for f in report.errors] == ["N2"]
    message = report.errors[0].message
    assert message.startswith("import 'v': transform step 'injectCA': ")
    assert "certs" in message
    assert "\n" not in message


def test_step_errors_inherited_by_variants_are_reported_once(tmp_path: Path) -> None:
    imp = _import(
        transform=[{"name": "injectCa", "params": {}}],
        variants=[{"name": "a", "suffix": "-a"}, {"name": "b", "suffix": "-b"}],
    )
    (tmp_path / "a.yaml").write_text(_policy(imports=[imp]))
    report = _lint(tmp_path)
    assert len(report.errors) == 1


def test_variant_own_steps_are_checked_and_named(tmp_path: Path) -> None:
    imp = _import(
        variants=[
            {"name": "plain"},
            {"name": "fips", "suffix": "-fips", "transform": [{"name": "nope"}]},
        ]
    )
    (tmp_path / "a.yaml").write_text(_policy(imports=[imp]))
    report = _lint(tmp_path)
    assert len(report.errors) == 1
    assert "variant 'fips'" in report.errors[0].message
    assert "'nope'" in report.errors[0].message


def test_remediation_rules_follow_reconcile(tmp_path: Path) -> None:
    imp = _import(remediate=[{"name": "upgradePackages"}])
    (tmp_path / "a.yaml").write_text(_policy(imports=[imp]))
    report = _lint(tmp_path)
    assert len(report.errors) == 1
    assert "remediate step 'upgradePackages'" in report.errors[0].message
    assert "rewritePackageSources" in report.errors[0].message


def test_valid_remediation_has_no_error(tmp_path: Path) -> None:
    imp = _import(
        transform=[{"name": "rewritePackageSources", "params": {"mirror": "corp"}}],
        remediate=[{"name": "upgradePackages"}],
    )
    (tmp_path / "a.yaml").write_text(_policy(imports=[imp]))
    report = _lint(tmp_path)
    assert report.errors == []


def test_import_valid_once_defaults_are_merged(tmp_path: Path) -> None:
    imp = {"name": "v", "tags": {}}
    defaults = {
        "destinations": [_dest("nginx")],
        "transform": [{"name": "injectCA", "params": {"certs": ["corp"]}}],
    }
    (tmp_path / "a.yaml").write_text(_policy(imports=[imp], defaults=defaults))
    report = _lint(tmp_path)
    assert report.errors == []


# --- N2: ownership ---------------------------------------------------------------------


def test_two_policies_one_repository_is_an_ownership_error(tmp_path: Path) -> None:
    dest = [_dest("nginx", "harbor")]
    (tmp_path / "a.yaml").write_text(_policy("one", [_import(destinations=dest)]))
    (tmp_path / "b.yaml").write_text(_policy("two", [_import(destinations=dest)]))
    report = _lint(tmp_path)
    assert len(report.errors) == 1
    err = report.errors[0]
    assert err.level == "N2"
    assert err.path == "a.yaml"
    assert err.related == ["b.yaml"]
    assert err.message == (
        "destination repository 'harbor/lib/nginx' is written by policies 'one' (a.yaml) "
        "and 'two' (b.yaml); a repository must be owned by exactly one policy"
    )
    assert lint_exit_code(report) == 1


def test_three_policies_one_repository_are_listed_in_claim_order(tmp_path: Path) -> None:
    dest = [_dest("nginx", "harbor")]
    (tmp_path / "a.yaml").write_text(_policy("zed", [_import(destinations=dest)]))
    (tmp_path / "b.yaml").write_text(_policy("alpha", [_import(destinations=dest)]))
    (tmp_path / "c.yaml").write_text(_policy("zed", [_import(destinations=dest)]))
    (tmp_path / "d.yaml").write_text(_policy("mid", [_import(destinations=dest)]))
    report = _lint(tmp_path)
    assert len(report.errors) == 1
    err = report.errors[0]
    assert err.related == ["b.yaml", "c.yaml", "d.yaml"]
    assert "policies 'zed' (a.yaml), 'alpha' (b.yaml) and 'mid' (d.yaml);" in err.message


def test_ownership_key_is_the_resolved_host_with_a_roster(tmp_path: Path) -> None:
    # Two logical names for one host only meet once N3 resolves them (D4).
    roster = {
        "harbor": RegistryConfig(host="harbor.example.com"),
        "alias": RegistryConfig(host="harbor.example.com"),
    }
    (tmp_path / "a.yaml").write_text(_policy("one", [_import(destinations=[_dest("x", "harbor")])]))
    (tmp_path / "b.yaml").write_text(_policy("two", [_import(destinations=[_dest("x", "alias")])]))
    assert _lint(tmp_path).errors == []
    report = _lint(tmp_path, roster=roster)
    assert len(report.errors) == 1
    assert "harbor.example.com/lib/x" in report.errors[0].message


def test_omitted_registry_uses_the_default_key(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(_policy("one"))
    (tmp_path / "b.yaml").write_text(_policy("two"))
    report = _lint(tmp_path)
    assert len(report.errors) == 1
    assert "<default>/lib/nginx" in report.errors[0].message


def test_same_policy_name_in_two_files_is_not_an_ownership_error(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(_policy("one"))
    (tmp_path / "b.yaml").write_text(_policy("one"))
    assert _lint(tmp_path).errors == []


def test_two_imports_of_one_policy_one_repository_is_fine(tmp_path: Path) -> None:
    imports = [_import("v1"), _import("v2")]
    (tmp_path / "a.yaml").write_text(_policy(imports=imports))
    report = _lint(tmp_path)
    assert report.errors == []


# --- N2: aliases -----------------------------------------------------------------------


def test_same_literal_alias_from_two_imports_is_an_error(tmp_path: Path) -> None:
    imports = [
        _import("v1", tags={"aliases": ["latest"]}),
        _import("v2", tags={"aliases": ["latest"]}),
    ]
    (tmp_path / "a.yaml").write_text(_policy(imports=imports))
    report = _lint(tmp_path)
    assert len(report.errors) == 1
    err = report.errors[0]
    assert (err.level, err.path) == ("N2", "a.yaml")
    assert "'v1'" in err.message and "'v2'" in err.message
    assert "'latest'" in err.message
    assert report.warnings == []
    assert lint_exit_code(report) == 1


def test_two_imports_with_one_name_still_overlap(tmp_path: Path) -> None:
    imports = [
        _import("v", tags={"aliases": ["latest"]}),
        _import("v", tags={"aliases": ["latest"]}),
    ]
    (tmp_path / "a.yaml").write_text(_policy(imports=imports))
    report = _lint(tmp_path)
    assert [f.level for f in report.errors] == ["N2"]
    assert "imports[0] 'v'" in report.errors[0].message
    assert "imports[1] 'v'" in report.errors[0].message


def test_overlapping_templates_are_a_warning_only(tmp_path: Path) -> None:
    imports = [
        _import("v1", tags={"aliases": ["{major}"]}),
        _import("v2", tags={"aliases": ["{major}"]}),
    ]
    (tmp_path / "a.yaml").write_text(_policy(imports=imports))
    report = _lint(tmp_path)
    assert report.errors == []
    assert len(report.warnings) == 1
    warning = report.warnings[0]
    assert (warning.level, warning.path) == ("N2", "a.yaml")
    assert "'v1'" in warning.message and "'v2'" in warning.message
    assert lint_exit_code(report) == 0


def test_same_alias_into_two_repositories_is_fine(tmp_path: Path) -> None:
    imports = [
        _import("v1", tags={"aliases": ["latest"]}, destinations=[_dest("nginx")]),
        _import("v2", tags={"aliases": ["latest"]}, destinations=[_dest("redis")]),
    ]
    (tmp_path / "a.yaml").write_text(_policy(imports=imports))
    report = _lint(tmp_path)
    assert report.errors == []
    assert report.warnings == []


def test_variant_suffixes_keep_aliases_apart(tmp_path: Path) -> None:
    imports = [
        _import("v1", tags={"aliases": ["latest"]}),
        _import("v2", tags={"aliases": ["latest"]}, variants=[{"name": "f", "suffix": "-fips"}]),
    ]
    (tmp_path / "a.yaml").write_text(_policy(imports=imports))
    assert _lint(tmp_path).errors == []


def test_git_imports_claim_the_source_ref(tmp_path: Path) -> None:
    git = {"url": "https://github.com/example/skill.git", "ref": "main"}
    imports = [_import("r1"), _import("r2")]
    (tmp_path / "a.yaml").write_text(_policy(imports=imports, artifactType="skill", source=git))
    report = _lint(tmp_path)
    assert len(report.errors) == 1
    assert "'main'" in report.errors[0].message


# --- N3: configuration -----------------------------------------------------------------


def test_without_roster_n3_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(_policy(imports=[_import(destinations=[_dest("x", "quay")])]))
    report = _lint(tmp_path)
    assert report.errors == []
    assert report.skipped == [Skipped(level="N3", reason="KNOCK_REGISTRIES not set")]


def test_unknown_destination_registry_is_an_n3_error(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(_policy(imports=[_import(destinations=[_dest("x", "quay")])]))
    report = _lint(tmp_path, roster=HARBOR)
    assert report.skipped == []
    assert len(report.errors) == 1
    err = report.errors[0]
    assert (err.level, err.path) == ("N3", "a.yaml")
    assert "'quay'" in err.message and "harbor" in err.message


def test_omitted_registry_with_several_configured_is_an_n3_error(tmp_path: Path) -> None:
    roster = {**HARBOR, "quay": RegistryConfig(host="quay.example.com")}
    (tmp_path / "a.yaml").write_text(_policy())
    report = _lint(tmp_path, roster=roster)
    assert [f.level for f in report.errors] == ["N3"]


def test_known_references_pass(tmp_path: Path) -> None:
    cert = tmp_path / "corp.crt"
    cert.write_text("PEM")
    imp = _import(
        destinations=[_dest("x", "harbor")],
        transform=[
            {"name": "injectCA", "params": {"certs": ["corp", "inline"]}},
            {"name": "rewritePackageSources", "params": {"mirror": "deb"}},
        ],
    )
    (tmp_path / "a.yaml").write_text(_policy(imports=[imp]))
    report = _lint(
        tmp_path,
        roster=HARBOR,
        ca_certs={"corp": CACertSource(path=str(cert)), "inline": CACertSource(pem="PEM")},
        package_mirrors={"deb": PackageMirror(apt="https://mirror")},
    )
    assert report.errors == []


def test_unknown_ca_and_mirror_are_n3_errors_reported_once(tmp_path: Path) -> None:
    steps = [
        {"name": "injectCA", "params": {"certs": ["corp"]}},
        {"name": "rewritePackageSources", "params": {"mirror": "deb"}},
    ]
    imports = [
        _import("v1", destinations=[_dest("x", "harbor")], transform=steps),
        _import("v2", destinations=[_dest("y", "harbor")], transform=steps),
    ]
    (tmp_path / "a.yaml").write_text(_policy(imports=imports))
    report = _lint(tmp_path, roster=HARBOR)
    assert [f.level for f in report.errors] == ["N3", "N3"]
    assert "CA cert 'corp'" in report.errors[0].message
    assert "package mirror 'deb'" in report.errors[1].message


def test_unreadable_ca_path_is_an_n3_error(tmp_path: Path) -> None:
    imp = _import(
        destinations=[_dest("x", "harbor")],
        transform=[{"name": "injectCA", "params": {"certs": ["corp"]}}],
    )
    (tmp_path / "a.yaml").write_text(_policy(imports=[imp]))
    missing = tmp_path / "missing.crt"
    report = _lint(tmp_path, roster=HARBOR, ca_certs={"corp": CACertSource(path=str(missing))})
    assert len(report.errors) == 1
    err = report.errors[0]
    assert (err.level, err.path) == ("N3", "a.yaml")
    assert str(missing) in err.message


def test_unknown_resource_kind_is_an_internal_error() -> None:
    with pytest.raises(InternalError, match="other"):
        _check_refs([ResourceRef("other", "x")], {}, {})


# --- order, report and exit code -------------------------------------------------------


def test_findings_are_ordered(tmp_path: Path) -> None:
    dest = [_dest("shared", "quay")]
    bad_step = [{"name": "nope"}]
    (tmp_path / "a.yaml").write_text(
        _policy("one", [_import(destinations=dest, transform=bad_step)])
    )
    (tmp_path / "b.yaml").write_text(_policy("two", [_import(destinations=dest)]))
    (tmp_path / "c.yaml").write_text("not: a: valid: policy")
    report = _lint(tmp_path, roster=HARBOR)
    assert [(f.level, f.path) for f in report.errors] == [
        ("N1", "c.yaml"),
        ("N2", "a.yaml"),
        ("N3", "a.yaml"),
        ("N3", "b.yaml"),
        ("N2", "a.yaml"),
    ]
    assert report.errors[-1].related == ["b.yaml"]


def test_exit_code_from_findings() -> None:
    finding = Finding(level="N2", path="a.yaml", loc=None, message="w")
    assert lint_exit_code(LintReport(errors=[], warnings=[finding], skipped=[])) == 0
    assert lint_exit_code(LintReport(errors=[finding], warnings=[], skipped=[])) == 1


def test_report_envelope_and_schema(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("not: a: valid: policy")
    report = _lint(tmp_path)
    document = json.loads(report.model_dump_json(by_alias=True))
    assert document["apiVersion"] == "knock.io/v1alpha1"
    assert document["kind"] == "LintReport"
    assert set(document) == {"apiVersion", "kind", "errors", "warnings", "skipped"}
    jsonschema.validate(document, lint_report_json_schema())
