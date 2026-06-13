from __future__ import annotations

import pytest

from houba.config import Settings


def test_purge_settings_default_to_none_and_30(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "HOUBA_USAGE_ORACLE_CMD",
        "HOUBA_PURGE_MIN_IDLE_DAYS",
        "HOUBA_USAGE_ORACLE_TIMEOUT",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings()
    assert s.usage_oracle_cmd is None
    assert s.purge_min_idle_days is None
    assert s.usage_oracle_timeout == 30


def test_purge_settings_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOUBA_USAGE_ORACLE_CMD", "/opt/oracles/datadog.sh")
    monkeypatch.setenv("HOUBA_PURGE_MIN_IDLE_DAYS", "15")
    monkeypatch.setenv("HOUBA_USAGE_ORACLE_TIMEOUT", "45")
    s = Settings()
    assert s.usage_oracle_cmd == "/opt/oracles/datadog.sh"
    assert s.purge_min_idle_days == 15
    assert s.usage_oracle_timeout == 45
