"""Adapter HTTP pour endoflife.date."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from houba.errors import EolSourceError
from houba.ports.eol_source import EolEntry

MAX_ATTEMPTS = 5


class _Transient(EolSourceError):
    """Erreur transitoire interne, déclenche un retry."""


class EndoflifeHttpAdapter:
    def __init__(self, *, base_url: str = "https://endoflife.date/api") -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))

    def fetch_eol(self, product: str) -> list[EolEntry]:
        data = self._get(f"/{product}.json")
        if not isinstance(data, list):
            raise EolSourceError(f"unexpected payload from endoflife.date: {type(data).__name__}")
        return [_to_entry(item) for item in data]

    @retry(
        retry=retry_if_exception_type(_Transient),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, max=2.0),
        reraise=True,
    )
    def _get(self, path: str) -> Any:
        try:
            r = self._client.get(self._base + path)
        except httpx.HTTPError as e:
            raise _Transient(str(e)) from e
        if r.status_code == 404:
            raise EolSourceError(f"{path}: 404")
        if 500 <= r.status_code < 600:
            raise _Transient(f"{r.status_code}: {r.text}")
        if not r.is_success:
            raise EolSourceError(f"{r.status_code}: {r.text}")
        return r.json()


def _to_entry(item: dict[str, Any]) -> EolEntry:
    raw_eol = item.get("eol", "")
    # endoflife.date renvoie soit une date ISO, soit bool ; on stocke en str brut.
    eol_str = str(raw_eol).lower() if isinstance(raw_eol, bool) else str(raw_eol)
    return EolEntry(
        cycle=str(item.get("cycle", "")),
        eol=eol_str,
        latest=str(item.get("latest", "")),
        lts=bool(item.get("lts", False)),
    )
