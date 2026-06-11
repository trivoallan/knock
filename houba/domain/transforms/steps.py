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


class _RewritePackageSourcesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mirror: str = Field(min_length=1)


class RewritePackageSources(TransformStepCompiler[_RewritePackageSourcesParams]):
    name = "rewritePackageSources"
    params_model = _RewritePackageSourcesParams

    def resource_refs(self, params: _RewritePackageSourcesParams) -> tuple[ResourceRef, ...]:
        return (ResourceRef("packageMirror", params.mirror),)

    def fragment(
        self, params: _RewritePackageSourcesParams, resources: tuple[ResolvedResource, ...]
    ) -> Fragment:
        (m,) = resources
        rewrites: list[str] = []
        if m.apt:
            rewrites.append(
                f"if [ -f /etc/apt/sources.list ]; then "
                f"sed -ri 's#https?://[^/]+#{m.apt}#g' /etc/apt/sources.list; fi"
            )
            rewrites.append(
                f"if ls /etc/apt/sources.list.d/*.list >/dev/null 2>&1; then "
                f"sed -ri 's#https?://[^/]+#{m.apt}#g' /etc/apt/sources.list.d/*.list; fi"
            )
        if m.apk:
            rewrites.append(
                f"if [ -f /etc/apk/repositories ]; then "
                f"sed -ri 's#https?://[^/]+#{m.apk}#g' /etc/apk/repositories; fi"
            )
        instructions = ("RUN set -eux; " + "; ".join(rewrites),) if rewrites else ()
        return Fragment(instructions=instructions)


class _SetTimezoneParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    zone: str = Field(min_length=1)


class SetTimezone(TransformStepCompiler[_SetTimezoneParams]):
    name = "setTimezone"
    params_model = _SetTimezoneParams

    def fragment(
        self, params: _SetTimezoneParams, resources: tuple[ResolvedResource, ...]
    ) -> Fragment:
        z = params.zone
        return Fragment(
            instructions=(
                f"RUN ln -snf /usr/share/zoneinfo/{z} /etc/localtime && echo {z} > /etc/timezone",
                f"ENV TZ={z}",
            )
        )
