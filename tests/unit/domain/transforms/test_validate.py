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
_UPGRADE = ("upgradePackages", {})


def _remediate(*steps: TransformStep, after: tuple[TransformStep, ...] = ()) -> None:
    validate_transform_steps(list(steps), role="remediate", preceding=after)


def test_accepts_upgrade_after_rewrite_in_the_remediation() -> None:
    _remediate(_step(*_REWRITE), _step(*_UPGRADE))


def test_accepts_upgrade_when_the_transform_rewrites_the_sources() -> None:
    _remediate(_step(*_UPGRADE), after=(_step(*_REWRITE), _step("setTimezone", {"zone": "UTC"})))


def test_rejects_upgrade_before_rewrite() -> None:
    # Upgrading first would fetch from the image's public repositories, not the mirror.
    with pytest.raises(PolicyValidationError) as e:
        _remediate(_step(*_UPGRADE), _step(*_REWRITE))
    assert "upgradePackages" in str(e.value) and "rewritePackageSources" in str(e.value)


def test_rejects_upgrade_without_rewrite() -> None:
    with pytest.raises(PolicyValidationError) as e:
        _remediate(_step(*_UPGRADE), after=(_step("injectCA", {"certs": ["corp"]}),))
    assert "upgradePackages" in str(e.value) and "rewritePackageSources" in str(e.value)


def test_rejects_a_second_upgrade_placed_before_the_rewrite() -> None:
    with pytest.raises(PolicyValidationError, match="rewritePackageSources"):
        _remediate(_step(*_UPGRADE), _step(*_REWRITE), _step(*_UPGRADE))


def test_upgrade_under_transform_points_to_remediate() -> None:
    with pytest.raises(PolicyValidationError, match="remediate:"):
        validate_transform_steps([_step(*_REWRITE), _step(*_UPGRADE)])


def test_rejects_a_transform_step_under_remediate() -> None:
    with pytest.raises(PolicyValidationError, match="not allowed under `remediate:`"):
        _remediate(_step("setTimezone", {"zone": "UTC"}))


def test_rejects_the_former_epoch_and_names_the_order() -> None:
    with pytest.raises(PolicyValidationError, match="remediation order"):
        _remediate(_step(*_REWRITE), _step("upgradePackages", {"epoch": "2026-10-10"}))


def test_rejects_any_other_upgrade_param() -> None:
    with pytest.raises(PolicyValidationError, match="upgradePackages"):
        _remediate(_step(*_REWRITE), _step("upgradePackages", {"force": True}))
