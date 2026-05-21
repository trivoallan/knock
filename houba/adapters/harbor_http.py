"""Adaptateur HTTP pour Harbor v2 (méthodes de lecture)."""

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
from houba.ports.harbor import Artifact, ArtifactTag, ImmutableTagRule, Repository

PAGE_SIZE = 100
MAX_ATTEMPTS = 5


class HarborHttpAdapter:
    def __init__(self, *, base_url: str, user: str, password: str) -> None:
        self._base = base_url.rstrip("/") + "/api/v2.0"
        self._client = httpx.Client(
            auth=(user, password),
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Accept": "application/json"},
        )

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
        # Harbor exige un double encodage du nom de repo : les `/` doivent rester
        # encodés côté serveur après le routing. Voir vars/HarborApi.groovy et
        # ci/harbor.py — bug historique reproduit ici intentionnellement.
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
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

    def get_artifact(
        self, project_name: str, repository_name: str, reference: str
    ) -> Artifact:
        repo_encoded = quote(quote(repository_name, safe=""), safe="")
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
    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        try:
            r = self._client.get(self._base + path, params=params)
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
