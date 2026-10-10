from knock.domain.mirror_policy import TransformStep
from knock.domain.transforms.base import ResolvedResource, ResolvedStep
from knock.domain.transforms.render import transform_version


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


def test_version_of_hardened_example_is_frozen() -> None:
    # Frozen on main before upgrade-packages-step: the renderer may change, the version may not.
    from tests.unit.domain.transforms.test_render import HARDENED_STEPS

    assert (
        transform_version(HARDENED_STEPS)
        == "sha256:972aa31c2ed39c22cf3187a8eec7b681a9b930f41a514012886e76c2e45ecac1"
    )


def _with_upgrade(epoch: str) -> list[ResolvedStep]:
    return [
        *_steps(),
        ResolvedStep(TransformStep(name="upgradePackages", params={"epoch": epoch}), ()),
    ]


def test_version_changes_with_the_upgrade_epoch() -> None:
    # The epoch is the human trigger: a new one must plan a rebuild.
    assert transform_version(_with_upgrade("2026-10-10")) != transform_version(
        _with_upgrade("2026-10-11")
    )


def test_version_is_stable_for_the_same_epoch() -> None:
    assert transform_version(_with_upgrade("2026-10-10")) == transform_version(
        _with_upgrade("2026-10-10")
    )
