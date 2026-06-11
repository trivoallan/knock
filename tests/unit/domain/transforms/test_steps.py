from houba.domain.transforms.base import ContextFile, Fragment, ResolvedResource, ResourceRef
from houba.domain.transforms.steps import InjectCA


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
