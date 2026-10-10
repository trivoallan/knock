"""The built-in transform-step vocabulary. Each step is a pure compiler."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from knock.domain.transforms.base import (
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
            # deb822 (Debian 12 / Ubuntu 24.04+): the host lives in the `URIs:` field as a
            # plain URL, so the same host-swap sed applies; `Signed-By:` is a path, not http(s).
            rewrites.append(
                f"if ls /etc/apt/sources.list.d/*.sources >/dev/null 2>&1; then "
                f"sed -ri 's#https?://[^/]+#{m.apt}#g' /etc/apt/sources.list.d/*.sources; fi"
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


# `epoch` is interpolated into a RUN instruction, so it is a trust boundary: nothing outside
# this alphabet is ever rendered.
_EPOCH_PATTERN = r"^[A-Za-z0-9._-]{1,64}$"

_DOCKER_CLEAN = "/etc/apt/apt.conf.d/docker-clean"
_DOCKER_CLEAN_ASIDE = "/tmp/knock-docker-clean"  # noqa: S108 — a path inside the build, not ours
_KEEP_CACHE = "/etc/apt/apt.conf.d/knock-keep-cache"


class _UpgradePackagesParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    epoch: str = Field(pattern=_EPOCH_PATTERN)


class UpgradePackages(TransformStepCompiler[_UpgradePackagesParams]):
    """Upgrade every installed OS package from the repositories the image points at.

    The policy must run `rewritePackageSources` first (enforced at validation), so those
    repositories are the internal mirror. `epoch` is the operator's trigger: it takes part in
    the transform version, and it is written into the RUN text so the layer cache cannot serve
    a previous upgrade.
    """

    name = "upgradePackages"
    params_model = _UpgradePackagesParams

    def fragment(
        self, params: _UpgradePackagesParams, resources: tuple[ResolvedResource, ...]
    ) -> Fragment:
        apt = "; ".join(
            (
                "export DEBIAN_FRONTEND=noninteractive",
                # Official Debian/Ubuntu images delete downloaded .deb files after each
                # install, which would empty the shared cache mount. Set that aside for the
                # upgrade and put it back, so the image keeps its own apt configuration.
                f"if [ -f {_DOCKER_CLEAN} ]; then mv {_DOCKER_CLEAN} {_DOCKER_CLEAN_ASIDE}; fi",
                f"echo 'Binary::apt::APT::Keep-Downloaded-Packages \"true\";' > {_KEEP_CACHE}",
                # `apt-get update` exits 0 when a repository cannot be reached, and the
                # upgrade then finds nothing to do: the build would succeed with nothing
                # upgraded. Error-Mode=any makes any fetch failure fatal. Some older apt
                # releases ignore the option (Debian 10's does), so also start from no index
                # and require one afterwards.
                "rm -rf /var/lib/apt/lists/*",
                "apt-get -o APT::Update::Error-Mode=any update",
                "ls /var/lib/apt/lists/*Release >/dev/null 2>&1 || "
                '{ echo "upgradePackages: no package index fetched" >&2; exit 1; }',
                # Ubuntu holds some fixes back as phased updates; a repair must not skip them.
                # The option is ignored on Debian.
                "apt-get -o APT::Get::Always-Include-Phased-Updates=true -y upgrade",
                f"rm -f {_KEEP_CACHE}",
                f"if [ -f {_DOCKER_CLEAN_ASIDE} ]; then "
                f"mv {_DOCKER_CLEAN_ASIDE} {_DOCKER_CLEAN}; fi",
                "rm -rf /var/lib/apt/lists/*",
            )
        )
        run = (
            "RUN --mount=type=cache,target=/var/cache/apt,sharing=locked set -eux; "
            f': "knock-upgrade-epoch={params.epoch}"; '
            f"if command -v apt-get >/dev/null 2>&1; then {apt}; "
            "elif command -v apk >/dev/null 2>&1; then apk upgrade --no-cache; "
            # Closed vocabulary: an image this step cannot upgrade fails the build, so the
            # signed lineage never claims an upgrade that did not happen.
            'else echo "upgradePackages: no apt-get or apk in image" >&2; exit 1; fi'
        )
        return Fragment(instructions=(run,))
