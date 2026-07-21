import pytest

from knock.domain.mirror_policy import TransformStep
from knock.domain.transforms.base import (
    ContextFile,
    Fragment,
    ResolvedResource,
    ResolvedStep,
    ResourceRef,
    TransformStepCompiler,
)


def test_fragment_defaults_to_no_context_files() -> None:
    frag = Fragment(instructions=("RUN true",))
    assert frag.instructions == ("RUN true",)
    assert frag.context_files == ()


def test_resolved_step_pairs_step_with_resources() -> None:
    step = TransformStep(name="injectCA", params={"certs": ["corp"]})
    rr = ResolvedResource(kind="caCert", name="corp", filename="corp.crt", content="PEM")
    rs = ResolvedStep(step=step, resources=(rr,))
    assert rs.step.name == "injectCA"
    assert rs.resources[0].content == "PEM"


def test_compiler_is_abstract() -> None:
    with pytest.raises(TypeError):
        TransformStepCompiler()  # type: ignore[abstract]


def test_value_objects_are_frozen() -> None:
    ref = ResourceRef(kind="caCert", name="corp")
    cf = ContextFile(path="corp.crt", content="PEM")
    with pytest.raises(Exception):  # noqa: B017
        ref.name = "other"  # type: ignore[misc]
    with pytest.raises(Exception):  # noqa: B017
        cf.path = "x"  # type: ignore[misc]
