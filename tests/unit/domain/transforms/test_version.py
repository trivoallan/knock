from houba.domain.mirror_policy import TransformStep
from houba.domain.transforms.base import ResolvedResource, ResolvedStep
from houba.domain.transforms.render import transform_version


def _steps(cert_content: str = "PEM", apt: str = "https://m") -> list[ResolvedStep]:
    return [
        ResolvedStep(
            TransformStep(name="injectCA", params={"certs": ["corp"]}),
            (
                ResolvedResource(
                    kind="caCert", name="corp", filename="corp.crt", content=cert_content
                ),
            ),
        ),
        ResolvedStep(
            TransformStep(name="rewritePackageSources", params={"mirror": "corp"}),
            (ResolvedResource(kind="packageMirror", name="corp", apt=apt),),
        ),
    ]


def test_version_is_stable_and_prefixed() -> None:
    assert transform_version(_steps()) == transform_version(_steps())
    assert transform_version(_steps()).startswith("sha256:")


def test_version_changes_with_cert_content() -> None:
    assert transform_version(_steps(cert_content="PEM")) != transform_version(
        _steps(cert_content="NEWPEM")
    )


def test_version_changes_with_mirror_url() -> None:
    assert transform_version(_steps(apt="https://a")) != transform_version(_steps(apt="https://b"))


def test_version_changes_with_params() -> None:
    base = transform_version(_steps())
    other = [
        ResolvedStep(
            TransformStep(name="injectCA", params={"certs": ["corp", "extra"]}),
            (
                ResolvedResource(kind="caCert", name="corp", filename="corp.crt", content="PEM"),
                ResolvedResource(kind="caCert", name="extra", filename="extra.crt", content="PEM"),
            ),
        ),
    ]
    assert base != transform_version(other)


def test_version_changes_with_step_order() -> None:
    assert transform_version(_steps()) != transform_version(list(reversed(_steps())))
