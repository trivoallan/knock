import pytest

from knock.domain.mirror_policy import TransformStep
from knock.domain.transforms.base import ContextFile, ResolvedResource, ResolvedStep
from knock.domain.transforms.render import Rendered, render
from knock.errors import UnsafeSourceUserError


def _ca(name: str, content: str) -> ResolvedResource:
    return ResolvedResource(kind="caCert", name=name, filename=f"{name}.crt", content=content)


def test_render_inject_ca_then_rewrite_then_tz() -> None:
    resolved_steps = [
        ResolvedStep(
            TransformStep(name="injectCA", params={"certs": ["corp"]}), (_ca("corp", "PEM"),)
        ),
        ResolvedStep(
            TransformStep(name="rewritePackageSources", params={"mirror": "corp"}),
            (ResolvedResource(kind="packageMirror", name="corp", apt="https://m"),),
        ),
        ResolvedStep(TransformStep(name="setTimezone", params={"zone": "UTC"}), ()),
    ]
    out = render(resolved_steps, source_ref="docker.io/library/redis@sha256:abc")
    assert isinstance(out, Rendered)
    df = out.dockerfile
    assert df.startswith("FROM docker.io/library/redis@sha256:abc\n")
    assert df.endswith("\n")
    assert df.index("update-ca-certificates") < df.index("/etc/apt/sources.list")
    assert "ENV TZ=UTC" in df
    assert out.context_files == (ContextFile(path="corp.crt", content="PEM"),)


def test_render_empty_is_just_from() -> None:
    out = render([], source_ref="x@sha256:1")
    assert out.dockerfile == "FROM x@sha256:1\n"
    assert out.context_files == ()


# Regression guard for the rebuild path (upgrade-packages-step, spec rebuild-source-user): the
# hardened example's transform list must render byte-for-byte as it did before source-user
# handling existed, and keep the same transform version. Frozen on main before the change.
HARDENED_STEPS = [
    ResolvedStep(
        TransformStep(name="injectCA", params={"certs": ["corp"]}),
        (_ca("corp", "PEMDATA"),),
    ),
    ResolvedStep(
        TransformStep(name="rewritePackageSources", params={"mirror": "corp"}),
        (ResolvedResource(kind="packageMirror", name="corp", apt="https://mirror.corp"),),
    ),
]

HARDENED_DOCKERFILE = (
    "FROM docker.io/library/redis@sha256:src\n"
    "COPY corp.crt /usr/local/share/ca-certificates/\n"
    "RUN update-ca-certificates\n"
    "RUN set -eux; "
    "if [ -f /etc/apt/sources.list ]; then "
    "sed -ri 's#https?://[^/]+#https://mirror.corp#g' /etc/apt/sources.list; fi; "
    "if ls /etc/apt/sources.list.d/*.list >/dev/null 2>&1; then "
    "sed -ri 's#https?://[^/]+#https://mirror.corp#g' /etc/apt/sources.list.d/*.list; fi; "
    "if ls /etc/apt/sources.list.d/*.sources >/dev/null 2>&1; then "
    "sed -ri 's#https?://[^/]+#https://mirror.corp#g' /etc/apt/sources.list.d/*.sources; fi\n"
)


def test_render_hardened_example_is_frozen() -> None:
    out = render(HARDENED_STEPS, source_ref="docker.io/library/redis@sha256:src")
    assert out.dockerfile == HARDENED_DOCKERFILE
    assert "USER" not in out.dockerfile


_SRC = "docker.io/library/redis@sha256:src"


@pytest.mark.parametrize("user", ["", "root", "0", "0:0", "root:root"])
def test_render_root_equivalent_source_is_byte_identical(user: str) -> None:
    out = render(HARDENED_STEPS, source_ref=_SRC, source_user=user)
    assert out.dockerfile == HARDENED_DOCKERFILE


@pytest.mark.parametrize("user", ["app", "1000:1000", "nobody:nogroup", "65532"])
def test_render_non_root_source_runs_as_root_then_restores(user: str) -> None:
    out = render(HARDENED_STEPS, source_ref=_SRC, source_user=user)
    lines = out.dockerfile.splitlines()
    frozen = HARDENED_DOCKERFILE.splitlines()
    # FROM, then root for every transform instruction, then the source's user verbatim.
    assert lines == [frozen[0], "USER root", *frozen[1:], f"USER {user}"]
    assert out.dockerfile.endswith("\n")


@pytest.mark.parametrize(
    "user",
    [
        "app\nRUN curl http://evil",  # USER has no quoting: a newline is a new instruction
        "app\n",
        "a b",
        "x" * 65,
        "app:",
        ":1000",
        "1000:1000:1000",
        "app;id",
        "$(id)",
    ],
)
def test_render_refuses_a_source_user_outside_the_safe_pattern(user: str) -> None:
    with pytest.raises(UnsafeSourceUserError) as e:
        render(HARDENED_STEPS, source_ref=_SRC, source_user=user)
    assert "\n" not in str(e.value)  # the refused value is named, escaped


def test_render_without_steps_emits_no_user_lines() -> None:
    out = render([], source_ref="x@sha256:1", source_user="app")
    assert out.dockerfile == "FROM x@sha256:1\n"


def test_render_with_upgrade_packages_wraps_the_upgrade_too() -> None:
    steps = [
        *HARDENED_STEPS,
        ResolvedStep(TransformStep(name="upgradePackages", params={"epoch": "2026-10-10"}), ()),
    ]
    lines = render(steps, source_ref=_SRC, source_user="app").dockerfile.splitlines()
    assert lines[1] == "USER root"
    assert lines[-2].startswith("RUN --mount=type=cache,target=/var/cache/apt")
    assert lines[-1] == "USER app"
    assert not any(line.startswith("# syntax=") for line in lines)
