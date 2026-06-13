import pytest

from houba.errors import (
    AdapterError,
    BuildkitError,
    ConfigError,
    DomainError,
    HoubaError,
    InternalError,
    PolicyValidationError,
    RegctlError,
    ScanReportError,
    UnknownFormatError,
    exit_code_for,
)


def test_hierarchy() -> None:
    assert issubclass(DomainError, HoubaError)
    assert issubclass(AdapterError, HoubaError)
    assert issubclass(ConfigError, HoubaError)
    assert issubclass(InternalError, HoubaError)
    assert issubclass(RegctlError, AdapterError)
    assert issubclass(BuildkitError, AdapterError)


@pytest.mark.parametrize(
    "exc,expected_code",
    [
        (DomainError("x"), 1),
        (AdapterError("x"), 2),
        (RegctlError("x"), 2),
        (BuildkitError("x"), 2),
        (ConfigError("x"), 3),
        (InternalError("x"), 4),
    ],
)
def test_exit_codes(exc: HoubaError, expected_code: int) -> None:
    assert exit_code_for(exc) == expected_code


def test_exit_code_for_unknown_exception() -> None:
    assert exit_code_for(RuntimeError("boom")) == 4


def test_policy_validation_error_is_domain_error_exit_1() -> None:
    err = PolicyValidationError("bad policy")
    assert isinstance(err, DomainError)
    assert exit_code_for(err) == 1


def test_cosign_error_is_adapter_exit_2() -> None:
    from houba.errors import CosignError, exit_code_for

    assert exit_code_for(CosignError("boom")) == 2


def test_scan_report_error_is_domain_exit_1() -> None:
    assert issubclass(ScanReportError, DomainError)
    assert exit_code_for(ScanReportError("bad sarif")) == 1


def test_unknown_format_error_is_domain_exit_1() -> None:
    assert issubclass(UnknownFormatError, DomainError)
    assert exit_code_for(UnknownFormatError("nope")) == 1
