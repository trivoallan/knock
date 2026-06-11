from __future__ import annotations

from pathlib import Path

import pytest

from houba.errors import PolicyValidationError
from houba.use_cases.loader import load_policy_dir

VALID = """
apiVersion: houba.io/v1alpha1
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
