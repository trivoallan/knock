import pytest

from houba.domain.transforms.registry import BUILTIN_STEPS, DEFAULT_REGISTRY
from houba.domain.transforms.steps import InjectCA, RewritePackageSources, SetTimezone
from houba.errors import PolicyValidationError


def test_builtin_steps_are_the_three_primitives() -> None:
    types = {type(s) for s in BUILTIN_STEPS}
    assert types == {InjectCA, RewritePackageSources, SetTimezone}


def test_names_lists_all_builtins() -> None:
    assert DEFAULT_REGISTRY.names() == frozenset(
        {"injectCA", "rewritePackageSources", "setTimezone"}
    )


def test_get_returns_the_compiler() -> None:
    assert DEFAULT_REGISTRY.get("injectCA").name == "injectCA"


def test_get_unknown_raises_policy_validation_error() -> None:
    with pytest.raises(PolicyValidationError, match="unknown transform step 'enableFips'"):
        DEFAULT_REGISTRY.get("enableFips")
