"""Adaptateur HTTP pour Harbor v2 (méthodes de lecture)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from hub2hub.errors import (
    HarborAuthError,
    HarborError,
    HarborNotFoundError,
    HarborTransientError,
)
from hub2hub.ports.harbor import Artifact, Repository

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

        if r.status_code == 401:
            raise HarborAuthError(r.text)
        if r.status_code == 404:
            raise HarborNotFoundError(f"{path}: {r.text}")
        if 500 <= r.status_code < 600:
            raise HarborTransientError(f"{r.status_code}: {r.text}")
        if not r.is_success:
            raise HarborError(f"{r.status_code}: {r.text}")
        return r.json()
