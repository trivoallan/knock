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
