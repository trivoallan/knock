from __future__ import annotations

from pathlib import Path

import pytest

from knock.errors import PolicyValidationError
from knock.use_cases.loader import load_policy_dir, load_policy_files

VALID = """
apiVersion: knock.io/v1alpha1
kind: MirrorPolicy
metadata: { name: %s }
spec:
  artifactType: image
  source: { registry: docker.io, repository: library/%s }
  imports: [{ name: v, tags: {}, destinations: [{ project: lib, repository: %s }] }]
"""


def test_load_recursive(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text(VALID % ("redis", "redis", "redis"))
    sub = tmp_path / "team-x"
    sub.mkdir()
    (sub / "b.yaml").write_text(VALID % ("nginx", "nginx", "nginx"))
    (tmp_path / "notes.txt").write_text("ignored")
    policies = load_policy_dir(tmp_path)
    assert sorted(p.metadata.name for p in policies) == ["nginx", "redis"]


def test_load_invalid_file_raises(tmp_path: Path) -> None:
    (tmp_path / "bad.yml").write_text("not: a: valid: policy")
    with pytest.raises(PolicyValidationError):
        load_policy_dir(tmp_path)


def test_load_empty_dir_returns_empty(tmp_path: Path) -> None:
    assert load_policy_dir(tmp_path) == []


BAD_FIELD = VALID % ("bad", "bad", "bad") + "  bogus: 1\n"


def test_load_files_collects_every_error(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(BAD_FIELD)
    (tmp_path / "b.yaml").write_text("not: a: valid: policy")
    (tmp_path / "notes.txt").write_text("ignored")
    loaded, issues = load_policy_files(tmp_path)
    assert loaded == []
    assert sorted({i.path for i in issues}) == ["a.yaml", "b.yaml"]
    assert [i.path for i in issues] == sorted(i.path for i in issues)
    a = [i for i in issues if i.path == "a.yaml"]
    assert any(i.loc[:1] == ("spec",) and "bogus" in i.loc for i in a)


def test_load_files_returns_valid_next_to_broken(tmp_path: Path) -> None:
    sub = tmp_path / "team"
    sub.mkdir()
    (sub / "ok.yml").write_text(VALID % ("redis", "redis", "redis"))
    (tmp_path / "bad.yml").write_text("not: a: valid: policy")
    loaded, issues = load_policy_files(tmp_path)
    assert [(lp.path, lp.policy.metadata.name) for lp in loaded] == [("team/ok.yml", "redis")]
    assert [i.path for i in issues] == ["bad.yml"]


def test_load_dir_message_unchanged(tmp_path: Path) -> None:
    (tmp_path / "bad.yml").write_text(BAD_FIELD)
    with pytest.raises(PolicyValidationError) as ei:
        load_policy_dir(tmp_path)
    assert str(ei.value).startswith(f"{tmp_path / 'bad.yml'}: ")
    assert "bogus" in str(ei.value)
