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
