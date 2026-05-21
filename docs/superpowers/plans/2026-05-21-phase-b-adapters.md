# Phase B — Adapters (write-side + I/O complets) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compléter la couche `ports/` + `adapters/` du paquet `houba` avec toutes les opérations d'écriture (Harbor) et les nouveaux ports nécessaires aux use cases Phase C (BuildKit, Git, GitLab, Teams, EOL). Livrer une image Docker `houba` complète (skopeo + buildctl + git) publiée en CI sous le tag `v0-rc`.

**Architecture :** On reste en architecture hexagonale. Chaque port reste un `typing.Protocol` exposant des méthodes stables. Chaque adapter est testé en intégration isolée : HTTP via `respx`, CLI externes via fake-bins shell sous `tests/fake-bins/`. Aucun adapter ne fait d'I/O dans `domain/`. Aucune nouvelle logique métier : Phase B ne touche pas à `domain/`.

**Tech Stack :** Python 3.12, uv, httpx + tenacity (retry), pydantic v2, structlog, pytest + respx + syrupy, fake-bins POSIX shell, BuildKit (`buildctl`), skopeo, git CLI, Docker (image multi-stage).

**Branche de travail :** `feat/python-cli` (continue depuis Phase A — HEAD = `2309dbc`).

**Référence spec :** [docs/superpowers/specs/2026-05-21-refactor-groovy-to-python-cli-design.md](../specs/2026-05-21-refactor-groovy-to-python-cli-design.md) §4, §6.3, §7, §9.2.

---

## Carte des fichiers créés / modifiés en Phase B

```
houba/
├── ports/
│   ├── harbor.py                    MODIFIÉ : ajout dataclasses Label, ImmutableTagRule,
│   │                                          ArtifactTag ; méthodes write
│   ├── image_builder.py             NOUVEAU
│   ├── git_repo.py                  NOUVEAU
│   ├── gitlab.py                    NOUVEAU
│   ├── notifier.py                  NOUVEAU
│   └── eol_source.py                NOUVEAU
│
├── adapters/
│   ├── harbor_http.py               MODIFIÉ : méthodes write + retries POST/PUT/DELETE
│   ├── buildkit_cli.py              NOUVEAU
│   ├── git_cli.py                   NOUVEAU
│   ├── gitlab_http.py               NOUVEAU
│   ├── teams_webhook.py             NOUVEAU
│   └── endoflife_http.py            NOUVEAU
│
├── cli/
│   └── _di.py                       MODIFIÉ : composition root pour les 5 nouveaux adapters
│
└── errors.py                        (inchangé — toutes les exceptions existent déjà)

tests/
├── fakes/
│   ├── harbor.py                    MODIFIÉ : write methods + journal d'appels
│   ├── image_builder.py             NOUVEAU
│   ├── git_repo.py                  NOUVEAU
│   ├── gitlab.py                    NOUVEAU
│   ├── notifier.py                  NOUVEAU
│   └── eol_source.py                NOUVEAU
│
├── fake-bins/
│   ├── buildctl                     NOUVEAU
│   └── git                          NOUVEAU
│
├── unit/
│   ├── test_fakes_harbor.py         MODIFIÉ : couvre les nouvelles méthodes du fake
│   ├── test_fakes_image_builder.py  NOUVEAU
│   ├── test_fakes_git_repo.py       NOUVEAU
│   ├── test_fakes_gitlab.py         NOUVEAU
│   ├── test_fakes_notifier.py       NOUVEAU
│   └── test_fakes_eol_source.py     NOUVEAU
│
└── integration/
    ├── test_harbor_http.py          MODIFIÉ : tests write-side (POST/PUT/DELETE)
    ├── test_buildkit_cli.py         NOUVEAU
    ├── test_git_cli.py              NOUVEAU
    ├── test_gitlab_http.py          NOUVEAU
    ├── test_teams_webhook.py        NOUVEAU
    └── test_endoflife_http.py       NOUVEAU

Dockerfile                           MODIFIÉ : ajout skopeo + buildctl + git dans la runtime
.gitlab-ci.yml                       MODIFIÉ : ajout job python:publish:image (tag v0-rc)
pyproject.toml                       (inchangé — pas de nouvelle dépendance)
```

---

## Préambule — état attendu au début

- HEAD = `2309dbc` (`chore(gitignore): ignore .serena/`), branche `feat/python-cli`.
- `uv run ruff check . && uv run mypy houba && uv run pytest` passe (91 tests, 94.5 % coverage global, 96.2 % sur `domain/`).
- Aucune dépendance Python à ajouter : tout le stack Phase A suffit.
- Les fake-bins existants (`tests/fake-bins/skopeo`) sont déjà branchés via la fixture `fake_bin_path` dans `tests/conftest.py:11-17`.

---

## Groupe 1 — Harbor write-side

Étend le `HarborPort` et le `HarborHttpAdapter` avec les opérations d'écriture utilisées par les use cases Phase C : suppression d'artefact, gestion des tags, labels OCI, immutable tag rules.

### Task 1 : Étendre `HarborPort` (dataclasses + signatures `Protocol`)

**Files:**
- Modify: `houba/ports/harbor.py`
- Modify: `tests/fakes/harbor.py` (juste pour rendre l'ancien fake compatible)

- [ ] **Step 1 : Écrire le test de la nouvelle surface du port**

Créer `tests/unit/test_ports_harbor.py` :

```python
from __future__ import annotations

from typing import get_type_hints

from houba.ports.harbor import (
    Artifact,
    ArtifactTag,
    HarborPort,
    ImmutableTagRule,
    Label,
    Repository,
)


def test_label_dataclass_has_id_and_name() -> None:
    lab = Label(id=42, name="fr.sncf.h2h.source.tag=1.36")
    assert lab.id == 42
    assert lab.name == "fr.sncf.h2h.source.tag=1.36"


def test_artifact_tag_dataclass() -> None:
    t = ArtifactTag(name="1.36", immutable=False)
    assert t.name == "1.36"
    assert t.immutable is False


def test_immutable_tag_rule_dataclass() -> None:
    r = ImmutableTagRule(
        id=1,
        scope_selector="**",
        tag_selector="*",
        disabled=False,
    )
    assert r.id == 1
    assert r.disabled is False


def test_harbor_port_exposes_expected_methods() -> None:
    hints = get_type_hints(HarborPort)
    # Verifies dataclasses are importable as type hints from the port module.
    assert hints == {}  # Protocol has no annotated attrs ; methods are tested via FakeHarborPort


def test_harbor_port_protocol_runtime_check() -> None:
    """FakeHarborPort doit satisfaire HarborPort (protocole structurel)."""
    from tests.fakes.harbor import FakeHarborPort

    fake: HarborPort = FakeHarborPort()
    # Les méthodes read et write doivent toutes être présentes
    assert callable(fake.get_repositories)
    assert callable(fake.get_artifacts)
    assert callable(fake.get_artifact)
    assert callable(fake.list_artifact_tags)
    assert callable(fake.delete_repository)
    assert callable(fake.delete_artifact)
    assert callable(fake.create_artifact_tag)
    assert callable(fake.delete_artifact_tag)
    assert callable(fake.ensure_label)
    assert callable(fake.add_label_to_artifact)
    assert callable(fake.list_immutable_tag_rules)
    assert callable(fake.update_immutable_tag_rule)
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

```bash
uv run pytest tests/unit/test_ports_harbor.py -v
```

Expected : `ImportError` ou `AttributeError` sur `Label`, `ArtifactTag`, `ImmutableTagRule`.

- [ ] **Step 3 : Étendre `houba/ports/harbor.py`**

Remplacer entièrement le fichier par :

```python
"""Port d'accès à Harbor v2 (lectures + écritures).

Voir spec §4, §7.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Repository:
    name: str
    project_id: int
    artifact_count: int = 0


@dataclass(frozen=True)
class Artifact:
    digest: str
    tags: list[str] = field(default_factory=list)
    push_time: str = ""
    labels: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArtifactTag:
    name: str
    immutable: bool = False


@dataclass(frozen=True)
class Label:
    id: int
    name: str


@dataclass(frozen=True)
class ImmutableTagRule:
    id: int
    scope_selector: str
    tag_selector: str
    disabled: bool = False


class HarborPort(Protocol):
    # ---- Reads ----
    def get_repositories(self, project_name: str) -> list[Repository]: ...
    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]: ...
    def get_artifact(
        self, project_name: str, repository_name: str, reference: str
    ) -> Artifact: ...
    def list_artifact_tags(
        self, project_name: str, repository_name: str, reference: str
    ) -> list[ArtifactTag]: ...
    def list_immutable_tag_rules(self, project_name: str) -> list[ImmutableTagRule]: ...

    # ---- Writes ----
    def delete_repository(self, project_name: str, repository_name: str) -> None: ...
    def delete_artifact(
        self, project_name: str, repository_name: str, reference: str
    ) -> None: ...
    def create_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None: ...
    def delete_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None: ...
    def ensure_label(self, name: str) -> Label: ...
    def add_label_to_artifact(
        self,
        project_name: str,
        repository_name: str,
        reference: str,
        label_id: int,
    ) -> None: ...
    def update_immutable_tag_rule(
        self,
        project_name: str,
        rule_id: int,
        scope_selector: str,
        tag_selector: str,
        disabled: bool,
    ) -> None: ...
```

- [ ] **Step 4 : Étendre `tests/fakes/harbor.py`**

Remplacer entièrement par :

```python
from __future__ import annotations

from dataclasses import dataclass, field

from houba.errors import HarborNotFoundError
from houba.ports.harbor import (
    Artifact,
    ArtifactTag,
    ImmutableTagRule,
    Label,
    Repository,
)


@dataclass
class _Recorded:
    """Journal d'appels pour vérification dans les tests use cases."""

    deleted_repositories: list[tuple[str, str]] = field(default_factory=list)
    deleted_artifacts: list[tuple[str, str, str]] = field(default_factory=list)
    deleted_artifact_tags: list[tuple[str, str, str, str]] = field(default_factory=list)
    created_artifact_tags: list[tuple[str, str, str, str]] = field(default_factory=list)
    added_labels: list[tuple[str, str, str, int]] = field(default_factory=list)
    updated_immutable_rules: list[tuple[str, int, str, str, bool]] = field(default_factory=list)


class FakeHarborPort:
    def __init__(
        self,
        repositories: dict[str, list[Repository]] | None = None,
        artifacts: dict[tuple[str, str], list[Artifact]] | None = None,
        tags_by_artifact: dict[tuple[str, str, str], list[ArtifactTag]] | None = None,
        immutable_rules: dict[str, list[ImmutableTagRule]] | None = None,
        labels: list[Label] | None = None,
    ) -> None:
        self._repositories = repositories or {}
        self._artifacts = artifacts or {}
        self._tags_by_artifact = tags_by_artifact or {}
        self._immutable_rules = immutable_rules or {}
        self._labels: dict[str, Label] = {lab.name: lab for lab in (labels or [])}
        self._next_label_id = max((lab.id for lab in self._labels.values()), default=0) + 1
        self.calls = _Recorded()

    # ---- Reads ----
    def get_repositories(self, project_name: str) -> list[Repository]:
        return list(self._repositories.get(project_name, []))

    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]:
        return list(self._artifacts.get((project_name, repository_name), []))

    def get_artifact(
        self, project_name: str, repository_name: str, reference: str
    ) -> Artifact:
        for art in self._artifacts.get((project_name, repository_name), []):
            if art.digest == reference or reference in art.tags:
                return art
        raise HarborNotFoundError(
            f"{project_name}/{repository_name}@{reference} not found in fake"
        )

    def list_artifact_tags(
        self, project_name: str, repository_name: str, reference: str
    ) -> list[ArtifactTag]:
        return list(self._tags_by_artifact.get((project_name, repository_name, reference), []))

    def list_immutable_tag_rules(self, project_name: str) -> list[ImmutableTagRule]:
        return list(self._immutable_rules.get(project_name, []))

    # ---- Writes ----
    def delete_repository(self, project_name: str, repository_name: str) -> None:
        self.calls.deleted_repositories.append((project_name, repository_name))

    def delete_artifact(
        self, project_name: str, repository_name: str, reference: str
    ) -> None:
        self.calls.deleted_artifacts.append((project_name, repository_name, reference))

    def create_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None:
        self.calls.created_artifact_tags.append(
            (project_name, repository_name, reference, tag)
        )

    def delete_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None:
        self.calls.deleted_artifact_tags.append(
            (project_name, repository_name, reference, tag)
        )

    def ensure_label(self, name: str) -> Label:
        if name in self._labels:
            return self._labels[name]
        lab = Label(id=self._next_label_id, name=name)
        self._labels[name] = lab
        self._next_label_id += 1
        return lab

    def add_label_to_artifact(
        self,
        project_name: str,
        repository_name: str,
        reference: str,
        label_id: int,
    ) -> None:
        self.calls.added_labels.append(
            (project_name, repository_name, reference, label_id)
        )

    def update_immutable_tag_rule(
        self,
        project_name: str,
        rule_id: int,
        scope_selector: str,
        tag_selector: str,
        disabled: bool,
    ) -> None:
        self.calls.updated_immutable_rules.append(
            (project_name, rule_id, scope_selector, tag_selector, disabled)
        )
```

- [ ] **Step 5 : Relancer le test**

```bash
uv run pytest tests/unit/test_ports_harbor.py -v
```

Expected : 4 passed.

- [ ] **Step 6 : Vérifier qu'on n'a rien cassé**

```bash
uv run pytest tests/unit -v
uv run mypy houba
uv run ruff check .
```

Expected : tout vert.

- [ ] **Step 7 : Commit**

```bash
git add houba/ports/harbor.py tests/fakes/harbor.py tests/unit/test_ports_harbor.py
git commit -m "feat(ports): étend HarborPort avec dataclasses et méthodes write"
```

---

### Task 2 : Étendre `FakeHarborPort` (tests dédiés)

**Files:**
- Modify: `tests/unit/test_fakes_harbor.py`

- [ ] **Step 1 : Lire l'existant**

```bash
sed -n '1,40p' tests/unit/test_fakes_harbor.py
```

- [ ] **Step 2 : Ajouter les tests des nouvelles méthodes**

Append à `tests/unit/test_fakes_harbor.py` :

```python
import pytest

from houba.errors import HarborNotFoundError
from houba.ports.harbor import (
    Artifact,
    ArtifactTag,
    ImmutableTagRule,
    Label,
)
from tests.fakes.harbor import FakeHarborPort


def test_get_artifact_by_digest() -> None:
    art = Artifact(digest="sha256:abc", tags=["1.36"])
    fake = FakeHarborPort(artifacts={("lib", "busybox"): [art]})
    assert fake.get_artifact("lib", "busybox", "sha256:abc") == art


def test_get_artifact_by_tag() -> None:
    art = Artifact(digest="sha256:abc", tags=["1.36", "latest"])
    fake = FakeHarborPort(artifacts={("lib", "busybox"): [art]})
    assert fake.get_artifact("lib", "busybox", "latest") == art


def test_get_artifact_missing_raises() -> None:
    fake = FakeHarborPort()
    with pytest.raises(HarborNotFoundError):
        fake.get_artifact("lib", "busybox", "missing")


def test_list_artifact_tags() -> None:
    tags = [ArtifactTag(name="1.36"), ArtifactTag(name="latest", immutable=True)]
    fake = FakeHarborPort(tags_by_artifact={("lib", "busybox", "sha256:abc"): tags})
    assert fake.list_artifact_tags("lib", "busybox", "sha256:abc") == tags


def test_list_immutable_tag_rules() -> None:
    rule = ImmutableTagRule(id=1, scope_selector="**", tag_selector="*", disabled=False)
    fake = FakeHarborPort(immutable_rules={"lib": [rule]})
    assert fake.list_immutable_tag_rules("lib") == [rule]


def test_delete_repository_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.delete_repository("lib", "busybox")
    assert fake.calls.deleted_repositories == [("lib", "busybox")]


def test_delete_artifact_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.delete_artifact("lib", "busybox", "sha256:abc")
    assert fake.calls.deleted_artifacts == [("lib", "busybox", "sha256:abc")]


def test_create_and_delete_tags_are_journaled() -> None:
    fake = FakeHarborPort()
    fake.create_artifact_tag("lib", "busybox", "sha256:abc", "1.36")
    fake.delete_artifact_tag("lib", "busybox", "sha256:abc", "old")
    assert fake.calls.created_artifact_tags == [("lib", "busybox", "sha256:abc", "1.36")]
    assert fake.calls.deleted_artifact_tags == [("lib", "busybox", "sha256:abc", "old")]


def test_ensure_label_returns_existing() -> None:
    pre = Label(id=7, name="fr.sncf.h2h.source.tag=1.36")
    fake = FakeHarborPort(labels=[pre])
    assert fake.ensure_label("fr.sncf.h2h.source.tag=1.36") is pre


def test_ensure_label_creates_when_missing() -> None:
    fake = FakeHarborPort()
    lab = fake.ensure_label("fr.sncf.h2h.source.tag=1.36")
    assert lab.id >= 1
    assert lab.name == "fr.sncf.h2h.source.tag=1.36"
    # Second call returns same label
    assert fake.ensure_label("fr.sncf.h2h.source.tag=1.36").id == lab.id


def test_add_label_to_artifact_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.add_label_to_artifact("lib", "busybox", "sha256:abc", 7)
    assert fake.calls.added_labels == [("lib", "busybox", "sha256:abc", 7)]


def test_update_immutable_tag_rule_is_journaled() -> None:
    fake = FakeHarborPort()
    fake.update_immutable_tag_rule("lib", 1, "**", "v*", True)
    assert fake.calls.updated_immutable_rules == [("lib", 1, "**", "v*", True)]
```

- [ ] **Step 3 : Lancer les tests**

```bash
uv run pytest tests/unit/test_fakes_harbor.py -v
```

Expected : tous passent (3 anciens + 12 nouveaux).

- [ ] **Step 4 : Commit**

```bash
git add tests/unit/test_fakes_harbor.py
git commit -m "test(fakes): couvre les méthodes write de FakeHarborPort"
```

---

### Task 3 : Étendre `HarborHttpAdapter` — reads manquants

**Files:**
- Modify: `houba/adapters/harbor_http.py`
- Modify: `tests/integration/test_harbor_http.py`

- [ ] **Step 1 : Écrire les tests des reads manquants**

Append à `tests/integration/test_harbor_http.py` :

```python
def test_get_artifact_by_tag(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        body = {
            "digest": "sha256:abc",
            "tags": [{"name": "1.36"}, {"name": "latest"}],
            "push_time": "2026-05-21T12:00:00Z",
            "labels": [{"name": "fr.sncf.h2h.source.tag=1.36"}],
        }
        router.get(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/latest"
        ).respond(200, json=body)
        art = adapter.get_artifact("lib", "busybox", "latest")
        assert art.digest == "sha256:abc"
        assert art.tags == ["1.36", "latest"]


def test_get_artifact_double_encodes_repo(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.get(
            "/api/v2.0/projects/lib/repositories/foo%252Fbar/artifacts/sha256:abc"
        ).respond(200, json={"digest": "sha256:abc"})
        adapter.get_artifact("lib", "foo/bar", "sha256:abc")
        assert route.called


def test_list_artifact_tags(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        body = [{"name": "1.36", "immutable": False}, {"name": "latest", "immutable": True}]
        router.get(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/sha256:abc/tags",
            params={"page": "1", "page_size": "100"},
        ).respond(200, json=body)
        router.get(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/sha256:abc/tags",
            params={"page": "2", "page_size": "100"},
        ).respond(200, json=[])
        tags = adapter.list_artifact_tags("lib", "busybox", "sha256:abc")
        assert tags == [
            ArtifactTag(name="1.36", immutable=False),
            ArtifactTag(name="latest", immutable=True),
        ]


def test_list_immutable_tag_rules(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        body = [
            {
                "id": 1,
                "scope_selector": {"repository": {"decoration": "**"}},
                "tag_selector": {"decoration": "matches", "pattern": "v*"},
                "disabled": False,
            }
        ]
        router.get(
            "/api/v2.0/projects/lib/immutabletagrules",
            params={"page": "1", "page_size": "100"},
        ).respond(200, json=body)
        router.get(
            "/api/v2.0/projects/lib/immutabletagrules",
            params={"page": "2", "page_size": "100"},
        ).respond(200, json=[])
        rules = adapter.list_immutable_tag_rules("lib")
        assert rules == [
            ImmutableTagRule(id=1, scope_selector="**", tag_selector="v*", disabled=False),
        ]
```

Ajouter en tête du fichier :

```python
from houba.ports.harbor import ArtifactTag, ImmutableTagRule
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

```bash
uv run pytest tests/integration/test_harbor_http.py::test_get_artifact_by_tag -v
```

Expected : `AttributeError: 'HarborHttpAdapter' object has no attribute 'get_artifact'`.

- [ ] **Step 3 : Implémenter les méthodes read manquantes**

Ajouter dans `houba/adapters/harbor_http.py` (après `get_artifacts`) :

```python
    def get_artifact(
        self, project_name: str, repository_name: str, reference: str
    ) -> Artifact:
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
        ref_encoded = quote(reference, safe=":")
        path = f"/projects/{project_name}/repositories/{repo_encoded}/artifacts/{ref_encoded}"
        item = self._get(path)
        return Artifact(
            digest=item["digest"],
            tags=[t["name"] for t in (item.get("tags") or [])],
            push_time=item.get("push_time", ""),
            labels=[lab["name"] for lab in (item.get("labels") or [])],
        )

    def list_artifact_tags(
        self, project_name: str, repository_name: str, reference: str
    ) -> list[ArtifactTag]:
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
        ref_encoded = quote(reference, safe=":")
        path = (
            f"/projects/{project_name}/repositories/{repo_encoded}"
            f"/artifacts/{ref_encoded}/tags"
        )
        items = list(self._paginate(path))
        return [ArtifactTag(name=i["name"], immutable=i.get("immutable", False)) for i in items]

    def list_immutable_tag_rules(self, project_name: str) -> list[ImmutableTagRule]:
        path = f"/projects/{project_name}/immutabletagrules"
        items = list(self._paginate(path))
        return [_parse_immutable_rule(i) for i in items]
```

Et en bas du fichier, fonction utilitaire :

```python
def _parse_immutable_rule(payload: dict[str, Any]) -> ImmutableTagRule:
    scope = payload.get("scope_selector") or {}
    scope_repo = scope.get("repository") or {}
    tag = payload.get("tag_selector") or {}
    return ImmutableTagRule(
        id=payload["id"],
        scope_selector=scope_repo.get("decoration", "**"),
        tag_selector=tag.get("pattern", "*"),
        disabled=payload.get("disabled", False),
    )
```

Et en tête, mettre à jour l'import :

```python
from houba.ports.harbor import Artifact, ArtifactTag, ImmutableTagRule, Repository
```

- [ ] **Step 4 : Relancer**

```bash
uv run pytest tests/integration/test_harbor_http.py -v
uv run mypy houba
```

Expected : tous passent.

- [ ] **Step 5 : Commit**

```bash
git add houba/adapters/harbor_http.py tests/integration/test_harbor_http.py
git commit -m "feat(adapters): HarborHttpAdapter ajoute get_artifact / list_artifact_tags / list_immutable_tag_rules"
```

---

### Task 4 : Étendre `HarborHttpAdapter` — méthodes write

**Files:**
- Modify: `houba/adapters/harbor_http.py`
- Modify: `tests/integration/test_harbor_http.py`

- [ ] **Step 1 : Écrire les tests write**

Append à `tests/integration/test_harbor_http.py` :

```python
from houba.ports.harbor import Label  # ajout en tête


def test_delete_repository(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.delete("/api/v2.0/projects/lib/repositories/busybox").respond(200)
        adapter.delete_repository("lib", "busybox")
        assert route.called


def test_delete_artifact(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.delete(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/sha256:abc"
        ).respond(200)
        adapter.delete_artifact("lib", "busybox", "sha256:abc")
        assert route.called


def test_create_artifact_tag(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.post(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/sha256:abc/tags",
            json={"name": "1.36"},
        ).respond(201)
        adapter.create_artifact_tag("lib", "busybox", "sha256:abc", "1.36")
        assert route.called


def test_delete_artifact_tag(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.delete(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/sha256:abc/tags/old"
        ).respond(200)
        adapter.delete_artifact_tag("lib", "busybox", "sha256:abc", "old")
        assert route.called


def test_ensure_label_returns_existing(adapter: HarborHttpAdapter) -> None:
    """L'API Harbor expose /labels (global) ; on cherche d'abord par name."""
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get(
            "/api/v2.0/labels",
            params={"name": "fr.sncf.h2h.source.tag=1.36", "scope": "g"},
        ).respond(200, json=[{"id": 7, "name": "fr.sncf.h2h.source.tag=1.36"}])
        lab = adapter.ensure_label("fr.sncf.h2h.source.tag=1.36")
        assert lab == Label(id=7, name="fr.sncf.h2h.source.tag=1.36")


def test_ensure_label_creates_when_missing(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get(
            "/api/v2.0/labels",
            params={"name": "fr.sncf.h2h.source.tag=new", "scope": "g"},
        ).respond(200, json=[])
        create_route = router.post(
            "/api/v2.0/labels",
            json={"name": "fr.sncf.h2h.source.tag=new", "scope": "g"},
        ).respond(
            201,
            headers={"Location": "/api/v2.0/labels/42"},
        )
        lab = adapter.ensure_label("fr.sncf.h2h.source.tag=new")
        assert create_route.called
        assert lab == Label(id=42, name="fr.sncf.h2h.source.tag=new")


def test_add_label_to_artifact(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.post(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/sha256:abc/labels",
            json={"id": 7, "name": "fr.sncf.h2h.source.tag=1.36"},
        ).respond(200)
        adapter.add_label_to_artifact("lib", "busybox", "sha256:abc", 7)
        assert route.called


def test_update_immutable_tag_rule(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.put("/api/v2.0/projects/lib/immutabletagrules/1").respond(200)
        adapter.update_immutable_tag_rule(
            "lib", 1, scope_selector="**", tag_selector="v*", disabled=True
        )
        assert route.called


def test_write_transient_5xx_is_retried(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        responses = [httpx.Response(503), httpx.Response(503), httpx.Response(200)]
        route = router.delete(
            "/api/v2.0/projects/lib/repositories/busybox"
        ).mock(side_effect=responses)
        adapter.delete_repository("lib", "busybox")
        assert route.call_count == 3


def test_write_404_raises_not_found(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.delete(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/sha256:bad"
        ).respond(404)
        with pytest.raises(HarborNotFoundError):
            adapter.delete_artifact("lib", "busybox", "sha256:bad")
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

```bash
uv run pytest tests/integration/test_harbor_http.py::test_delete_repository -v
```

Expected : `AttributeError`.

- [ ] **Step 3 : Implémenter les méthodes write dans `harbor_http.py`**

Ajouter dans `HarborHttpAdapter`, après `list_immutable_tag_rules` :

```python
    def delete_repository(self, project_name: str, repository_name: str) -> None:
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
        self._request("DELETE", f"/projects/{project_name}/repositories/{repo_encoded}")

    def delete_artifact(
        self, project_name: str, repository_name: str, reference: str
    ) -> None:
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
        ref_encoded = quote(reference, safe=":")
        self._request(
            "DELETE",
            f"/projects/{project_name}/repositories/{repo_encoded}/artifacts/{ref_encoded}",
        )

    def create_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None:
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
        ref_encoded = quote(reference, safe=":")
        self._request(
            "POST",
            f"/projects/{project_name}/repositories/{repo_encoded}"
            f"/artifacts/{ref_encoded}/tags",
            json={"name": tag},
        )

    def delete_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None:
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
        ref_encoded = quote(reference, safe=":")
        self._request(
            "DELETE",
            f"/projects/{project_name}/repositories/{repo_encoded}"
            f"/artifacts/{ref_encoded}/tags/{tag}",
        )

    def ensure_label(self, name: str) -> Label:
        # Harbor labels sont globaux (scope="g"). On cherche d'abord par name exact.
        existing = self._get("/labels", params={"name": name, "scope": "g"})
        if existing:
            return Label(id=existing[0]["id"], name=existing[0]["name"])
        response = self._request_full("POST", "/labels", json={"name": name, "scope": "g"})
        # Harbor renvoie 201 avec Location: /api/v2.0/labels/<id>
        location = response.headers.get("Location", "")
        try:
            new_id = int(location.rsplit("/", 1)[-1])
        except (ValueError, IndexError) as e:
            raise HarborError(
                f"Cannot parse Location header from label creation: {location!r}"
            ) from e
        return Label(id=new_id, name=name)

    def add_label_to_artifact(
        self,
        project_name: str,
        repository_name: str,
        reference: str,
        label_id: int,
    ) -> None:
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
        ref_encoded = quote(reference, safe=":")
        self._request(
            "POST",
            f"/projects/{project_name}/repositories/{repo_encoded}"
            f"/artifacts/{ref_encoded}/labels",
            json={"id": label_id},
        )

    def update_immutable_tag_rule(
        self,
        project_name: str,
        rule_id: int,
        scope_selector: str,
        tag_selector: str,
        disabled: bool,
    ) -> None:
        body = {
            "scope_selector": {"repository": {"decoration": scope_selector}},
            "tag_selector": {"decoration": "matches", "pattern": tag_selector},
            "disabled": disabled,
        }
        self._request(
            "PUT",
            f"/projects/{project_name}/immutabletagrules/{rule_id}",
            json=body,
        )
```

Ajouter la méthode `_request` (qui factorise les non-GET) au même endroit que `_get` :

```python
    @retry(
        retry=retry_if_exception_type(HarborTransientError),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, max=2.0),
        reraise=True,
    )
    def _request(
        self, method: str, path: str, *, json: Any = None, params: dict[str, Any] | None = None
    ) -> Any:
        return self._call(method, path, json=json, params=params).json() or None

    @retry(
        retry=retry_if_exception_type(HarborTransientError),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, max=2.0),
        reraise=True,
    )
    def _request_full(
        self, method: str, path: str, *, json: Any = None
    ) -> httpx.Response:
        """Comme `_request` mais retourne la réponse brute (utile pour les headers)."""
        return self._call(method, path, json=json, params=None)

    def _call(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            r = self._client.request(method, self._base + path, json=json, params=params)
        except httpx.HTTPError as e:
            raise HarborTransientError(str(e)) from e
        if r.status_code in (401, 403):
            raise HarborAuthError(f"{r.status_code}: {r.text}")
        if r.status_code == 404:
            raise HarborNotFoundError(f"{path}: {r.text}")
        if 500 <= r.status_code < 600:
            raise HarborTransientError(f"{r.status_code}: {r.text}")
        if not r.is_success:
            raise HarborError(f"{r.status_code}: {r.text}")
        return r
```

Refactorer `_get` pour réutiliser `_call` (remplacement complet) :

```python
    @retry(
        retry=retry_if_exception_type(HarborTransientError),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, max=2.0),
        reraise=True,
    )
    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._call("GET", path, params=params).json()
```

Et l'import en tête : ajouter `Label` dans la ligne d'import de ports.

- [ ] **Step 4 : Relancer toute l'intégration Harbor**

```bash
uv run pytest tests/integration/test_harbor_http.py -v
uv run mypy houba
uv run ruff check .
```

Expected : tous verts (15+ tests).

- [ ] **Step 5 : Commit**

```bash
git add houba/adapters/harbor_http.py tests/integration/test_harbor_http.py
git commit -m "feat(adapters): HarborHttpAdapter ajoute les méthodes write (delete, tags, labels, rules)"
```

---

## Groupe 2 — ImageBuilder (BuildKit)

Wrapper subprocess autour de `buildctl` pour builder une image OCI à partir d'un Dockerfile et la pousser sur Harbor.

### Task 5 : Port `image_builder.py`

**Files:**
- Create: `houba/ports/image_builder.py`
- Create: `tests/fakes/image_builder.py`
- Create: `tests/unit/test_fakes_image_builder.py`

- [ ] **Step 1 : Écrire le test du fake**

`tests/unit/test_fakes_image_builder.py` :

```python
from __future__ import annotations

from pathlib import Path

from houba.ports.image_builder import BuildRequest
from tests.fakes.image_builder import FakeImageBuilder


def test_fake_records_build_requests(tmp_path: Path) -> None:
    fake = FakeImageBuilder()
    req = BuildRequest(
        dockerfile_path=tmp_path / "Dockerfile",
        context_dir=tmp_path,
        image_ref="harbor.example.com/lib/busybox:1.36",
        build_args={"VERSION": "1.36"},
    )
    fake.build_and_push(req)
    assert fake.requests == [req]


def test_fake_simulates_failure() -> None:
    fake = FakeImageBuilder(fail=True)
    import pytest

    from houba.errors import BuildkitError

    with pytest.raises(BuildkitError):
        fake.build_and_push(
            BuildRequest(
                dockerfile_path=Path("/x"),
                context_dir=Path("/x"),
                image_ref="x",
                build_args={},
            )
        )
```

- [ ] **Step 2 : Vérifier qu'il échoue**

```bash
uv run pytest tests/unit/test_fakes_image_builder.py -v
```

Expected : `ImportError`.

- [ ] **Step 3 : Écrire le port**

`houba/ports/image_builder.py` :

```python
"""Port d'accès à un builder d'images OCI (BuildKit en prod)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class BuildRequest:
    dockerfile_path: Path
    context_dir: Path
    image_ref: str
    build_args: dict[str, str] = field(default_factory=dict)


class ImageBuilderPort(Protocol):
    def build_and_push(self, request: BuildRequest) -> None: ...
```

- [ ] **Step 4 : Écrire le fake**

`tests/fakes/image_builder.py` :

```python
from __future__ import annotations

from houba.errors import BuildkitError
from houba.ports.image_builder import BuildRequest


class FakeImageBuilder:
    def __init__(self, *, fail: bool = False) -> None:
        self.requests: list[BuildRequest] = []
        self._fail = fail

    def build_and_push(self, request: BuildRequest) -> None:
        if self._fail:
            raise BuildkitError("fake builder configured to fail")
        self.requests.append(request)
```

- [ ] **Step 5 : Lancer le test**

```bash
uv run pytest tests/unit/test_fakes_image_builder.py -v
```

Expected : 2 passed.

- [ ] **Step 6 : Commit**

```bash
git add houba/ports/image_builder.py tests/fakes/image_builder.py \
        tests/unit/test_fakes_image_builder.py
git commit -m "feat(ports): ajoute ImageBuilderPort + FakeImageBuilder"
```

---

### Task 6 : Adapter `buildkit_cli.py` + fake-bin `buildctl`

**Files:**
- Create: `houba/adapters/buildkit_cli.py`
- Create: `tests/fake-bins/buildctl`
- Create: `tests/integration/test_buildkit_cli.py`

- [ ] **Step 1 : Écrire le fake-bin**

`tests/fake-bins/buildctl` :

```sh
#!/usr/bin/env sh
# Fake buildctl pour tests d'intégration.
# Scénario via FAKE_BUILDCTL_SCENARIO. Trace les arguments dans FAKE_BUILDCTL_LOG.

set -e

if [ -n "${FAKE_BUILDCTL_LOG:-}" ]; then
    echo "$@" >> "$FAKE_BUILDCTL_LOG"
fi

case "${FAKE_BUILDCTL_SCENARIO:-success}" in
    success)
        echo "#1 [internal] load build definition"
        echo "#1 transferring dockerfile: 100B done"
        echo "#1 DONE 0.0s"
        ;;
    fail)
        echo "buildctl: simulated failure" >&2
        exit 1
        ;;
    *)
        echo "fake-buildctl: unknown scenario ${FAKE_BUILDCTL_SCENARIO}" >&2
        exit 99
        ;;
esac
```

Rendre exécutable :

```bash
chmod +x tests/fake-bins/buildctl
```

- [ ] **Step 2 : Écrire les tests intégration**

`tests/integration/test_buildkit_cli.py` :

```python
from __future__ import annotations

from pathlib import Path

import pytest

from houba.adapters.buildkit_cli import BuildkitAdapter
from houba.errors import BuildkitError
from houba.ports.image_builder import BuildRequest


def _request(tmp_path: Path) -> BuildRequest:
    df = tmp_path / "Dockerfile"
    df.write_text("FROM scratch\n")
    return BuildRequest(
        dockerfile_path=df,
        context_dir=tmp_path,
        image_ref="harbor.example.com/lib/busybox:1.36",
        build_args={"VERSION": "1.36"},
    )


def test_build_and_push_success(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "buildctl.log"
    monkeypatch.setenv("FAKE_BUILDCTL_LOG", str(log))
    monkeypatch.setenv("FAKE_BUILDCTL_SCENARIO", "success")
    BuildkitAdapter().build_and_push(_request(tmp_path))
    args = log.read_text().strip()
    assert "build" in args
    assert "harbor.example.com/lib/busybox:1.36" in args
    assert "VERSION=1.36" in args


def test_build_and_push_failure_raises_buildkit_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_BUILDCTL_SCENARIO", "fail")
    with pytest.raises(BuildkitError):
        BuildkitAdapter().build_and_push(_request(tmp_path))


def test_explicit_missing_binary_raises_buildkit_error() -> None:
    with pytest.raises(BuildkitError, match="not found"):
        BuildkitAdapter(binary="/nonexistent/buildctl")
```

- [ ] **Step 3 : Vérifier que le test échoue**

```bash
uv run pytest tests/integration/test_buildkit_cli.py -v
```

Expected : `ImportError`.

- [ ] **Step 4 : Écrire l'adapter**

`houba/adapters/buildkit_cli.py` :

```python
"""Wrapper subprocess autour de buildctl (BuildKit) pour build + push d'images OCI."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from houba.errors import BuildkitError
from houba.ports.image_builder import BuildRequest


class BuildkitAdapter:
    def __init__(self, binary: str | None = None) -> None:
        if binary is not None:
            if not Path(binary).is_file():
                raise BuildkitError(f"buildctl binary not found: {binary}")
            self._bin = binary
            return
        resolved = shutil.which("buildctl")
        if not resolved:
            raise BuildkitError("buildctl binary not found in PATH")
        self._bin = resolved

    def build_and_push(self, request: BuildRequest) -> None:
        args = [
            "build",
            "--frontend=dockerfile.v0",
            f"--local=context={request.context_dir}",
            f"--local=dockerfile={request.dockerfile_path.parent}",
            f"--opt=filename={request.dockerfile_path.name}",
            f"--output=type=image,name={request.image_ref},push=true",
        ]
        for k, v in sorted(request.build_args.items()):
            args.append(f"--opt=build-arg:{k}={v}")
        try:
            r = subprocess.run(  # noqa: S603
                [self._bin, *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=1800,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise BuildkitError(str(e)) from e
        if r.returncode != 0:
            raise BuildkitError(f"buildctl {' '.join(args)} failed: {r.stderr.strip()}")
```

- [ ] **Step 5 : Relancer**

```bash
uv run pytest tests/integration/test_buildkit_cli.py -v
uv run mypy houba
```

Expected : 3 passed.

- [ ] **Step 6 : Commit**

```bash
git add houba/adapters/buildkit_cli.py tests/fake-bins/buildctl \
        tests/integration/test_buildkit_cli.py
git commit -m "feat(adapters): BuildkitAdapter wrap buildctl avec fake-bin de test"
```

---

## Groupe 3 — Git

Wrapper subprocess autour de `git` (clone, add, commit, push, tag, checkout, current_revision).

### Task 7 : Port `git_repo.py`

**Files:**
- Create: `houba/ports/git_repo.py`
- Create: `tests/fakes/git_repo.py`
- Create: `tests/unit/test_fakes_git_repo.py`

- [ ] **Step 1 : Écrire le test du fake**

`tests/unit/test_fakes_git_repo.py` :

```python
from __future__ import annotations

from pathlib import Path

import pytest

from houba.errors import GitError
from houba.ports.git_repo import GitCommit, GitRef
from tests.fakes.git_repo import FakeGitRepoPort


def test_clone_journaled() -> None:
    fake = FakeGitRepoPort()
    fake.clone("https://gitlab.example.com/g/r.git", Path("/tmp/r"), branch="master")
    assert fake.clones == [("https://gitlab.example.com/g/r.git", Path("/tmp/r"), "master")]


def test_commit_records_message() -> None:
    fake = FakeGitRepoPort()
    fake.add(Path("/tmp/r"), ["a.txt", "b.txt"])
    fake.commit(Path("/tmp/r"), "feat: add files")
    assert fake.commits == [GitCommit(repo=Path("/tmp/r"), message="feat: add files")]


def test_push_and_tag_journaled() -> None:
    fake = FakeGitRepoPort()
    fake.push(Path("/tmp/r"), remote="origin", ref="master")
    fake.tag(Path("/tmp/r"), name="v1.0", message="release")
    assert fake.pushes == [(Path("/tmp/r"), "origin", "master")]
    assert fake.tags == [GitRef(repo=Path("/tmp/r"), name="v1.0", message="release")]


def test_current_revision_returns_seeded() -> None:
    fake = FakeGitRepoPort(revisions={Path("/tmp/r"): "abc123"})
    assert fake.current_revision(Path("/tmp/r")) == "abc123"


def test_current_revision_unknown_raises() -> None:
    fake = FakeGitRepoPort()
    with pytest.raises(GitError):
        fake.current_revision(Path("/tmp/r"))
```

- [ ] **Step 2 : Vérifier l'échec**

```bash
uv run pytest tests/unit/test_fakes_git_repo.py -v
```

Expected : `ImportError`.

- [ ] **Step 3 : Écrire le port**

`houba/ports/git_repo.py` :

```python
"""Port d'accès à un dépôt git local (clone, commit, push, tag)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class GitCommit:
    repo: Path
    message: str


@dataclass(frozen=True)
class GitRef:
    repo: Path
    name: str
    message: str | None = None


class GitRepoPort(Protocol):
    def clone(self, url: str, destination: Path, *, branch: str | None = None) -> None: ...
    def checkout(self, repo: Path, ref: str) -> None: ...
    def add(self, repo: Path, paths: list[str]) -> None: ...
    def commit(self, repo: Path, message: str) -> None: ...
    def push(self, repo: Path, *, remote: str, ref: str) -> None: ...
    def tag(self, repo: Path, *, name: str, message: str | None = None) -> None: ...
    def current_revision(self, repo: Path) -> str: ...
```

- [ ] **Step 4 : Écrire le fake**

`tests/fakes/git_repo.py` :

```python
from __future__ import annotations

from pathlib import Path

from houba.errors import GitError
from houba.ports.git_repo import GitCommit, GitRef


class FakeGitRepoPort:
    def __init__(self, *, revisions: dict[Path, str] | None = None) -> None:
        self._revisions = revisions or {}
        self.clones: list[tuple[str, Path, str | None]] = []
        self.checkouts: list[tuple[Path, str]] = []
        self.adds: list[tuple[Path, list[str]]] = []
        self.commits: list[GitCommit] = []
        self.pushes: list[tuple[Path, str, str]] = []
        self.tags: list[GitRef] = []

    def clone(self, url: str, destination: Path, *, branch: str | None = None) -> None:
        self.clones.append((url, destination, branch))

    def checkout(self, repo: Path, ref: str) -> None:
        self.checkouts.append((repo, ref))

    def add(self, repo: Path, paths: list[str]) -> None:
        self.adds.append((repo, list(paths)))

    def commit(self, repo: Path, message: str) -> None:
        self.commits.append(GitCommit(repo=repo, message=message))

    def push(self, repo: Path, *, remote: str, ref: str) -> None:
        self.pushes.append((repo, remote, ref))

    def tag(self, repo: Path, *, name: str, message: str | None = None) -> None:
        self.tags.append(GitRef(repo=repo, name=name, message=message))

    def current_revision(self, repo: Path) -> str:
        try:
            return self._revisions[repo]
        except KeyError as e:
            raise GitError(f"no revision known for {repo}") from e
```

- [ ] **Step 5 : Relancer**

```bash
uv run pytest tests/unit/test_fakes_git_repo.py -v
```

Expected : 5 passed.

- [ ] **Step 6 : Commit**

```bash
git add houba/ports/git_repo.py tests/fakes/git_repo.py \
        tests/unit/test_fakes_git_repo.py
git commit -m "feat(ports): ajoute GitRepoPort + FakeGitRepoPort"
```

---

### Task 8 : Adapter `git_cli.py` + fake-bin `git`

**Files:**
- Create: `houba/adapters/git_cli.py`
- Create: `tests/fake-bins/git`
- Create: `tests/integration/test_git_cli.py`

- [ ] **Step 1 : Écrire le fake-bin**

`tests/fake-bins/git` :

```sh
#!/usr/bin/env sh
# Fake git pour tests d'intégration.
# Trace les arguments dans FAKE_GIT_LOG ; renvoie des sorties prédéfinies selon les
# sous-commandes attendues. Comportement par défaut : success (exit 0).

set -e

if [ -n "${FAKE_GIT_LOG:-}" ]; then
    echo "$@" >> "$FAKE_GIT_LOG"
fi

case "$1" in
    rev-parse)
        # rev-parse HEAD → renvoie la révision factice
        echo "${FAKE_GIT_REVISION:-abc123def456}"
        ;;
    clone|checkout|add|commit|push|tag)
        if [ "${FAKE_GIT_SCENARIO:-success}" = "fail" ]; then
            echo "git $1: simulated failure" >&2
            exit 1
        fi
        ;;
    *)
        # Autres sous-commandes : silencieux, exit 0
        :
        ;;
esac
```

```bash
chmod +x tests/fake-bins/git
```

- [ ] **Step 2 : Écrire les tests intégration**

`tests/integration/test_git_cli.py` :

```python
from __future__ import annotations

from pathlib import Path

import pytest

from houba.adapters.git_cli import GitCliAdapter
from houba.errors import GitError


def _log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    log = tmp_path / "git.log"
    monkeypatch.setenv("FAKE_GIT_LOG", str(log))
    return log


def test_clone_calls_git(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(monkeypatch, tmp_path)
    GitCliAdapter().clone(
        "https://gitlab.example.com/g/r.git", tmp_path / "r", branch="master"
    )
    out = log.read_text()
    assert "clone" in out
    assert "--branch master" in out or "-b master" in out


def test_commit_calls_git_commit(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(monkeypatch, tmp_path)
    GitCliAdapter().commit(tmp_path, "feat: add x")
    assert "commit -m feat: add x" in log.read_text()


def test_push_calls_git_push(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(monkeypatch, tmp_path)
    GitCliAdapter().push(tmp_path, remote="origin", ref="master")
    assert "push origin master" in log.read_text()


def test_tag_calls_git_tag(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = _log(monkeypatch, tmp_path)
    GitCliAdapter().tag(tmp_path, name="v1.0", message="release")
    assert "tag -a v1.0" in log.read_text()


def test_current_revision_returns_rev_parse_output(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_GIT_REVISION", "deadbeef")
    assert GitCliAdapter().current_revision(tmp_path) == "deadbeef"


def test_failure_raises_git_error(
    fake_bin_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_GIT_SCENARIO", "fail")
    with pytest.raises(GitError):
        GitCliAdapter().push(tmp_path, remote="origin", ref="master")


def test_missing_binary_raises_git_error() -> None:
    with pytest.raises(GitError, match="not found"):
        GitCliAdapter(binary="/nonexistent/git")
```

- [ ] **Step 3 : Vérifier l'échec**

```bash
uv run pytest tests/integration/test_git_cli.py -v
```

Expected : `ImportError`.

- [ ] **Step 4 : Écrire l'adapter**

`houba/adapters/git_cli.py` :

```python
"""Wrapper subprocess autour de git (clone, commit, push, tag, rev-parse)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from houba.errors import GitError


class GitCliAdapter:
    def __init__(self, binary: str | None = None) -> None:
        if binary is not None:
            if not Path(binary).is_file():
                raise GitError(f"git binary not found: {binary}")
            self._bin = binary
            return
        resolved = shutil.which("git")
        if not resolved:
            raise GitError("git binary not found in PATH")
        self._bin = resolved

    def clone(self, url: str, destination: Path, *, branch: str | None = None) -> None:
        args = ["clone"]
        if branch is not None:
            args += ["--branch", branch]
        args += [url, str(destination)]
        self._run(args, cwd=None)

    def checkout(self, repo: Path, ref: str) -> None:
        self._run(["checkout", ref], cwd=repo)

    def add(self, repo: Path, paths: list[str]) -> None:
        self._run(["add", *paths], cwd=repo)

    def commit(self, repo: Path, message: str) -> None:
        self._run(["commit", "-m", message], cwd=repo)

    def push(self, repo: Path, *, remote: str, ref: str) -> None:
        self._run(["push", remote, ref], cwd=repo)

    def tag(self, repo: Path, *, name: str, message: str | None = None) -> None:
        args = ["tag", "-a", name]
        if message is not None:
            args += ["-m", message]
        else:
            args += ["-m", name]
        self._run(args, cwd=repo)

    def current_revision(self, repo: Path) -> str:
        return self._run(["rev-parse", "HEAD"], cwd=repo).strip()

    def _run(self, args: list[str], *, cwd: Path | None) -> str:
        try:
            r = subprocess.run(  # noqa: S603
                [self._bin, *args],
                cwd=str(cwd) if cwd else None,
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise GitError(str(e)) from e
        if r.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout
```

- [ ] **Step 5 : Relancer**

```bash
uv run pytest tests/integration/test_git_cli.py -v
uv run mypy houba
```

Expected : 7 passed.

- [ ] **Step 6 : Commit**

```bash
git add houba/adapters/git_cli.py tests/fake-bins/git \
        tests/integration/test_git_cli.py
git commit -m "feat(adapters): GitCliAdapter wrap git CLI avec fake-bin de test"
```

---

## Groupe 4 — GitLab

Client HTTP pour l'API REST GitLab. Minimal pour Phase B : `find_project_by_path`, `create_merge_request`, `get_project_variable`.

### Task 9 : Port `gitlab.py`

**Files:**
- Create: `houba/ports/gitlab.py`
- Create: `tests/fakes/gitlab.py`
- Create: `tests/unit/test_fakes_gitlab.py`

- [ ] **Step 1 : Écrire le test du fake**

`tests/unit/test_fakes_gitlab.py` :

```python
from __future__ import annotations

import pytest

from houba.errors import GitLabError
from houba.ports.gitlab import GitLabProject, MergeRequest
from tests.fakes.gitlab import FakeGitLabPort


def test_find_project_returns_seeded() -> None:
    proj = GitLabProject(id=42, path="group/repo", default_branch="master")
    fake = FakeGitLabPort(projects=[proj])
    assert fake.find_project_by_path("group/repo") == proj


def test_find_project_missing_raises() -> None:
    fake = FakeGitLabPort()
    with pytest.raises(GitLabError):
        fake.find_project_by_path("group/repo")


def test_create_merge_request_returns_journal() -> None:
    fake = FakeGitLabPort(next_mr_iid=12)
    mr = fake.create_merge_request(
        project_id=42,
        source_branch="feat/x",
        target_branch="master",
        title="feat: x",
        description="body",
    )
    assert mr == MergeRequest(iid=12, project_id=42)
    assert fake.created_mrs == [(42, "feat/x", "master", "feat: x", "body")]


def test_get_project_variable_returns_seeded() -> None:
    fake = FakeGitLabPort(variables={(42, "HOUBA_KEY"): "value"})
    assert fake.get_project_variable(42, "HOUBA_KEY") == "value"


def test_get_project_variable_unknown_raises() -> None:
    fake = FakeGitLabPort()
    with pytest.raises(GitLabError):
        fake.get_project_variable(42, "MISSING")
```

- [ ] **Step 2 : Vérifier l'échec**

```bash
uv run pytest tests/unit/test_fakes_gitlab.py -v
```

Expected : `ImportError`.

- [ ] **Step 3 : Écrire le port**

`houba/ports/gitlab.py` :

```python
"""Port d'accès à l'API REST GitLab (minimal Phase B)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GitLabProject:
    id: int
    path: str
    default_branch: str = "master"


@dataclass(frozen=True)
class MergeRequest:
    iid: int
    project_id: int


class GitLabPort(Protocol):
    def find_project_by_path(self, path: str) -> GitLabProject: ...
    def create_merge_request(
        self,
        *,
        project_id: int,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> MergeRequest: ...
    def get_project_variable(self, project_id: int, key: str) -> str: ...
```

- [ ] **Step 4 : Écrire le fake**

`tests/fakes/gitlab.py` :

```python
from __future__ import annotations

from houba.errors import GitLabError
from houba.ports.gitlab import GitLabProject, MergeRequest


class FakeGitLabPort:
    def __init__(
        self,
        *,
        projects: list[GitLabProject] | None = None,
        variables: dict[tuple[int, str], str] | None = None,
        next_mr_iid: int = 1,
    ) -> None:
        self._projects = {p.path: p for p in (projects or [])}
        self._variables = variables or {}
        self._next_iid = next_mr_iid
        self.created_mrs: list[tuple[int, str, str, str, str]] = []

    def find_project_by_path(self, path: str) -> GitLabProject:
        try:
            return self._projects[path]
        except KeyError as e:
            raise GitLabError(f"project not found: {path}") from e

    def create_merge_request(
        self,
        *,
        project_id: int,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> MergeRequest:
        self.created_mrs.append((project_id, source_branch, target_branch, title, description))
        mr = MergeRequest(iid=self._next_iid, project_id=project_id)
        self._next_iid += 1
        return mr

    def get_project_variable(self, project_id: int, key: str) -> str:
        try:
            return self._variables[(project_id, key)]
        except KeyError as e:
            raise GitLabError(f"variable not found: project={project_id} key={key}") from e
```

- [ ] **Step 5 : Relancer**

```bash
uv run pytest tests/unit/test_fakes_gitlab.py -v
```

Expected : 5 passed.

- [ ] **Step 6 : Commit**

```bash
git add houba/ports/gitlab.py tests/fakes/gitlab.py tests/unit/test_fakes_gitlab.py
git commit -m "feat(ports): ajoute GitLabPort + FakeGitLabPort"
```

---

### Task 10 : Adapter `gitlab_http.py`

**Files:**
- Create: `houba/adapters/gitlab_http.py`
- Create: `tests/integration/test_gitlab_http.py`

- [ ] **Step 1 : Écrire les tests intégration**

`tests/integration/test_gitlab_http.py` :

```python
from __future__ import annotations

import pytest
import respx
import httpx

from houba.adapters.gitlab_http import GitLabHttpAdapter
from houba.errors import GitLabError
from houba.ports.gitlab import GitLabProject


@pytest.fixture()
def adapter() -> GitLabHttpAdapter:
    return GitLabHttpAdapter(base_url="https://gitlab.example.com", token="glpat-xxx")


def test_find_project_by_path_returns_project(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        router.get(
            "/api/v4/projects/group%2Frepo"
        ).respond(200, json={"id": 42, "path_with_namespace": "group/repo", "default_branch": "main"})
        proj = adapter.find_project_by_path("group/repo")
        assert proj == GitLabProject(id=42, path="group/repo", default_branch="main")


def test_find_project_404_raises_gitlab_error(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        router.get("/api/v4/projects/group%2Fmissing").respond(404)
        with pytest.raises(GitLabError):
            adapter.find_project_by_path("group/missing")


def test_create_merge_request(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        route = router.post(
            "/api/v4/projects/42/merge_requests",
            json={
                "source_branch": "feat/x",
                "target_branch": "master",
                "title": "feat: x",
                "description": "body",
            },
        ).respond(201, json={"iid": 7, "project_id": 42})
        mr = adapter.create_merge_request(
            project_id=42,
            source_branch="feat/x",
            target_branch="master",
            title="feat: x",
            description="body",
        )
        assert route.called
        assert mr.iid == 7


def test_get_project_variable(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        router.get("/api/v4/projects/42/variables/HOUBA_KEY").respond(
            200, json={"key": "HOUBA_KEY", "value": "v", "variable_type": "env_var"}
        )
        assert adapter.get_project_variable(42, "HOUBA_KEY") == "v"


def test_get_project_variable_404_raises_gitlab_error(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        router.get("/api/v4/projects/42/variables/MISSING").respond(404)
        with pytest.raises(GitLabError):
            adapter.get_project_variable(42, "MISSING")


def test_transient_5xx_retried(adapter: GitLabHttpAdapter) -> None:
    with respx.mock(base_url="https://gitlab.example.com") as router:
        responses = [
            httpx.Response(503),
            httpx.Response(200, json={"id": 1, "path_with_namespace": "g/r", "default_branch": "master"}),
        ]
        route = router.get("/api/v4/projects/g%2Fr").mock(side_effect=responses)
        adapter.find_project_by_path("g/r")
        assert route.call_count == 2
```

- [ ] **Step 2 : Vérifier l'échec**

```bash
uv run pytest tests/integration/test_gitlab_http.py -v
```

Expected : `ImportError`.

- [ ] **Step 3 : Écrire l'adapter**

`houba/adapters/gitlab_http.py` :

```python
"""Adapter HTTP pour l'API REST GitLab."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from houba.errors import GitLabError
from houba.ports.gitlab import GitLabProject, MergeRequest

MAX_ATTEMPTS = 5


class _Transient(GitLabError):
    """Erreur transitoire interne, déclenche un retry."""


class GitLabHttpAdapter:
    def __init__(self, *, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/") + "/api/v4"
        self._client = httpx.Client(
            headers={"PRIVATE-TOKEN": token, "Accept": "application/json"},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    def find_project_by_path(self, path: str) -> GitLabProject:
        encoded = quote(path, safe="")
        data = self._request("GET", f"/projects/{encoded}")
        return GitLabProject(
            id=data["id"],
            path=data["path_with_namespace"],
            default_branch=data.get("default_branch", "master"),
        )

    def create_merge_request(
        self,
        *,
        project_id: int,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> MergeRequest:
        body = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
        }
        data = self._request("POST", f"/projects/{project_id}/merge_requests", json=body)
        return MergeRequest(iid=data["iid"], project_id=data["project_id"])

    def get_project_variable(self, project_id: int, key: str) -> str:
        data = self._request("GET", f"/projects/{project_id}/variables/{quote(key, safe='')}")
        return str(data["value"])

    @retry(
        retry=retry_if_exception_type(_Transient),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, max=2.0),
        reraise=True,
    )
    def _request(self, method: str, path: str, *, json: Any = None) -> Any:
        try:
            r = self._client.request(method, self._base + path, json=json)
        except httpx.HTTPError as e:
            raise _Transient(str(e)) from e
        if r.status_code in (401, 403):
            raise GitLabError(f"auth error: {r.status_code} {r.text}")
        if r.status_code == 404:
            raise GitLabError(f"not found: {path}")
        if 500 <= r.status_code < 600:
            raise _Transient(f"{r.status_code}: {r.text}")
        if not r.is_success:
            raise GitLabError(f"{r.status_code}: {r.text}")
        return r.json()
```

- [ ] **Step 4 : Relancer**

```bash
uv run pytest tests/integration/test_gitlab_http.py -v
uv run mypy houba
```

Expected : 6 passed.

- [ ] **Step 5 : Commit**

```bash
git add houba/adapters/gitlab_http.py tests/integration/test_gitlab_http.py
git commit -m "feat(adapters): GitLabHttpAdapter pour API REST GitLab (find/MR/variable)"
```

---

## Groupe 5 — Notifier (Teams)

### Task 11 : Port `notifier.py` + fake

**Files:**
- Create: `houba/ports/notifier.py`
- Create: `tests/fakes/notifier.py`
- Create: `tests/unit/test_fakes_notifier.py`

- [ ] **Step 1 : Écrire le test du fake**

`tests/unit/test_fakes_notifier.py` :

```python
from __future__ import annotations

import pytest

from houba.errors import AdapterError
from tests.fakes.notifier import FakeNotifierPort


def test_send_records_payload() -> None:
    fake = FakeNotifierPort()
    fake.send({"title": "ok", "items": [1, 2]})
    assert fake.payloads == [{"title": "ok", "items": [1, 2]}]


def test_send_when_failing_raises() -> None:
    fake = FakeNotifierPort(fail=True)
    with pytest.raises(AdapterError):
        fake.send({})
```

- [ ] **Step 2 : Vérifier l'échec**

```bash
uv run pytest tests/unit/test_fakes_notifier.py -v
```

Expected : `ImportError`.

- [ ] **Step 3 : Écrire le port**

`houba/ports/notifier.py` :

```python
"""Port de notification (Teams webhook en prod, no-op en dry-run)."""

from __future__ import annotations

from typing import Any, Protocol


class NotifierPort(Protocol):
    def send(self, payload: dict[str, Any]) -> None: ...
```

- [ ] **Step 4 : Écrire le fake**

`tests/fakes/notifier.py` :

```python
from __future__ import annotations

from typing import Any

from houba.errors import AdapterError


class FakeNotifierPort:
    def __init__(self, *, fail: bool = False) -> None:
        self.payloads: list[dict[str, Any]] = []
        self._fail = fail

    def send(self, payload: dict[str, Any]) -> None:
        if self._fail:
            raise AdapterError("fake notifier configured to fail")
        self.payloads.append(payload)
```

- [ ] **Step 5 : Lancer le test**

```bash
uv run pytest tests/unit/test_fakes_notifier.py -v
```

Expected : 2 passed.

- [ ] **Step 6 : Commit**

```bash
git add houba/ports/notifier.py tests/fakes/notifier.py tests/unit/test_fakes_notifier.py
git commit -m "feat(ports): ajoute NotifierPort + FakeNotifierPort"
```

---

### Task 12 : Adapter `teams_webhook.py`

**Files:**
- Create: `houba/adapters/teams_webhook.py`
- Create: `tests/integration/test_teams_webhook.py`

- [ ] **Step 1 : Écrire les tests intégration**

`tests/integration/test_teams_webhook.py` :

```python
from __future__ import annotations

import httpx
import pytest
import respx

from houba.adapters.teams_webhook import TeamsWebhookAdapter
from houba.errors import AdapterError


def test_send_posts_payload_to_webhook() -> None:
    adapter = TeamsWebhookAdapter(webhook_url="https://outlook.office.com/webhook/abc")
    with respx.mock() as router:
        route = router.post(
            "https://outlook.office.com/webhook/abc",
            json={"title": "ok"},
        ).respond(200, text="1")
        adapter.send({"title": "ok"})
        assert route.called


def test_send_4xx_raises_adapter_error() -> None:
    adapter = TeamsWebhookAdapter(webhook_url="https://outlook.office.com/webhook/abc")
    with respx.mock() as router:
        router.post("https://outlook.office.com/webhook/abc").respond(400, text="bad request")
        with pytest.raises(AdapterError):
            adapter.send({})


def test_send_5xx_retries_then_succeeds() -> None:
    adapter = TeamsWebhookAdapter(webhook_url="https://outlook.office.com/webhook/abc")
    with respx.mock() as router:
        route = router.post("https://outlook.office.com/webhook/abc").mock(
            side_effect=[httpx.Response(503), httpx.Response(200, text="1")]
        )
        adapter.send({})
        assert route.call_count == 2


def test_send_5xx_exhaust_retries_raises() -> None:
    adapter = TeamsWebhookAdapter(webhook_url="https://outlook.office.com/webhook/abc")
    with respx.mock() as router:
        router.post("https://outlook.office.com/webhook/abc").respond(503)
        with pytest.raises(AdapterError):
            adapter.send({})
```

- [ ] **Step 2 : Vérifier l'échec**

```bash
uv run pytest tests/integration/test_teams_webhook.py -v
```

Expected : `ImportError`.

- [ ] **Step 3 : Écrire l'adapter**

`houba/adapters/teams_webhook.py` :

```python
"""Notifier Teams via webhook HTTP (POST JSON)."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from houba.errors import AdapterError

MAX_ATTEMPTS = 5


class _Transient(AdapterError):
    """Erreur transitoire (5xx, network), déclenche un retry."""


class TeamsWebhookAdapter:
    def __init__(self, *, webhook_url: str) -> None:
        self._url = webhook_url
        self._client = httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))

    def send(self, payload: dict[str, Any]) -> None:
        self._post(payload)

    @retry(
        retry=retry_if_exception_type(_Transient),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, max=2.0),
        reraise=True,
    )
    def _post(self, payload: dict[str, Any]) -> None:
        try:
            r = self._client.post(self._url, json=payload)
        except httpx.HTTPError as e:
            raise _Transient(str(e)) from e
        if 500 <= r.status_code < 600:
            raise _Transient(f"teams webhook {r.status_code}: {r.text}")
        if not r.is_success:
            raise AdapterError(f"teams webhook {r.status_code}: {r.text}")
```

- [ ] **Step 4 : Relancer**

```bash
uv run pytest tests/integration/test_teams_webhook.py -v
uv run mypy houba
```

Expected : 4 passed.

- [ ] **Step 5 : Commit**

```bash
git add houba/adapters/teams_webhook.py tests/integration/test_teams_webhook.py
git commit -m "feat(adapters): TeamsWebhookAdapter (POST JSON avec retry transient)"
```

---

## Groupe 6 — EOL source

### Task 13 : Port `eol_source.py` + fake

**Files:**
- Create: `houba/ports/eol_source.py`
- Create: `tests/fakes/eol_source.py`
- Create: `tests/unit/test_fakes_eol_source.py`

- [ ] **Step 1 : Écrire le test du fake**

`tests/unit/test_fakes_eol_source.py` :

```python
from __future__ import annotations

import pytest

from houba.errors import EolSourceError
from houba.ports.eol_source import EolEntry
from tests.fakes.eol_source import FakeEolSourcePort


def test_fetch_returns_seeded() -> None:
    entries = [
        EolEntry(cycle="1.36", eol="2027-06-01", latest="1.36.1"),
        EolEntry(cycle="1.37", eol="2028-06-01", latest="1.37.0"),
    ]
    fake = FakeEolSourcePort(entries={"busybox": entries})
    assert fake.fetch_eol("busybox") == entries


def test_fetch_unknown_raises() -> None:
    fake = FakeEolSourcePort()
    with pytest.raises(EolSourceError):
        fake.fetch_eol("missing")
```

- [ ] **Step 2 : Vérifier l'échec**

```bash
uv run pytest tests/unit/test_fakes_eol_source.py -v
```

Expected : `ImportError`.

- [ ] **Step 3 : Écrire le port**

`houba/ports/eol_source.py` :

```python
"""Port d'accès à endoflife.date (lecture seulement)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EolEntry:
    """Une entrée de cycle EOL pour un produit.

    `eol` peut être une date ISO (`"2027-06-01"`) ou une string booléenne renvoyée
    par endoflife.date (`"false"`, `"true"`). On garde la valeur brute ; le
    parsing est dans `domain/eol.py`.
    """

    cycle: str
    eol: str
    latest: str = ""
    lts: bool = False


class EolSourcePort(Protocol):
    def fetch_eol(self, product: str) -> list[EolEntry]: ...
```

- [ ] **Step 4 : Écrire le fake**

`tests/fakes/eol_source.py` :

```python
from __future__ import annotations

from houba.errors import EolSourceError
from houba.ports.eol_source import EolEntry


class FakeEolSourcePort:
    def __init__(self, *, entries: dict[str, list[EolEntry]] | None = None) -> None:
        self._entries = entries or {}

    def fetch_eol(self, product: str) -> list[EolEntry]:
        try:
            return list(self._entries[product])
        except KeyError as e:
            raise EolSourceError(f"unknown product: {product}") from e
```

- [ ] **Step 5 : Lancer le test**

```bash
uv run pytest tests/unit/test_fakes_eol_source.py -v
```

Expected : 2 passed.

- [ ] **Step 6 : Commit**

```bash
git add houba/ports/eol_source.py tests/fakes/eol_source.py \
        tests/unit/test_fakes_eol_source.py
git commit -m "feat(ports): ajoute EolSourcePort + FakeEolSourcePort"
```

---

### Task 14 : Adapter `endoflife_http.py`

**Files:**
- Create: `houba/adapters/endoflife_http.py`
- Create: `tests/integration/test_endoflife_http.py`

- [ ] **Step 1 : Écrire les tests**

`tests/integration/test_endoflife_http.py` :

```python
from __future__ import annotations

import httpx
import pytest
import respx

from houba.adapters.endoflife_http import EndoflifeHttpAdapter
from houba.errors import EolSourceError
from houba.ports.eol_source import EolEntry


@pytest.fixture()
def adapter() -> EndoflifeHttpAdapter:
    return EndoflifeHttpAdapter(base_url="https://endoflife.date/api")


def test_fetch_eol_busybox(adapter: EndoflifeHttpAdapter) -> None:
    with respx.mock() as router:
        router.get("https://endoflife.date/api/busybox.json").respond(
            200,
            json=[
                {"cycle": "1.36", "eol": "2027-06-01", "latest": "1.36.1", "lts": False},
                {"cycle": "1.37", "eol": False, "latest": "1.37.0"},
            ],
        )
        entries = adapter.fetch_eol("busybox")
        assert entries == [
            EolEntry(cycle="1.36", eol="2027-06-01", latest="1.36.1", lts=False),
            EolEntry(cycle="1.37", eol="false", latest="1.37.0", lts=False),
        ]


def test_fetch_eol_404_raises_eol_source_error(adapter: EndoflifeHttpAdapter) -> None:
    with respx.mock() as router:
        router.get("https://endoflife.date/api/missing.json").respond(404)
        with pytest.raises(EolSourceError):
            adapter.fetch_eol("missing")


def test_fetch_eol_5xx_retried_then_succeeds(adapter: EndoflifeHttpAdapter) -> None:
    with respx.mock() as router:
        route = router.get("https://endoflife.date/api/busybox.json").mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json=[])]
        )
        adapter.fetch_eol("busybox")
        assert route.call_count == 2


def test_fetch_eol_5xx_exhaust_raises(adapter: EndoflifeHttpAdapter) -> None:
    with respx.mock() as router:
        router.get("https://endoflife.date/api/busybox.json").respond(503)
        with pytest.raises(EolSourceError):
            adapter.fetch_eol("busybox")
```

- [ ] **Step 2 : Vérifier l'échec**

```bash
uv run pytest tests/integration/test_endoflife_http.py -v
```

Expected : `ImportError`.

- [ ] **Step 3 : Écrire l'adapter**

`houba/adapters/endoflife_http.py` :

```python
"""Adapter HTTP pour endoflife.date."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from houba.errors import EolSourceError
from houba.ports.eol_source import EolEntry

MAX_ATTEMPTS = 5


class _Transient(EolSourceError):
    """Erreur transitoire interne, déclenche un retry."""


class EndoflifeHttpAdapter:
    def __init__(self, *, base_url: str = "https://endoflife.date/api") -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))

    def fetch_eol(self, product: str) -> list[EolEntry]:
        data = self._get(f"/{product}.json")
        if not isinstance(data, list):
            raise EolSourceError(f"unexpected payload from endoflife.date: {type(data).__name__}")
        return [_to_entry(item) for item in data]

    @retry(
        retry=retry_if_exception_type(_Transient),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, max=2.0),
        reraise=True,
    )
    def _get(self, path: str) -> Any:
        try:
            r = self._client.get(self._base + path)
        except httpx.HTTPError as e:
            raise _Transient(str(e)) from e
        if r.status_code == 404:
            raise EolSourceError(f"{path}: 404")
        if 500 <= r.status_code < 600:
            raise _Transient(f"{r.status_code}: {r.text}")
        if not r.is_success:
            raise EolSourceError(f"{r.status_code}: {r.text}")
        return r.json()


def _to_entry(item: dict[str, Any]) -> EolEntry:
    raw_eol = item.get("eol", "")
    # endoflife.date renvoie soit une date ISO, soit bool ; on stocke en str brut.
    eol_str = str(raw_eol).lower() if isinstance(raw_eol, bool) else str(raw_eol)
    return EolEntry(
        cycle=str(item.get("cycle", "")),
        eol=eol_str,
        latest=str(item.get("latest", "")),
        lts=bool(item.get("lts", False)),
    )
```

- [ ] **Step 4 : Relancer**

```bash
uv run pytest tests/integration/test_endoflife_http.py -v
uv run mypy houba
```

Expected : 4 passed.

- [ ] **Step 5 : Commit**

```bash
git add houba/adapters/endoflife_http.py tests/integration/test_endoflife_http.py
git commit -m "feat(adapters): EndoflifeHttpAdapter (parse JSON, retry transient)"
```

---

## Groupe 7 — Composition root, Dockerfile, CI

### Task 15 : Étendre `_di.py` (composition root)

**Files:**
- Modify: `houba/cli/_di.py`

- [ ] **Step 1 : Remplacer le contenu de `houba/cli/_di.py`**

```python
"""Composition root. Construit les adapters concrets à partir des Settings.

Volontairement non couvert par les tests unitaires (cf. coverage omit).
"""

from __future__ import annotations

from dataclasses import dataclass

from houba.adapters.buildkit_cli import BuildkitAdapter
from houba.adapters.endoflife_http import EndoflifeHttpAdapter
from houba.adapters.git_cli import GitCliAdapter
from houba.adapters.gitlab_http import GitLabHttpAdapter
from houba.adapters.harbor_http import HarborHttpAdapter
from houba.adapters.skopeo_cli import SkopeoAdapter
from houba.adapters.system_clock import SystemClock
from houba.adapters.teams_webhook import TeamsWebhookAdapter
from houba.config import Settings


@dataclass(frozen=True)
class Container:
    settings: Settings
    harbor: HarborHttpAdapter
    skopeo: SkopeoAdapter
    builder: BuildkitAdapter
    git: GitCliAdapter
    gitlab: GitLabHttpAdapter
    notifier: TeamsWebhookAdapter | None
    eol: EndoflifeHttpAdapter
    clock: SystemClock


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    harbor = HarborHttpAdapter(
        base_url=settings.harbor.url,
        user=settings.harbor.user,
        password=settings.harbor.password.get_secret_value(),
    )
    gitlab = GitLabHttpAdapter(
        base_url=settings.gitlab.url,
        token=settings.gitlab.token.get_secret_value(),
    )
    notifier = None
    if settings.teams_webhook_url is not None:
        notifier = TeamsWebhookAdapter(
            webhook_url=settings.teams_webhook_url.get_secret_value()
        )
    return Container(
        settings=settings,
        harbor=harbor,
        skopeo=SkopeoAdapter(),
        builder=BuildkitAdapter(),
        git=GitCliAdapter(),
        gitlab=gitlab,
        notifier=notifier,
        eol=EndoflifeHttpAdapter(base_url=settings.endoflife_url),
        clock=SystemClock(),
    )
```

- [ ] **Step 2 : Vérifier mypy + tests**

```bash
uv run mypy houba
uv run pytest -v
```

Expected : tout vert. Note : `_di.py` n'est pas couvert (cf. `pyproject.toml` coverage omit).

- [ ] **Step 3 : Commit**

```bash
git add houba/cli/_di.py
git commit -m "feat(cli): étend le composition root avec les 5 nouveaux adapters Phase B"
```

---

### Task 16 : Dockerfile runtime complet (skopeo + buildctl + git)

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1 : Remplacer le Dockerfile**

```dockerfile
# Phase B — image runtime complète : Python CLI + skopeo + buildctl + git.

FROM python:3.12-slim AS build

WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY houba ./houba

RUN pip install --no-cache-dir uv && uv build

FROM python:3.12-slim AS runtime

# skopeo et buildctl viennent d'images upstream officielles (build reproductible).
COPY --from=quay.io/skopeo/stable:v1.13 /usr/bin/skopeo /usr/bin/skopeo
COPY --from=moby/buildkit:v0.13-rootless /usr/bin/buildctl /usr/bin/buildctl

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

ENTRYPOINT ["houba"]
CMD ["--help"]
```

- [ ] **Step 2 : Build local**

```bash
docker build -t houba:phaseB .
```

Expected : build réussi (≈ 5 min à cause des deux `COPY --from` d'images externes).

- [ ] **Step 3 : Smoke tests sur l'image**

```bash
docker run --rm houba:phaseB version
docker run --rm --entrypoint skopeo houba:phaseB --version
docker run --rm --entrypoint buildctl houba:phaseB --version
docker run --rm --entrypoint git houba:phaseB --version
```

Expected :
- `houba version` → `0.1.0.dev0`
- `skopeo --version` → `skopeo version 1.13.x`
- `buildctl --version` → `buildctl github.com/moby/buildkit v0.13.x`
- `git --version` → `git version 2.x`

- [ ] **Step 4 : Commit**

```bash
git add Dockerfile
git commit -m "feat(image): runtime complète avec skopeo + buildctl + git (Phase B)"
```

---

### Task 17 : CI — job `python:publish:image` taggué `v0-rc`

**Files:**
- Modify: `.gitlab-ci.yml`

- [ ] **Step 1 : Lire l'existant**

```bash
sed -n '1,80p' .gitlab-ci.yml
```

- [ ] **Step 2 : Remplacer entièrement par**

```yaml
# CI/CD du repo houba — CLI Python de la pipeline Hub2Hub.
# Pour le projet métier Hub2Hub (Jenkins Shared Library Groovy), voir le repo shared-libs.

stages:
  - test
  - build
  - publish

.python_base:
  image: python:3.12-slim
  before_script:
    - pip install --no-cache-dir uv
    - apt-get update && apt-get install -y --no-install-recommends git ca-certificates
    - uv sync

python:lint:
  extends: .python_base
  stage: test
  script:
    - uv run ruff check .
    - uv run ruff format --check .
    - uv run mypy houba
  rules:
    - changes:
        - pyproject.toml
        - uv.lock
        - houba/**/*
        - tests/**/*
        - .gitlab-ci.yml

python:test:
  extends: .python_base
  stage: test
  script:
    - uv run pytest tests/ -v --cov=houba --cov-report=term-missing --cov-fail-under=80
    - uv run pytest tests/unit/domain -v --cov=houba.domain --cov-report=term-missing --cov-fail-under=90
  artifacts:
    when: always
    paths:
      - .coverage
    expire_in: 1 week
  rules:
    - changes:
        - pyproject.toml
        - uv.lock
        - houba/**/*
        - tests/**/*

python:build:image:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_TLS_CERTDIR: ""
  script:
    - docker build -t houba:${CI_COMMIT_SHORT_SHA} .
  rules:
    - if: $CI_COMMIT_BRANCH
      changes:
        - Dockerfile
        - pyproject.toml
        - uv.lock
        - houba/**/*

# Publication de l'image v0-rc sur la registry Harbor SNCF.
# Déclenchée sur master OU sur création de tag, après build:image.
python:publish:image:
  stage: publish
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_TLS_CERTDIR: ""
    # HARBOR_REGISTRY, HARBOR_PROJECT, HARBOR_USER, HARBOR_PASSWORD : variables CI/CD GitLab,
    # provisionnées au repo houba avec un robot account write sur le projet Harbor cible.
    IMAGE_NAME: ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/houba
  before_script:
    - echo "$HARBOR_PASSWORD" | docker login "$HARBOR_REGISTRY" -u "$HARBOR_USER" --password-stdin
  script:
    - docker build -t "${IMAGE_NAME}:${CI_COMMIT_SHORT_SHA}" -t "${IMAGE_NAME}:v0-rc" .
    - docker push "${IMAGE_NAME}:${CI_COMMIT_SHORT_SHA}"
    - docker push "${IMAGE_NAME}:v0-rc"
    # Sur tag git semver, on push aussi le tag versionné.
    - |
      if [ -n "$CI_COMMIT_TAG" ]; then
        docker tag "${IMAGE_NAME}:${CI_COMMIT_SHORT_SHA}" "${IMAGE_NAME}:${CI_COMMIT_TAG}"
        docker push "${IMAGE_NAME}:${CI_COMMIT_TAG}"
      fi
  rules:
    - if: $CI_COMMIT_BRANCH == "master"
    - if: $CI_COMMIT_TAG =~ /^v[0-9]+\.[0-9]+\.[0-9]+/
```

- [ ] **Step 3 : Lint YAML local (sanity)**

```bash
python -c "import yaml; yaml.safe_load(open('.gitlab-ci.yml'))"
```

Expected : pas de sortie (YAML valide).

- [ ] **Step 4 : Commit**

```bash
git add .gitlab-ci.yml
git commit -m "ci: ajoute job python:publish:image (push houba:v0-rc sur Harbor)"
```

---

### Task 18 : Vérification globale Phase B + coverage gate

**Files:** Aucun nouveau fichier ; lance la suite complète.

- [ ] **Step 1 : Suite complète**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy houba
uv run pytest -v --cov=houba --cov-report=term-missing --cov-fail-under=80
```

Expected : tout passe ; coverage global ≥ 80 %.

- [ ] **Step 2 : Coverage `domain/` inchangé (régression check)**

```bash
uv run pytest tests/unit/domain -v --cov=houba.domain --cov-report=term-missing --cov-fail-under=90
```

Expected : pass, ≥ 90 % (Phase B ne touche pas à `domain/`).

- [ ] **Step 3 : Coverage `adapters/` ≥ 80 %**

```bash
uv run pytest tests/integration tests/unit -v \
    --cov=houba.adapters --cov-report=term-missing --cov-fail-under=80
```

Expected : ≥ 80 %.

- [ ] **Step 4 : Sanity grep — pureté domain inchangée**

```bash
grep -rn "import requests\|import httpx\|import subprocess" houba/domain/ \
    || echo "OK domain pur"
grep -rn "os.environ" houba/ --include='*.py' | grep -v config.py \
    || echo "OK env vars confinées à config.py"
```

Expected : 2× "OK".

- [ ] **Step 5 : Vérifier qu'aucun port n'importe un adapter**

```bash
grep -rn "from houba.adapters" houba/ports/ || echo "OK ports n'importent pas d'adapter"
```

Expected : "OK".

- [ ] **Step 6 : Build image + smoke runtime**

```bash
docker build -t houba:phaseB-final .
docker run --rm houba:phaseB-final version
docker run --rm --entrypoint sh houba:phaseB-final -c 'command -v skopeo && command -v buildctl && command -v git'
```

Expected : version affichée, 3 binaires localisés.

- [ ] **Step 7 : Tag Phase B (local, ne pas pousser sans demande)**

```bash
git tag -a v0.2.0-phase-b -m "Phase B — adapters complets + image runtime v0-rc"
git log --oneline v0.2.0-phase-b | head -1
```

Expected : tag créé sur HEAD.

---

## Critères d'acceptation de la Phase B

La phase est livrée quand **tous** les critères suivants sont satisfaits :

- [ ] `uv run ruff check .` passe.
- [ ] `uv run ruff format --check .` passe.
- [ ] `uv run mypy houba` passe (strict global, partiellement laxiste sur adapters/cli).
- [ ] `uv run pytest` passe avec coverage global ≥ 80 %.
- [ ] Coverage `houba.domain` ≥ 90 % (inchangé depuis Phase A).
- [ ] Coverage `houba.adapters` ≥ 80 %.
- [ ] `docker build -t houba:phaseB .` réussit et embarque `skopeo`, `buildctl`, `git`.
- [ ] `docker run --rm houba:phaseB version` affiche `0.1.0.dev0`.
- [ ] `docker run --rm --entrypoint skopeo houba:phaseB --version` affiche `1.13.x`.
- [ ] `docker run --rm --entrypoint buildctl houba:phaseB --version` affiche `v0.13.x`.
- [ ] `docker run --rm --entrypoint git houba:phaseB --version` affiche `2.x`.
- [ ] Aucun module dans `houba/domain/` n'importe d'I/O (httpx, requests, subprocess, pathlib.Path open).
- [ ] Aucun module dans `houba/ports/` n'importe `houba.adapters.*`.
- [ ] `os.environ` n'est lu qu'à l'intérieur de `houba/config.py`.
- [ ] Tous les nouveaux ports ont leur fake correspondant dans `tests/fakes/` et une suite de tests unitaires associée.
- [ ] Tous les nouveaux adapters ont une suite de tests d'intégration (respx pour HTTP, fake-bins pour CLI).
- [ ] Pipeline GitLab CI vert sur `feat/python-cli` (le job `python:publish:image` ne tournera qu'au merge sur `master`).
- [ ] Tag local `v0.2.0-phase-b` posé sur HEAD.

```bash
# Sanity grep final
grep -rn "import requests\|import httpx\|import subprocess" houba/domain/ || echo "OK"
grep -rn "from houba.adapters" houba/ports/ || echo "OK"
grep -rn "os.environ" houba/ --include='*.py' | grep -v config.py || echo "OK"
```
