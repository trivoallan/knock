from typing import Any

import pytest

from houba.domain.mirror_policy import TransformStep
from houba.domain.transform import validate_transform_steps
from houba.errors import PolicyValidationError


def _step(name: str, params: dict[str, Any]) -> TransformStep:
    return TransformStep(name=name, params=params)


def test_accepts_the_two_known_steps() -> None:
    validate_transform_steps(
        [
            _step("injectCA", {"certs": ["corp-root", "partner-ca"]}),
            _step("rewritePackageSources", {"mirror": "corp"}),
        ]
    )  # no raise


def test_empty_is_valid() -> None:
    validate_transform_steps([])  # no raise


def test_rejects_unknown_step_name() -> None:
    with pytest.raises(PolicyValidationError, match="unknown transform step 'setTimezone'"):
        validate_transform_steps([_step("setTimezone", {"tz": "UTC"})])


def test_rejects_injectca_without_list_of_strings() -> None:
    with pytest.raises(PolicyValidationError, match=r"injectCA\.certs"):
        validate_transform_steps([_step("injectCA", {"certs": "corp-root"})])


def test_rejects_injectca_empty_list() -> None:
    with pytest.raises(PolicyValidationError, match=r"injectCA\.certs"):
        validate_transform_steps([_step("injectCA", {"certs": []})])


def test_rejects_rewrite_without_string_mirror() -> None:
    with pytest.raises(PolicyValidationError, match=r"rewritePackageSources\.mirror"):
        validate_transform_steps([_step("rewritePackageSources", {"mirror": ["corp"]})])
