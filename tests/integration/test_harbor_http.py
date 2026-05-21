import httpx
import pytest
import respx

from hub2hub.adapters.harbor_http import HarborHttpAdapter
from hub2hub.errors import HarborAuthError, HarborNotFoundError, HarborTransientError


@pytest.fixture()
def adapter() -> HarborHttpAdapter:
    return HarborHttpAdapter(
        base_url="https://harbor.example.com",
        user="robot$h2h",
        password="s3cret",
    )


def test_get_repositories_paginates_until_empty(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        page1 = [{"name": "lib/a", "project_id": 1, "artifact_count": 2}]
        page2 = [{"name": "lib/b", "project_id": 1, "artifact_count": 1}]
        router.get(
            "/api/v2.0/projects/lib/repositories", params={"page": "1", "page_size": "100"}
        ).respond(200, json=page1)
        router.get(
            "/api/v2.0/projects/lib/repositories", params={"page": "2", "page_size": "100"}
        ).respond(200, json=page2)
        router.get(
            "/api/v2.0/projects/lib/repositories", params={"page": "3", "page_size": "100"}
        ).respond(200, json=[])

        repos = adapter.get_repositories("lib")
        assert [r.name for r in repos] == ["lib/a", "lib/b"]


def test_get_artifacts_url_double_encodes_repository(adapter: HarborHttpAdapter) -> None:
    """Bug historique : un repo `foo/bar` doit être double-encodé dans l'URL."""
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.get("/api/v2.0/projects/lib/repositories/foo%252Fbar/artifacts").respond(
            200, json=[]
        )
        adapter.get_artifacts("lib", "foo/bar")
        assert route.called


def test_auth_error_maps_401(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get("/api/v2.0/projects/lib/repositories").respond(401, json={"errors": []})
        with pytest.raises(HarborAuthError):
            adapter.get_repositories("lib")


def test_not_found_error_maps_404(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get("/api/v2.0/projects/lib/repositories").respond(404, json={"errors": []})
        with pytest.raises(HarborNotFoundError):
            adapter.get_repositories("lib")


def test_transient_5xx_retried_then_succeeds(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        responses = [
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json=[]),
        ]
        route = router.get(
            "/api/v2.0/projects/lib/repositories", params={"page": "1", "page_size": "100"}
        ).mock(side_effect=responses)
        adapter.get_repositories("lib")
        assert route.call_count == 3


def test_transient_5xx_exhausts_retries_then_raises(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get(
            "/api/v2.0/projects/lib/repositories", params={"page": "1", "page_size": "100"}
        ).respond(503)
        with pytest.raises(HarborTransientError):
            adapter.get_repositories("lib")
