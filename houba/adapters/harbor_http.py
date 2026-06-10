"""Adaptateur HTTP pour Harbor v2 (méthodes de lecture et d'écriture)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from houba.errors import (
    HarborAuthError,
    HarborError,
    HarborNotFoundError,
    HarborTransientError,
)
from houba.ports.harbor import Artifact, ArtifactTag, ImmutableTagRule, Label, Repository

PAGE_SIZE = 100
MAX_ATTEMPTS = 5


def _encode_repo(repository_name: str) -> str:
    """Double-encode a Harbor repository name for URL path segments.

    Harbor exige un double encodage du nom de repo : les `/` doivent rester
    encodés côté serveur après le routing. Voir vars/HarborApi.groovy et
    ci/harbor.py — bug historique reproduit ici intentionnellement.
    """
    return quote(quote(repository_name, safe=""), safe="")


class HarborHttpAdapter:
    def __init__(self, *, base_url: str, user: str, password: str) -> None:
        self._base = base_url.rstrip("/") + "/api/v2.0"
        self._client = httpx.Client(
            auth=(user, password),
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_repositories(self, project_name: str) -> list[Repository]:
        items = list(self._paginate(f"/projects/{project_name}/repositories"))
        return [
            Repository(
                name=item["name"],
                project_id=item["project_id"],
                artifact_count=item.get("artifact_count", 0),
            )
            for item in items
        ]

    def get_artifacts(self, project_name: str, repository_name: str) -> list[Artifact]:
        repo_encoded = _encode_repo(repository_name)
        path = f"/projects/{project_name}/repositories/{repo_encoded}/artifacts"
        items = list(self._paginate(path))
        return [
            Artifact(
                digest=item["digest"],
                tags=[t["name"] for t in (item.get("tags") or [])],
                push_time=item.get("push_time", ""),
                labels=[lab["name"] for lab in (item.get("labels") or [])],
            )
            for item in items
        ]

    def get_artifact(self, project_name: str, repository_name: str, reference: str) -> Artifact:
        repo_encoded = _encode_repo(repository_name)
        # safe=":" preserves the `sha256:` separator dans les digests. Les noms de tags
        # ne doivent pas contenir de `:` (convention Harbor) sous peine d'être parsés
        # comme des digests par l'API.
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
        repo_encoded = _encode_repo(repository_name)
        ref_encoded = quote(reference, safe=":")
        path = f"/projects/{project_name}/repositories/{repo_encoded}/artifacts/{ref_encoded}/tags"
        items = list(self._paginate(path))
        return [ArtifactTag(name=i["name"], immutable=i.get("immutable", False)) for i in items]

    def list_immutable_tag_rules(self, project_name: str) -> list[ImmutableTagRule]:
        path = f"/projects/{project_name}/immutabletagrules"
        items = list(self._paginate(path))
        return [_parse_immutable_rule(i) for i in items]

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def delete_repository(self, project_name: str, repository_name: str) -> None:
        repo_encoded = _encode_repo(repository_name)
        self._request("DELETE", f"/projects/{project_name}/repositories/{repo_encoded}")

    def delete_artifact(self, project_name: str, repository_name: str, reference: str) -> None:
        repo_encoded = _encode_repo(repository_name)
        ref_encoded = quote(reference, safe=":")
        path = f"/projects/{project_name}/repositories/{repo_encoded}/artifacts/{ref_encoded}"
        self._request("DELETE", path)

    def create_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None:
        repo_encoded = _encode_repo(repository_name)
        ref_encoded = quote(reference, safe=":")
        path = f"/projects/{project_name}/repositories/{repo_encoded}/artifacts/{ref_encoded}/tags"
        self._request("POST", path, json={"name": tag})

    def delete_artifact_tag(
        self, project_name: str, repository_name: str, reference: str, tag: str
    ) -> None:
        repo_encoded = _encode_repo(repository_name)
        ref_encoded = quote(reference, safe=":")
        tag_encoded = quote(tag, safe="")
        path = (
            f"/projects/{project_name}/repositories/{repo_encoded}"
            f"/artifacts/{ref_encoded}/tags/{tag_encoded}"
        )
        self._request("DELETE", path)

    def ensure_label(self, name: str) -> Label:
        existing = self._get("/labels", params={"name": name, "scope": "g"})
        if existing:
            item = existing[0]
            return Label(id=item["id"], name=item["name"])
        created = self._request("POST", "/labels", json={"name": name, "scope": "g"})
        assert created is not None, "Harbor POST /labels returned empty body"
        return Label(id=created["id"], name=created["name"])

    def add_label_to_artifact(
        self,
        project_name: str,
        repository_name: str,
        reference: str,
        label_id: int,
    ) -> None:
        repo_encoded = _encode_repo(repository_name)
        ref_encoded = quote(reference, safe=":")
        path = (
            f"/projects/{project_name}/repositories/{repo_encoded}/artifacts/{ref_encoded}/labels"
        )
        self._request("POST", path, json={"id": label_id})

    def update_immutable_tag_rule(
        self,
        project_name: str,
        rule_id: int,
        scope_selector: str,
        tag_selector: str,
        disabled: bool,
    ) -> None:
        path = f"/projects/{project_name}/immutabletagrules/{rule_id}"
        payload = {
            "id": rule_id,
            "scope_selector": {"repository": {"decoration": scope_selector}},
            "tag_selector": {"decoration": "matches", "pattern": tag_selector},
            "disabled": disabled,
        }
        self._request("PUT", path, json=payload)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _paginate(self, path: str) -> Iterable[dict[str, Any]]:
        page = 1
        while True:
            data = self._get(path, params={"page": page, "page_size": PAGE_SIZE})
            if not data:
                return
            yield from data
            page += 1

    @retry(
        retry=retry_if_exception_type(HarborTransientError),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, max=2.0),
        reraise=True,
    )
    def _call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            r = self._client.request(method, self._base + path, **kwargs)
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

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._call("GET", path, params=params).json()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any | None:
        r = self._call(method, path, json=json, params=params)
        if not r.content:
            return None
        return r.json()


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
