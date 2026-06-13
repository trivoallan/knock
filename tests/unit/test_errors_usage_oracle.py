from __future__ import annotations

from houba.errors import AdapterError, UsageOracleError, exit_code_for


def test_usage_oracle_error_is_adapter_error_exit_2() -> None:
    assert issubclass(UsageOracleError, AdapterError)
    assert exit_code_for(UsageOracleError("boom")) == 2
