import pytest
from pydantic import ValidationError

from knock.domain.mirror_policy import TransformStep
from knock.domain.transforms.base import ResourceRef
from knock.domain.transforms.registry import BUILTIN_STEPS, DEFAULT_REGISTRY, step_resource_refs
from knock.domain.transforms.steps import (
    InjectCA,
    RewritePackageSources,
    SetTimezone,
    UpgradePackages,
)
from knock.errors import PolicyValidationError


def test_builtin_steps_are_the_four_primitives() -> None:
    types = {type(s) for s in BUILTIN_STEPS}
    assert types == {InjectCA, RewritePackageSources, SetTimezone, UpgradePackages}


def test_names_lists_all_builtins() -> None:
    assert DEFAULT_REGISTRY.names() == frozenset(
        {"injectCA", "rewritePackageSources", "setTimezone", "upgradePackages"}
    )


def test_get_returns_the_compiler() -> None:
    assert DEFAULT_REGISTRY.get("injectCA").name == "injectCA"


def test_get_unknown_raises_policy_validation_error() -> None:
    with pytest.raises(PolicyValidationError, match="unknown transform step 'enableFips'"):
        DEFAULT_REGISTRY.get("enableFips")


def test_step_resource_refs_returns_the_compiler_refs() -> None:
    step = TransformStep(name="injectCA", params={"certs": ["a", "b"]})
    assert step_resource_refs(step, remediate=False) == (
        ResourceRef("caCert", "a"),
        ResourceRef("caCert", "b"),
    )


def test_step_resource_refs_validates_params() -> None:
    step = TransformStep(name="injectCA", params={"certs": []})
    with pytest.raises(ValidationError):
        step_resource_refs(step, remediate=False)


def test_step_resource_refs_unknown_step_raises() -> None:
    with pytest.raises(PolicyValidationError, match="unknown transform step"):
        step_resource_refs(TransformStep(name="nope"), remediate=False)


def test_step_resource_refs_picks_the_model_by_role() -> None:
    # upgradePackages: the policy model takes no epoch, the rendering model requires one.
    bare = TransformStep(name="upgradePackages")
    assert step_resource_refs(bare, remediate=True) == ()
    with pytest.raises(ValidationError):
        step_resource_refs(bare, remediate=False)
    with_epoch = TransformStep(name="upgradePackages", params={"epoch": "2026-01-01"})
    assert step_resource_refs(with_epoch, remediate=False) == ()
    with pytest.raises(ValidationError):
        step_resource_refs(with_epoch, remediate=True)
