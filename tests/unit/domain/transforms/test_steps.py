from houba.domain.transforms.base import ContextFile, Fragment, ResolvedResource, ResourceRef
from houba.domain.transforms.steps import InjectCA, RewritePackageSources


def _cert(name: str, content: str) -> ResolvedResource:
    return ResolvedResource(kind="caCert", name=name, filename=f"{name}.crt", content=content)


def test_inject_ca_resource_refs_one_per_cert() -> None:
    p = InjectCA.params_model(certs=["corp", "partner"])
    assert InjectCA().resource_refs(p) == (
        ResourceRef("caCert", "corp"),
        ResourceRef("caCert", "partner"),
    )


def test_inject_ca_fragment_copies_and_updates_trust_store() -> None:
    p = InjectCA.params_model(certs=["corp", "partner"])
    resources = (_cert("corp", "PEM1"), _cert("partner", "PEM2"))
    frag = InjectCA().fragment(p, resources)
    assert frag == Fragment(
        instructions=(
            "COPY corp.crt partner.crt /usr/local/share/ca-certificates/",
            "RUN update-ca-certificates",
        ),
        context_files=(
            ContextFile(path="corp.crt", content="PEM1"),
            ContextFile(path="partner.crt", content="PEM2"),
        ),
    )


def _mirror(apt: str | None = None, apk: str | None = None) -> ResolvedResource:
    return ResolvedResource(kind="packageMirror", name="corp", apt=apt, apk=apk)


def test_rewrite_resource_refs_one_mirror() -> None:
    p = RewritePackageSources.params_model(mirror="corp")
    assert RewritePackageSources().resource_refs(p) == (ResourceRef("packageMirror", "corp"),)


def test_rewrite_fragment_apt_and_apk() -> None:
    p = RewritePackageSources.params_model(mirror="corp")
    frag = RewritePackageSources().fragment(p, (_mirror(apt="https://m", apk="https://m"),))
    assert frag.context_files == ()
    (run,) = frag.instructions
    assert run.startswith("RUN set -eux; ")
    assert "/etc/apt/sources.list" in run
    assert "/etc/apt/sources.list.d/*.list" in run
    assert "/etc/apk/repositories" in run
    assert "s#https?://[^/]+#https://m#g" in run


def test_rewrite_fragment_apt_only_omits_apk() -> None:
    p = RewritePackageSources.params_model(mirror="corp")
    frag = RewritePackageSources().fragment(p, (_mirror(apt="https://m"),))
    (run,) = frag.instructions
    assert "/etc/apt/sources.list" in run
    assert "/etc/apk/repositories" not in run
