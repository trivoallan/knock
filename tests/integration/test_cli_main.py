from unittest.mock import patch

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError
from typer.testing import CliRunner

from houba.cli.main import _run, app
from houba.errors import ConfigError, HarborAuthError, NoTagsToImportError, PolicyValidationError


def test_houba_version_outputs_version_string() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_houba_help_lists_subgroups() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dev" in result.stdout
    assert "version" in result.stdout


def test_run_maps_validation_error_to_exit_3() -> None:
    """ValidationError de Pydantic (config invalide) → exit 3."""

    def _raise() -> None:
        raise ValidationError.from_exception_data("Settings", [])

    with patch("houba.cli.main.app", side_effect=_raise):
        with pytest.raises(SystemExit) as excinfo:
            _run()
    assert excinfo.value.code == 3


def test_run_maps_settings_error_to_exit_3() -> None:
    """SettingsError (ex. HOUBA_REGISTRIES au JSON malformé) → exit 3 (config)."""

    def _raise() -> None:
        raise SettingsError(
            "error parsing value for field 'registries' from source 'EnvSettingsSource'"
        )

    with patch("houba.cli.main.app", side_effect=_raise):
        with pytest.raises(SystemExit) as excinfo:
            _run()
    assert excinfo.value.code == 3


@pytest.mark.parametrize(
    "exc,expected_code",
    [
        (ConfigError("boom"), 3),
        (NoTagsToImportError("nada"), 1),
        (HarborAuthError("401"), 2),
        (PolicyValidationError("bad"), 1),
    ],
)
def test_run_maps_houba_errors_to_exit_codes(exc: Exception, expected_code: int) -> None:
    def _raise() -> None:
        raise exc

    with patch("houba.cli.main.app", side_effect=_raise):
        with pytest.raises(SystemExit) as excinfo:
            _run()
    assert excinfo.value.code == expected_code
