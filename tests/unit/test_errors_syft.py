from __future__ import annotations

from houba.errors import AdapterError, SyftError, exit_code_for


def test_syft_error_is_adapter_error_exit_2() -> None:
    err = SyftError("boom")
    assert isinstance(err, AdapterError)
    assert exit_code_for(err) == 2
