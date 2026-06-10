import pytest

from houba.errors import (
    AdapterError,
    ConfigError,
    DomainError,
    HarborAuthError,
    HarborError,
    HarborNotFoundError,
    HarborTransientError,
    HoubaError,
    InternalError,
    NoTagsToImportError,
    PropertiesValidationError,
    exit_code_for,
)


def test_hierarchy() -> None:
    assert issubclass(DomainError, HoubaError)
    assert issubclass(AdapterError, HoubaError)
    assert issubclass(ConfigError, HoubaError)
    assert issubclass(InternalError, HoubaError)
    assert issubclass(HarborError, AdapterError)
    assert issubclass(HarborAuthError, HarborError)
    assert issubclass(HarborNotFoundError, HarborError)
    assert issubclass(HarborTransientError, HarborError)
    assert issubclass(PropertiesValidationError, DomainError)
    assert issubclass(NoTagsToImportError, DomainError)


@pytest.mark.parametrize(
    "exc,expected_code",
    [
        (DomainError("x"), 1),
        (PropertiesValidationError("x"), 1),
        (AdapterError("x"), 2),
        (HarborAuthError("x"), 2),
        (ConfigError("x"), 3),
        (InternalError("x"), 4),
    ],
)
def test_exit_codes(exc: HoubaError, expected_code: int) -> None:
    assert exit_code_for(exc) == expected_code


def test_exit_code_for_unknown_exception() -> None:
    assert exit_code_for(RuntimeError("boom")) == 4


def test_policy_validation_error_is_domain_error_exit_1() -> None:
    from houba.errors import DomainError, PolicyValidationError, exit_code_for

    err = PolicyValidationError("bad policy")
    assert isinstance(err, DomainError)
    assert exit_code_for(err) == 1
