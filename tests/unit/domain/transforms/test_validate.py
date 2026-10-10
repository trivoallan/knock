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


_REWRITE = ("rewritePackageSources", {"mirror": "corp"})
_UPGRADE = ("upgradePackages", {"epoch": "2026-10-10"})


def test_accepts_upgrade_after_rewrite() -> None:
    validate_transform_steps([_step(*_REWRITE), _step(*_UPGRADE)])


def test_accepts_upgrade_after_rewrite_with_steps_between() -> None:
    validate_transform_steps(
        [_step(*_REWRITE), _step("setTimezone", {"zone": "UTC"}), _step(*_UPGRADE)]
    )


def test_rejects_upgrade_before_rewrite() -> None:
    # Upgrading first would fetch from the image's public repositories, not the mirror.
    with pytest.raises(PolicyValidationError) as e:
        validate_transform_steps([_step(*_UPGRADE), _step(*_REWRITE)])
    assert "upgradePackages" in str(e.value) and "rewritePackageSources" in str(e.value)


def test_rejects_upgrade_without_rewrite() -> None:
    with pytest.raises(PolicyValidationError) as e:
        validate_transform_steps([_step("injectCA", {"certs": ["corp"]}), _step(*_UPGRADE)])
    assert "upgradePackages" in str(e.value) and "rewritePackageSources" in str(e.value)


def test_rejects_a_second_upgrade_placed_before_the_rewrite() -> None:
    with pytest.raises(PolicyValidationError, match="rewritePackageSources"):
        validate_transform_steps([_step(*_UPGRADE), _step(*_REWRITE), _step(*_UPGRADE)])


@pytest.mark.parametrize(
    "params",
    [
        {},  # epoch is required
        {"epoch": ""},
        {"epoch": '"; rm -rf /'},
        {"epoch": "2026 10 10"},
        {"epoch": "2026-10-10\n"},  # a trailing newline would end the RUN instruction
        {"epoch": "x" * 65},
        {"epoch": 20261010},  # not a string
        {"epoch": "2026-10-10", "extra": True},
    ],
)
def test_rejects_upgrade_epoch_outside_the_pattern(params: dict[str, Any]) -> None:
    with pytest.raises(PolicyValidationError, match="upgradePackages"):
        validate_transform_steps([_step(*_REWRITE), _step("upgradePackages", params)])


def test_accepts_epoch_at_the_pattern_bounds() -> None:
    for epoch in ("1", "x" * 64, "2026-10-10", "v1.2_rc-3"):
        validate_transform_steps([_step(*_REWRITE), _step("upgradePackages", {"epoch": epoch})])
