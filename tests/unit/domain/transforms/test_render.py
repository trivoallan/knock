from knock.domain.mirror_policy import TransformStep
from knock.domain.transforms.base import ContextFile, ResolvedResource, ResolvedStep
from knock.domain.transforms.render import Rendered, render


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
