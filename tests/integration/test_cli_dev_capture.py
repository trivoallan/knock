import json
from pathlib import Path

import pytest
import respx
from typer.testing import CliRunner

from houba.cli.main import app


@pytest.fixture()
def harbor_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOUBA_HARBOR_URL", "https://harbor.example.com")
    monkeypatch.setenv("HOUBA_HARBOR_USER", "u")
    monkeypatch.setenv("HOUBA_HARBOR_PASSWORD", "p")
    monkeypatch.setenv("HOUBA_GITLAB_URL", "https://gl")
    monkeypatch.setenv("HOUBA_GITLAB_TOKEN", "t")
    monkeypatch.setenv("HOUBA_GITLAB_GROUP", "g")


def test_capture_writes_repositories_and_artifacts(
    harbor_env: None,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    with respx.mock(base_url="https://harbor.example.com") as router:
        router.get(
            "/api/v2.0/projects/lib/repositories", params={"page": "1", "page_size": "100"}
        ).respond(
            200,
            json=[{"name": "lib/foo", "project_id": 1, "artifact_count": 1}],
        )
        router.get(
            "/api/v2.0/projects/lib/repositories", params={"page": "2", "page_size": "100"}
        ).respond(200, json=[])
        router.get(
            "/api/v2.0/projects/lib/repositories/foo/artifacts",
            params={"page": "1", "page_size": "100"},
        ).respond(
            200,
            json=[
                {
                    "digest": "sha256:abc",
                    "tags": [{"name": "v1"}],
                    "push_time": "2026-01-01T00:00:00Z",
                }
            ],
        )
        router.get(
            "/api/v2.0/projects/lib/repositories/foo/artifacts",
            params={"page": "2", "page_size": "100"},
        ).respond(200, json=[])

        result = runner.invoke(
            app,
            [
                "dev",
                "capture",
                "--project",
                "lib",
                "--repository",
                "foo",
                "--output",
                str(tmp_path),
            ],
        )

    assert result.exit_code == 0, result.stdout

    repos = json.loads((tmp_path / "lib__repositories.json").read_text())
    arts = json.loads((tmp_path / "lib__foo__artifacts.json").read_text())
    assert repos[0]["name"] == "lib/foo"
    assert arts[0]["digest"] == "sha256:abc"
