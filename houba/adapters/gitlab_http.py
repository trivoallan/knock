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
