"""The built-in transform-step vocabulary. Each step is a pure compiler."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from houba.domain.transforms.base import (
    ContextFile,
    Fragment,
    ResolvedResource,
    ResourceRef,
    TransformStepCompiler,
)

CA_DIR = "/usr/local/share/ca-certificates"


class _InjectCAParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    certs: list[str] = Field(min_length=1)


class InjectCA(TransformStepCompiler[_InjectCAParams]):
    name = "injectCA"
    params_model = _InjectCAParams

    def resource_refs(self, params: _InjectCAParams) -> tuple[ResourceRef, ...]:
        return tuple(ResourceRef("caCert", c) for c in params.certs)

    def fragment(
        self, params: _InjectCAParams, resources: tuple[ResolvedResource, ...]
    ) -> Fragment:
        files: list[ContextFile] = []
        names: list[str] = []
        for r in resources:
            assert r.filename is not None and r.content is not None  # caCert always resolves both
            files.append(ContextFile(path=r.filename, content=r.content))
            names.append(r.filename)
        return Fragment(
            instructions=(
                f"COPY {' '.join(names)} {CA_DIR}/",
                "RUN update-ca-certificates",
            ),
            context_files=tuple(files),
        )
