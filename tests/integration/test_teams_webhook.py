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
