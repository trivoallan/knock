from typing import Any

import pytest

from knock.domain.mirror_policy import TransformStep
from knock.domain.transforms.render import validate_transform_steps
from knock.errors import PolicyValidationError


def _step(name: str, params: dict[str, Any]) -> TransformStep:
    return TransformStep(name=name, params=params)


def test_accepts_the_three_known_steps() -> None:
    validate_transform_steps(
        [
            _step("injectCA", {"certs": ["corp", "partner"]}),
            _step("rewritePackageSources", {"mirror": "corp"}),
            _step("setTimezone", {"zone": "Europe/Paris"}),
        ]
    )


def test_empty_is_valid() -> None:
    validate_transform_steps([])


def test_rejects_unknown_step_name() -> None:
    with pytest.raises(PolicyValidationError, match="unknown transform step 'enableFips'"):
        validate_transform_steps([_step("enableFips", {})])


def test_rejects_injectca_not_a_list() -> None:
    with pytest.raises(PolicyValidationError, match="injectCA"):
        validate_transform_steps([_step("injectCA", {"certs": "corp"})])


def test_rejects_injectca_empty_list() -> None:
    with pytest.raises(PolicyValidationError, match="injectCA"):
        validate_transform_steps([_step("injectCA", {"certs": []})])


def test_rejects_injectca_unknown_param() -> None:
    with pytest.raises(PolicyValidationError, match="injectCA"):
        validate_transform_steps([_step("injectCA", {"certz": ["corp"]})])


def test_rejects_rewrite_non_string_mirror() -> None:
    with pytest.raises(PolicyValidationError, match="rewritePackageSources"):
        validate_transform_steps([_step("rewritePackageSources", {"mirror": ["corp"]})])


def test_rejects_set_timezone_missing_zone() -> None:
    with pytest.raises(PolicyValidationError, match="setTimezone"):
        validate_transform_steps([_step("setTimezone", {})])
