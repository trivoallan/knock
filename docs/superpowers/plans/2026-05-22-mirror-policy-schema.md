# MirrorPolicy schema + merge + JSON Schema — Implementation Plan (Phase 1 of 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure-domain `MirrorPolicy` data model — parse + validate a policy YAML, resolve `defaults` into each `import` via the rule-B merge, and emit a JSON Schema — with no I/O.

**Architecture:** New pure module `houba/domain/mirror_policy.py` (Pydantic v2 models, camelCase↔snake_case aliasing, `extra="forbid"`) plus `houba/domain/policy_merge.py` (rule-B: shallow-merge maps, replace lists). Additive — the legacy `houba/domain/properties.py` stays untouched until the reconcile use case replaces it (Phase 7). Transform steps are modelled *structurally* here (a named step with a free-form params dict); the per-step `image` vocabulary is Phase 6.

**Tech Stack:** Python 3.12, Pydantic v2 (`pydantic.alias_generators.to_camel`, `model_validator`, `model_json_schema`), PyYAML, pytest. Everything via `uv run`.

**Reference spec:** [docs/superpowers/specs/2026-05-22-mirror-policy-format-design.md](../specs/2026-05-22-mirror-policy-format-design.md) — §3 (schema), §3.4 (merge rule B), §4 (imports), §5 (TagSelection), §6 (artifactType), §6.2 (platforms validation).

**Branch:** `feat/mirror-policy` (already checked out).

---

## File map for this phase

```
houba/
├── errors.py                      MODIFY: add PolicyValidationError(DomainError)
└── domain/
    ├── mirror_policy.py           NEW: Pydantic models + parse_mirror_policy + json_schema
    └── policy_merge.py            NEW: resolve_imports (rule B) + post-merge validation

tests/
└── unit/domain/
    ├── test_mirror_policy.py      NEW
    └── test_policy_merge.py       NEW
```

Scope boundaries for this phase: **no** tag selection, **no** alias resolution, **no** reconcile-plan, **no** registry/config. `aliases` and `transform` are accepted and structurally validated, but their *semantics* (rendering aliases, applying transforms) are later phases. Coverage gate on `houba.domain` stays ≥ 90 %.

---

## Task 1: `PolicyValidationError` in the error hierarchy

**Files:**
- Modify: `houba/errors.py`
- Test: `tests/unit/test_errors.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_errors.py`:

```python
def test_policy_validation_error_is_domain_error_exit_1() -> None:
    from houba.errors import DomainError, PolicyValidationError, exit_code_for

    err = PolicyValidationError("bad policy")
    assert isinstance(err, DomainError)
    assert exit_code_for(err) == 1
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/test_errors.py::test_policy_validation_error_is_domain_error_exit_1 -v`
Expected: FAIL — `ImportError: cannot import name 'PolicyValidationError'`.

- [ ] **Step 3: Implement**

In `houba/errors.py`, add the class next to `PropertiesValidationError` (under the `DomainError` branch):

```python
class PolicyValidationError(DomainError):
    """`MirrorPolicy` YAML invalid (schema, unknown field, inconsistent spec)."""
```

Add `"PolicyValidationError"` to the `__all__` list (keep it alphabetically sorted).

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/test_errors.py -v`
Expected: PASS (all error tests).

- [ ] **Step 5: Commit**

```bash
git add houba/errors.py tests/unit/test_errors.py
git commit -m "feat(errors): ajoute PolicyValidationError (branche DomainError)"
```

---

## Task 2: camelCase base model + `Source` / `Destination` / `ArtifactType`

**Files:**
- Create: `houba/domain/mirror_policy.py`
- Test: `tests/unit/domain/test_mirror_policy.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/test_mirror_policy.py`:

```python
from __future__ import annotations

import pytest

from houba.domain.mirror_policy import ArtifactType, Destination, Source


def test_source_parses() -> None:
    s = Source.model_validate({"registry": "docker.io", "repository": "library/redis"})
    assert s.registry == "docker.io"
    assert s.repository == "library/redis"


def test_destination_registry_optional() -> None:
    d = Destination.model_validate({"project": "lib", "repository": "redis"})
    assert d.registry is None
    assert d.project == "lib"


def test_destination_with_named_registry() -> None:
    d = Destination.model_validate(
        {"registry": "harbor-eu", "project": "lib", "repository": "redis"}
    )
    assert d.registry == "harbor-eu"


def test_artifact_type_values() -> None:
    assert ArtifactType("image") is ArtifactType.image
    assert ArtifactType("helmChart") is ArtifactType.helm_chart
    assert ArtifactType("generic") is ArtifactType.generic


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(Exception):  # pydantic ValidationError — extra="forbid"
        Source.model_validate({"registry": "docker.io", "repository": "r", "typo": 1})
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -v`
Expected: FAIL — `ModuleNotFoundError: houba.domain.mirror_policy`.

- [ ] **Step 3: Implement**

Create `houba/domain/mirror_policy.py`:

```python
"""Pure-domain models for the MirrorPolicy declaration (see spec §3).

YAML is camelCase; Python is snake_case. Unknown fields are rejected so typos in
a policy file fail fast (the schema is the public API).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class ArtifactType(str, Enum):
    image = "image"
    helm_chart = "helmChart"
    generic = "generic"


class Source(_CamelModel):
    registry: str
    repository: str


class Destination(_CamelModel):
    registry: str | None = None  # optional iff exactly one registry configured (checked at reconcile)
    project: str
    repository: str
```

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add houba/domain/mirror_policy.py tests/unit/domain/test_mirror_policy.py
git commit -m "feat(domain): MirrorPolicy base — CamelModel, Source, Destination, ArtifactType"
```

---

## Task 3: `TagSelection`

**Files:**
- Modify: `houba/domain/mirror_policy.py`
- Test: `tests/unit/domain/test_mirror_policy.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/domain/test_mirror_policy.py`:

```python
from houba.domain.mirror_policy import TagSelection


def test_tag_selection_defaults() -> None:
    t = TagSelection.model_validate({})
    assert t.include_regex is None
    assert t.exclude_regex == []
    assert t.semver_only is True
    assert t.names == []
    assert t.aliases == []


def test_tag_selection_camel_case_input() -> None:
    t = TagSelection.model_validate(
        {
            "includeRegex": "^7\\.",
            "excludeRegex": ["-rc"],
            "semverOnly": False,
            "names": ["7.2.1-special"],
            "aliases": ["{major}.{minor}", "latest"],
        }
    )
    assert t.include_regex == "^7\\."
    assert t.exclude_regex == ["-rc"]
    assert t.semver_only is False
    assert t.names == ["7.2.1-special"]
    assert t.aliases == ["{major}.{minor}", "latest"]
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -k tag_selection -v`
Expected: FAIL — `ImportError: cannot import name 'TagSelection'`.

- [ ] **Step 3: Implement**

Add to `houba/domain/mirror_policy.py` (after `Destination`):

```python
from pydantic import Field


class TagSelection(_CamelModel):
    include_regex: str | None = None
    exclude_regex: list[str] = Field(default_factory=list)
    semver_only: bool = True
    names: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
```

(Move the `from pydantic import Field` to the top import block alongside `BaseModel, ConfigDict`.)

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add houba/domain/mirror_policy.py tests/unit/domain/test_mirror_policy.py
git commit -m "feat(domain): MirrorPolicy TagSelection (regex/semverOnly/names/aliases)"
```

---

## Task 4: `TransformStep` — single-key map parsing

The YAML shape is `- injectCA: {certs: [...]}`: each list item is a one-key map whose key is the step name. We model it structurally as `{name, params}` here; the per-step vocabulary is Phase 6.

**Files:**
- Modify: `houba/domain/mirror_policy.py`
- Test: `tests/unit/domain/test_mirror_policy.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from houba.domain.mirror_policy import TransformStep


def test_transform_step_from_single_key_map() -> None:
    step = TransformStep.model_validate({"injectCA": {"certs": ["corp-root-ca"]}})
    assert step.name == "injectCA"
    assert step.params == {"certs": ["corp-root-ca"]}


def test_transform_step_with_empty_params() -> None:
    step = TransformStep.model_validate({"enableFips": {}})
    assert step.name == "enableFips"
    assert step.params == {}


def test_transform_step_null_params_becomes_empty() -> None:
    step = TransformStep.model_validate({"enableFips": None})
    assert step.params == {}


def test_transform_step_rejects_multi_key() -> None:
    with pytest.raises(ValueError):
        TransformStep.model_validate({"injectCA": {}, "setTimezone": {}})


def test_transform_step_rejects_empty() -> None:
    with pytest.raises(ValueError):
        TransformStep.model_validate({})
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -k transform_step -v`
Expected: FAIL — `ImportError: cannot import name 'TransformStep'`.

- [ ] **Step 3: Implement**

Add to `houba/domain/mirror_policy.py`:

```python
from typing import Any

from pydantic import model_validator


class TransformStep(_CamelModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _from_single_key_map(cls, data: Any) -> Any:
        # Accept the already-split {name, params} form (e.g. when re-validating)...
        if isinstance(data, dict) and set(data.keys()) <= {"name", "params"}:
            return data
        # ...otherwise expect the YAML single-key form {stepName: params}.
        if not isinstance(data, dict) or len(data) != 1:
            raise ValueError("a transform step must be a single-key map {stepName: params}")
        ((name, params),) = data.items()
        return {"name": name, "params": params or {}}
```

(Add `Any` and `model_validator` to the import block.)

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add houba/domain/mirror_policy.py tests/unit/domain/test_mirror_policy.py
git commit -m "feat(domain): MirrorPolicy TransformStep (parsing map single-clé)"
```

---

## Task 5: `Archive` and `Variant`

**Files:**
- Modify: `houba/domain/mirror_policy.py`
- Test: `tests/unit/domain/test_mirror_policy.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from houba.domain.mirror_policy import Archive, Variant


def test_archive_defaults() -> None:
    a = Archive.model_validate({})
    assert a.keep == 2
    assert a.older_than_days == 30


def test_archive_camel_input() -> None:
    a = Archive.model_validate({"keep": 5, "olderThanDays": 90})
    assert a.keep == 5
    assert a.older_than_days == 90


def test_variant_minimal() -> None:
    v = Variant.model_validate({"name": "standard", "suffix": ""})
    assert v.name == "standard"
    assert v.suffix == ""
    assert v.transform is None


def test_variant_with_transform() -> None:
    v = Variant.model_validate(
        {"name": "fips", "suffix": "-fips", "transform": [{"enableFips": {}}]}
    )
    assert v.suffix == "-fips"
    assert v.transform is not None
    assert v.transform[0].name == "enableFips"
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -k "archive or variant" -v`
Expected: FAIL — import errors for `Archive` / `Variant`.

- [ ] **Step 3: Implement**

Add to `houba/domain/mirror_policy.py`:

```python
class Archive(_CamelModel):
    keep: int = 2
    older_than_days: int = 30


class Variant(_CamelModel):
    name: str
    suffix: str = ""
    transform: list[TransformStep] | None = None  # None ⇒ inherit resolved transform
```

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add houba/domain/mirror_policy.py tests/unit/domain/test_mirror_policy.py
git commit -m "feat(domain): MirrorPolicy Archive + Variant"
```

---

## Task 6: `Defaults` and `ImportProfile`

**Files:**
- Modify: `houba/domain/mirror_policy.py`
- Test: `tests/unit/domain/test_mirror_policy.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from houba.domain.mirror_policy import Defaults, ImportProfile


def test_defaults_all_optional() -> None:
    d = Defaults.model_validate({})
    assert d.destinations is None
    assert d.transform is None
    assert d.archive is None
    assert d.tags is None
    assert d.platforms is None


def test_defaults_populated() -> None:
    d = Defaults.model_validate(
        {
            "platforms": ["linux/amd64", "linux/arm64"],
            "destinations": [{"registry": "harbor-eu", "project": "lib", "repository": "redis"}],
            "transform": [{"injectCA": {"certs": ["corp-root-ca"]}}],
            "archive": {"keep": 2, "olderThanDays": 30},
            "tags": {"semverOnly": True, "excludeRegex": ["-rc"]},
        }
    )
    assert d.platforms == ["linux/amd64", "linux/arm64"]
    assert d.destinations[0].registry == "harbor-eu"
    assert d.transform[0].name == "injectCA"
    assert d.tags.exclude_regex == ["-rc"]


def test_import_profile_minimal() -> None:
    i = ImportProfile.model_validate({"name": "v7", "tags": {"includeRegex": "^7\\."}})
    assert i.name == "v7"
    assert i.tags.include_regex == "^7\\."
    assert i.destinations is None  # inherited from defaults at merge time
    assert i.variants is None


def test_import_profile_full() -> None:
    i = ImportProfile.model_validate(
        {
            "name": "v7",
            "tags": {"includeRegex": "^7\\.", "aliases": ["{major}.{minor}"]},
            "destinations": [{"registry": "harbor-eu", "project": "lib", "repository": "redis"}],
            "transform": [{"setTimezone": {"zone": "Europe/Paris"}}],
            "archive": {"keep": 3},
            "platforms": ["linux/amd64"],
            "variants": [{"name": "standard", "suffix": ""}],
        }
    )
    assert i.platforms == ["linux/amd64"]
    assert i.variants[0].name == "standard"
    assert i.transform[0].name == "setTimezone"
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -k "defaults or import_profile" -v`
Expected: FAIL — import errors.

- [ ] **Step 3: Implement**

Add to `houba/domain/mirror_policy.py`:

```python
class Defaults(_CamelModel):
    destinations: list[Destination] | None = None
    transform: list[TransformStep] | None = None
    archive: Archive | None = None
    tags: TagSelection | None = None
    platforms: list[str] | None = None


class ImportProfile(_CamelModel):
    name: str
    tags: TagSelection
    destinations: list[Destination] | None = None
    transform: list[TransformStep] | None = None
    archive: Archive | None = None
    platforms: list[str] | None = None
    variants: list[Variant] | None = None
```

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add houba/domain/mirror_policy.py tests/unit/domain/test_mirror_policy.py
git commit -m "feat(domain): MirrorPolicy Defaults + ImportProfile"
```

---

## Task 7: `Spec` with the `generic ⇒ no transform` rule

**Files:**
- Modify: `houba/domain/mirror_policy.py`
- Test: `tests/unit/domain/test_mirror_policy.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from houba.domain.mirror_policy import Spec


def test_spec_minimal() -> None:
    spec = Spec.model_validate(
        {
            "artifactType": "image",
            "source": {"registry": "docker.io", "repository": "library/redis"},
            "imports": [{"name": "v7", "tags": {"includeRegex": "^7\\."}}],
        }
    )
    assert spec.artifact_type is ArtifactType.image
    assert spec.source.repository == "library/redis"
    assert len(spec.imports) == 1


def test_spec_artifact_type_required() -> None:
    with pytest.raises(Exception):
        Spec.model_validate(
            {
                "source": {"registry": "docker.io", "repository": "r"},
                "imports": [{"name": "v", "tags": {}}],
            }
        )


def test_spec_requires_at_least_one_import() -> None:
    with pytest.raises(Exception):
        Spec.model_validate(
            {
                "artifactType": "image",
                "source": {"registry": "docker.io", "repository": "r"},
                "imports": [],
            }
        )


def test_spec_generic_forbids_transform_in_defaults() -> None:
    from houba.errors import PolicyValidationError

    with pytest.raises(PolicyValidationError, match="generic"):
        Spec.model_validate(
            {
                "artifactType": "generic",
                "source": {"registry": "docker.io", "repository": "r"},
                "defaults": {"transform": [{"injectCA": {}}]},
                "imports": [{"name": "v", "tags": {}}],
            }
        )


def test_spec_generic_forbids_transform_in_import() -> None:
    from houba.errors import PolicyValidationError

    with pytest.raises(PolicyValidationError, match="generic"):
        Spec.model_validate(
            {
                "artifactType": "generic",
                "source": {"registry": "docker.io", "repository": "r"},
                "imports": [{"name": "v", "tags": {}, "transform": [{"injectCA": {}}]}],
            }
        )
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -k spec -v`
Expected: FAIL — `ImportError: cannot import name 'Spec'`.

- [ ] **Step 3: Implement**

Add to `houba/domain/mirror_policy.py`:

```python
from typing import Self

from houba.errors import PolicyValidationError


class Spec(_CamelModel):
    artifact_type: ArtifactType
    source: Source
    defaults: Defaults | None = None
    imports: list[ImportProfile] = Field(min_length=1)

    @model_validator(mode="after")
    def _generic_has_no_transform(self) -> Self:
        if self.artifact_type is not ArtifactType.generic:
            return self
        if self.defaults is not None and self.defaults.transform:
            raise PolicyValidationError("artifactType 'generic' must not declare transform steps")
        for imp in self.imports:
            if imp.transform:
                raise PolicyValidationError(
                    f"artifactType 'generic' must not declare transform steps (import '{imp.name}')"
                )
        return self
```

(Add `Self` to the typing import.)

Note: a Pydantic `ValidationError` raised for `min_length`/required fields is mapped to exit 3 by the CLI today; the *semantic* `generic`-transform rule raises `PolicyValidationError` (exit 1). Both are correct — structural vs business validation.

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add houba/domain/mirror_policy.py tests/unit/domain/test_mirror_policy.py
git commit -m "feat(domain): MirrorPolicy Spec + règle generic⇒no-transform"
```

---

## Task 8: `MirrorPolicy` envelope + `parse_mirror_policy`

**Files:**
- Modify: `houba/domain/mirror_policy.py`
- Test: `tests/unit/domain/test_mirror_policy.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from houba.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from houba.errors import PolicyValidationError

VALID_YAML = """
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata:
  name: redis
  labels:
    team: platform-data
spec:
  artifactType: image
  source: { registry: docker.io, repository: library/redis }
  imports:
    - name: v7
      tags: { includeRegex: "^7\\\\." }
"""


def test_parse_valid_policy() -> None:
    policy = parse_mirror_policy(VALID_YAML)
    assert isinstance(policy, MirrorPolicy)
    assert policy.api_version == "houba.io/v1alpha1"
    assert policy.kind == "MirrorPolicy"
    assert policy.metadata.name == "redis"
    assert policy.metadata.labels == {"team": "platform-data"}
    assert policy.spec.imports[0].name == "v7"


def test_parse_rejects_wrong_kind() -> None:
    with pytest.raises(PolicyValidationError):
        parse_mirror_policy(
            "apiVersion: houba.io/v1alpha1\nkind: Wrong\nmetadata: {name: x}\n"
            "spec: {artifactType: image, source: {registry: d, repository: r}, "
            "imports: [{name: v, tags: {}}]}\n"
        )


def test_parse_rejects_non_mapping() -> None:
    with pytest.raises(PolicyValidationError, match="mapping"):
        parse_mirror_policy("- just\n- a\n- list\n")


def test_parse_rejects_invalid_yaml() -> None:
    with pytest.raises(PolicyValidationError, match="YAML"):
        parse_mirror_policy("key: : :\n")


def test_parse_wraps_validation_error() -> None:
    # missing artifactType → pydantic ValidationError wrapped as PolicyValidationError
    with pytest.raises(PolicyValidationError):
        parse_mirror_policy(
            "apiVersion: houba.io/v1alpha1\nkind: MirrorPolicy\nmetadata: {name: x}\n"
            "spec: {source: {registry: d, repository: r}, imports: [{name: v, tags: {}}]}\n"
        )
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -k parse -v`
Expected: FAIL — import errors for `MirrorPolicy` / `parse_mirror_policy`.

- [ ] **Step 3: Implement**

Add to `houba/domain/mirror_policy.py`:

```python
from typing import Literal

import yaml
from pydantic import ValidationError


class Metadata(_CamelModel):
    name: str
    labels: dict[str, str] = Field(default_factory=dict)


class MirrorPolicy(_CamelModel):
    api_version: Literal["houba.io/v1alpha1"]
    kind: Literal["MirrorPolicy"]
    metadata: Metadata
    spec: Spec


def parse_mirror_policy(text: str) -> MirrorPolicy:
    """Parse and validate a MirrorPolicy YAML document.

    Raises PolicyValidationError on malformed YAML, a non-mapping root, an unknown
    field, a wrong kind/apiVersion, or any schema/semantic violation.
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise PolicyValidationError(f"invalid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise PolicyValidationError("the root YAML document must be a mapping")
    try:
        return MirrorPolicy.model_validate(raw)
    except ValidationError as e:
        raise PolicyValidationError(str(e)) from e
```

Move `Literal`, `yaml`, `ValidationError` into the top import block. Keep `Metadata`/`MirrorPolicy` defined *after* `Spec`.

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add houba/domain/mirror_policy.py tests/unit/domain/test_mirror_policy.py
git commit -m "feat(domain): enveloppe MirrorPolicy + parse_mirror_policy"
```

---

## Task 9: JSON Schema export

**Files:**
- Modify: `houba/domain/mirror_policy.py`
- Test: `tests/unit/domain/test_mirror_policy.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_json_schema_is_emitted_with_camel_case_keys() -> None:
    from houba.domain.mirror_policy import mirror_policy_json_schema

    schema = mirror_policy_json_schema()
    assert schema["title"] == "MirrorPolicy"
    assert schema["type"] == "object"
    # camelCase property names (the public contract), not snake_case
    dumped = repr(schema)
    assert "artifactType" in dumped
    assert "includeRegex" in dumped
    assert "artifact_type" not in dumped


def test_json_schema_is_stable_and_serializable() -> None:
    import json

    from houba.domain.mirror_policy import mirror_policy_json_schema

    # must be JSON-serializable (publishable for editor/CI validation)
    json.dumps(mirror_policy_json_schema())
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -k json_schema -v`
Expected: FAIL — `ImportError: cannot import name 'mirror_policy_json_schema'`.

- [ ] **Step 3: Implement**

Add to `houba/domain/mirror_policy.py`:

```python
def mirror_policy_json_schema() -> dict[str, Any]:
    """The JSON Schema for a MirrorPolicy, keyed by the public (camelCase) field names.

    Published for editor/CI validation of policy files (see CLAUDE.md: JSON Schema
    systematically). Derived from the Pydantic models — never hand-written.
    """
    return MirrorPolicy.model_json_schema(by_alias=True)
```

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_mirror_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add houba/domain/mirror_policy.py tests/unit/domain/test_mirror_policy.py
git commit -m "feat(domain): export JSON Schema du MirrorPolicy (by_alias)"
```

---

## Task 10: `resolve_imports` — rule-B merge

Resolve `defaults` into each `import`: shallow-merge maps (`tags`, `archive`), replace lists (`transform`, `destinations`, `platforms`). Produces a list of fully-resolved imports with no remaining inheritance.

**Files:**
- Create: `houba/domain/policy_merge.py`
- Test: `tests/unit/domain/test_policy_merge.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/test_policy_merge.py`:

```python
from __future__ import annotations

from houba.domain.mirror_policy import Spec
from houba.domain.policy_merge import ResolvedImport, resolve_imports


def _spec(defaults: dict | None, imports: list[dict]) -> Spec:
    body: dict = {
        "artifactType": "image",
        "source": {"registry": "docker.io", "repository": "library/redis"},
        "imports": imports,
    }
    if defaults is not None:
        body["defaults"] = defaults
    return Spec.model_validate(body)


def test_import_inherits_all_defaults() -> None:
    spec = _spec(
        defaults={
            "platforms": ["linux/amd64"],
            "destinations": [{"registry": "eu", "project": "lib", "repository": "redis"}],
            "transform": [{"setTimezone": {"zone": "Europe/Paris"}}],
            "archive": {"keep": 2, "olderThanDays": 30},
            "tags": {"semverOnly": True, "excludeRegex": ["-rc"]},
        },
        imports=[{"name": "v7", "tags": {"includeRegex": "^7\\."}}],
    )
    [resolved] = resolve_imports(spec)
    assert isinstance(resolved, ResolvedImport)
    assert resolved.platforms == ["linux/amd64"]
    assert resolved.destinations[0].registry == "eu"
    assert resolved.transform[0].name == "setTimezone"
    assert resolved.archive.keep == 2
    # tags shallow-merge: includeRegex from import, semverOnly + excludeRegex from defaults
    assert resolved.tags.include_regex == "^7\\."
    assert resolved.tags.semver_only is True
    assert resolved.tags.exclude_regex == ["-rc"]


def test_tags_shallow_merge_import_overrides_key() -> None:
    spec = _spec(
        defaults={"tags": {"semverOnly": True, "excludeRegex": ["-rc"]}},
        imports=[{"name": "v", "tags": {"includeRegex": "^1\\.", "semverOnly": False}}],
    )
    [resolved] = resolve_imports(spec)
    assert resolved.tags.semver_only is False  # import wins
    assert resolved.tags.exclude_regex == ["-rc"]  # inherited
    assert resolved.tags.include_regex == "^1\\."


def test_transform_list_replaced_not_merged() -> None:
    spec = _spec(
        defaults={"transform": [{"injectCA": {}}, {"setTimezone": {}}]},
        imports=[{"name": "v", "tags": {}, "transform": [{"enableFips": {}}]}],
    )
    [resolved] = resolve_imports(spec)
    assert [s.name for s in resolved.transform] == ["enableFips"]  # replace, no append


def test_destinations_list_replaced() -> None:
    spec = _spec(
        defaults={"destinations": [{"registry": "eu", "project": "lib", "repository": "r"}]},
        imports=[
            {
                "name": "v",
                "tags": {},
                "destinations": [{"registry": "us", "project": "legacy", "repository": "r"}],
            }
        ],
    )
    [resolved] = resolve_imports(spec)
    assert [d.registry for d in resolved.destinations] == ["us"]


def test_missing_defaults_uses_import_only() -> None:
    spec = _spec(
        defaults=None,
        imports=[
            {
                "name": "v",
                "tags": {"includeRegex": "^1\\."},
                "destinations": [{"project": "lib", "repository": "r"}],
                "platforms": ["linux/amd64"],
            }
        ],
    )
    [resolved] = resolve_imports(spec)
    assert resolved.destinations[0].project == "lib"
    assert resolved.platforms == ["linux/amd64"]
    assert resolved.archive is None  # no default, none on import
    assert resolved.transform == []  # no transform anywhere ⇒ empty list


def test_empty_tags_inherits_defaults_tags_wholesale() -> None:
    spec = _spec(
        defaults={"tags": {"semverOnly": False, "excludeRegex": ["-rc"]}},
        imports=[{"name": "v", "tags": {}}],
    )
    [resolved] = resolve_imports(spec)
    # import.tags sets no fields (model_fields_set is empty) → inherit defaults wholesale.
    # semverOnly comes from the default (False), NOT the model default (True): merge is
    # presence-based, so an omitted field is inherited, not overridden by its model default.
    assert resolved.tags.semver_only is False
    assert resolved.tags.exclude_regex == ["-rc"]
```

Note: the merge is **presence-based** — `_merge_tags` overlays only the fields in the import's `model_fields_set` (the keys actually present in the YAML) onto the defaults. A field the import omitted is inherited; Pydantic default values do not count as "set". This is why an import with `tags: {}` inherits the default's `semverOnly` rather than re-asserting the model default.

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_policy_merge.py -v`
Expected: FAIL — `ModuleNotFoundError: houba.domain.policy_merge`.

- [ ] **Step 3: Implement**

Create `houba/domain/policy_merge.py`:

```python
"""Resolve `defaults` into each `import` (spec §3.4, rule B).

Maps (`tags`, `archive`) shallow-merge key-by-key, one level; lists (`transform`,
`destinations`, `platforms`) replace wholesale. Merge is decided on *field presence
in the raw input*, so a field the import omitted is taken from defaults — Pydantic
default values do not count as "present".
"""

from __future__ import annotations

from dataclasses import dataclass

from houba.domain.mirror_policy import (
    Archive,
    Destination,
    Spec,
    TagSelection,
    TransformStep,
)


@dataclass(frozen=True)
class ResolvedImport:
    name: str
    tags: TagSelection
    destinations: list[Destination] | None
    transform: list[TransformStep]
    archive: Archive | None
    platforms: list[str] | None


def _merge_tags(default: TagSelection | None, override: TagSelection) -> TagSelection:
    if default is None:
        return override
    # shallow-merge: a field the override set explicitly wins; otherwise inherit.
    # `model_fields_set` tells us which fields were explicitly provided.
    merged = default.model_dump(by_alias=False)
    for field in override.model_fields_set:
        merged[field] = getattr(override, field)
    return TagSelection.model_validate(merged)


def resolve_imports(spec: Spec) -> list[ResolvedImport]:
    d = spec.defaults
    resolved: list[ResolvedImport] = []
    for imp in spec.imports:
        tags = imp.tags if d is None or d.tags is None else _merge_tags(d.tags, imp.tags)
        destinations = imp.destinations if imp.destinations is not None else (
            d.destinations if d else None
        )
        transform = imp.transform if imp.transform is not None else (
            (d.transform if d else None) or []
        )
        archive = imp.archive if imp.archive is not None else (d.archive if d else None)
        platforms = imp.platforms if imp.platforms is not None else (d.platforms if d else None)
        resolved.append(
            ResolvedImport(
                name=imp.name,
                tags=tags,
                destinations=destinations,
                transform=transform,
                archive=archive,
                platforms=platforms,
            )
        )
    return resolved
```

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_policy_merge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add houba/domain/policy_merge.py tests/unit/domain/test_policy_merge.py
git commit -m "feat(domain): resolve_imports — merge defaults→import (règle B)"
```

---

## Task 11: post-merge validation — `transform` + multi-platform ⇒ error

The multi-platform-rebuild restriction (spec §6.2) is checked on the *resolved* import: if it has transform steps and more than one platform, fail. Generic policies never reach here (they have no transform — Task 7).

**Files:**
- Modify: `houba/domain/policy_merge.py`
- Test: `tests/unit/domain/test_policy_merge.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/domain/test_policy_merge.py`:

```python
import pytest

from houba.errors import PolicyValidationError


def test_transform_plus_multi_platform_raises() -> None:
    spec = _spec(
        defaults={"platforms": ["linux/amd64", "linux/arm64"]},
        imports=[{"name": "v", "tags": {}, "transform": [{"injectCA": {}}]}],
    )
    with pytest.raises(PolicyValidationError, match="multi-platform"):
        resolve_imports(spec)


def test_transform_plus_single_platform_ok() -> None:
    spec = _spec(
        defaults={"platforms": ["linux/amd64"]},
        imports=[{"name": "v", "tags": {}, "transform": [{"injectCA": {}}]}],
    )
    [resolved] = resolve_imports(spec)
    assert resolved.platforms == ["linux/amd64"]


def test_no_transform_with_multi_platform_ok() -> None:
    # copy path: multiple platforms allowed when there is no transform
    spec = _spec(
        defaults={"platforms": ["linux/amd64", "linux/arm64"]},
        imports=[{"name": "v", "tags": {}}],
    )
    [resolved] = resolve_imports(spec)
    assert resolved.platforms == ["linux/amd64", "linux/arm64"]
    assert resolved.transform == []
```

- [ ] **Step 2: Run it red**

Run: `uv run pytest tests/unit/domain/test_policy_merge.py -k platform -v`
Expected: FAIL — `resolve_imports` does not raise yet.

- [ ] **Step 3: Implement**

In `houba/domain/policy_merge.py`, add the check inside the loop just before appending (and import the error at the top):

```python
from houba.errors import PolicyValidationError
```

```python
        if transform and platforms is not None and len(platforms) > 1:
            raise PolicyValidationError(
                f"multi-platform rebuild is not supported (import '{imp.name}'): "
                f"a transform with more than one platform; specify a single platform "
                f"or remove the transform"
            )
```

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/unit/domain/test_policy_merge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add houba/domain/policy_merge.py tests/unit/domain/test_policy_merge.py
git commit -m "feat(domain): rejette transform + multi-plateforme (rebuild différé)"
```

---

## Task 12: Phase verification + coverage gate

**Files:** none — run the suite.

- [ ] **Step 1: Full domain suite + coverage**

```bash
uv run pytest tests/unit/domain -v --cov=houba.domain --cov-report=term-missing --cov-fail-under=90
```

Expected: all pass; `houba.domain` coverage ≥ 90 %.

- [ ] **Step 2: Full suite (nothing else broke)**

```bash
uv run pytest -q
```

Expected: the previous 152 tests still pass plus the new ones; `properties.py` and its tests are untouched (legacy path intact).

- [ ] **Step 3: Lint + types**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy houba
```

Expected: all clean. `mirror_policy.py` and `policy_merge.py` live in `domain/` → fully `mypy --strict`.

- [ ] **Step 4: Sanity — domain purity preserved**

```bash
grep -rn "import httpx\|import requests\|import subprocess\|os.environ" houba/domain/mirror_policy.py houba/domain/policy_merge.py || echo "OK pure"
```

Expected: `OK pure`.

- [ ] **Step 5: Generate and eyeball the JSON Schema**

```bash
uv run python -c "import json; from houba.domain.mirror_policy import mirror_policy_json_schema as s; print(json.dumps(s(), indent=2))" | head -40
```

Expected: a JSON Schema with camelCase property names (`artifactType`, `includeRegex`, `semverOnly`, `olderThanDays`).

---

## Acceptance criteria for this phase

- [ ] `parse_mirror_policy(yaml)` returns a validated `MirrorPolicy`, and raises `PolicyValidationError` (exit 1) on malformed YAML, non-mapping root, unknown field, wrong kind/apiVersion, missing `artifactType`, empty `imports`, or a `generic` policy with transform steps.
- [ ] `resolve_imports(spec)` implements rule B: `tags`/`archive` shallow-merge, `transform`/`destinations`/`platforms` replace; omitted fields inherit from `defaults`.
- [ ] A resolved import combining transform steps with > 1 platform raises `PolicyValidationError` (multi-platform rebuild deferred).
- [ ] `mirror_policy_json_schema()` emits a JSON-serializable schema with camelCase keys.
- [ ] `houba.domain` coverage ≥ 90 %; full suite green; ruff + mypy clean.
- [ ] Legacy `houba/domain/properties.py` untouched (removed only when the reconcile use case lands, Phase 7).

## Out of scope (later phases)

- Tag selection (regex/semver/names) and alias-template resolution — **Phase 2**.
- Reconcile-plan computation + change-detection via `base.digest` — **Phase 3**.
- Multi-registry config (env-roster) + composition root — **Phase 4**.
- regctl adapter + copy-and-annotate path (multi-arch copy) — **Phase 5**.
- `image` transform vocabulary + BuildKit rebuild — **Phase 6**.
- reconcile use case + CLI command + alias-collision detection + retiring `properties.py` — **Phase 7**.
