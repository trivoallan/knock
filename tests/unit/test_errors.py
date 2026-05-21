import pytest

from houba.errors import (
    AdapterError,
    ConfigError,
    DomainError,
    H2HError,
    HarborAuthError,
    HarborError,
    HarborNotFoundError,
    HarborTransientError,
    InternalError,
    NoTagsToImportError,
    PropertiesValidationError,
    exit_code_for,
)


def test_hierarchy() -> None:
    assert issubclass(DomainError, H2HError)
    assert issubclass(AdapterError, H2HError)
    assert issubclass(ConfigError, H2HError)
    assert issubclass(InternalError, H2HError)
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
def test_exit_codes(exc: H2HError, expected_code: int) -> None:
    assert exit_code_for(exc) == expected_code


def test_exit_code_for_unknown_exception() -> None:
    assert exit_code_for(RuntimeError("boom")) == 4
