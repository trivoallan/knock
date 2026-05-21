import httpx
import pytest
import respx

from houba.adapters.harbor_http import HarborHttpAdapter
from houba.errors import HarborAuthError, HarborNotFoundError, HarborTransientError
from houba.ports.harbor import ArtifactTag, ImmutableTagRule, Label


@pytest.fixture()
def adapter() -> HarborHttpAdapter:
    return HarborHttpAdapter(
        base_url="https://harbor.example.com",
        user="robot$houba",
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


def test_auth_error_maps_403(adapter: HarborHttpAdapter) -> None:
    """Spec §6.3 : HarborAuthError couvre 401 ET 403 (permissions robot insuffisantes)."""
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get("/api/v2.0/projects/lib/repositories").respond(403, json={"errors": []})
        with pytest.raises(HarborAuthError):
            adapter.get_repositories("lib")


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


# ---------------------------------------------------------------------------
# Write methods
# ---------------------------------------------------------------------------


def test_delete_repository(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.delete(
            "/api/v2.0/projects/lib/repositories/busybox"
        ).respond(200)
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
            json={"name": "stable"},
        ).respond(201)
        adapter.create_artifact_tag("lib", "busybox", "sha256:abc", "stable")
        assert route.called


def test_delete_artifact_tag(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.delete(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/sha256:abc/tags/stable"
        ).respond(200)
        adapter.delete_artifact_tag("lib", "busybox", "sha256:abc", "stable")
        assert route.called


def test_ensure_label_creates_when_absent(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get(
            "/api/v2.0/labels",
            params={"name": "stable", "scope": "g"},
        ).respond(200, json=[])
        router.post(
            "/api/v2.0/labels",
            json={"name": "stable", "scope": "g"},
        ).respond(201, json={"id": 7, "name": "stable"})
        label = adapter.ensure_label("stable")
        assert label == Label(id=7, name="stable")


def test_ensure_label_returns_existing(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get(
            "/api/v2.0/labels",
            params={"name": "stable", "scope": "g"},
        ).respond(200, json=[{"id": 7, "name": "stable"}])
        label = adapter.ensure_label("stable")
        assert label == Label(id=7, name="stable")


def test_add_label_to_artifact(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.post(
            "/api/v2.0/projects/lib/repositories/busybox/artifacts/sha256:abc/labels",
            json={"id": 7},
        ).respond(200)
        adapter.add_label_to_artifact("lib", "busybox", "sha256:abc", 7)
        assert route.called


def test_update_immutable_tag_rule(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.put(
            "/api/v2.0/projects/lib/immutabletagrules/42",
        ).respond(200)
        adapter.update_immutable_tag_rule("lib", 42, "**", "v*", disabled=False)
        assert route.called


def test_delete_repository_double_encodes_repo(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.delete(
            "/api/v2.0/projects/lib/repositories/foo%252Fbar"
        ).respond(200)
        adapter.delete_repository("lib", "foo/bar")
        assert route.called


def test_delete_artifact_double_encodes_repo(adapter: HarborHttpAdapter) -> None:
    with respx.mock(base_url="https://harbor.example.com") as router:
        route = router.delete(
            "/api/v2.0/projects/lib/repositories/foo%252Fbar/artifacts/sha256:abc"
        ).respond(200)
        adapter.delete_artifact("lib", "foo/bar", "sha256:abc")
        assert route.called
