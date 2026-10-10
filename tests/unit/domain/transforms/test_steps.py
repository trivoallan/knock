from knock.domain.transforms.base import ContextFile, Fragment, ResolvedResource, ResourceRef
from knock.domain.transforms.steps import (
    InjectCA,
    RewritePackageSources,
    SetTimezone,
    UpgradePackages,
)


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
    assert "/etc/apt/sources.list.d/*.sources" in run  # deb822 (Debian 12 / Ubuntu 24.04+)
    assert "/etc/apk/repositories" in run
    assert "s#https?://[^/]+#https://m#g" in run


def test_rewrite_fragment_deb822_uses_same_host_swap() -> None:
    # deb822 .sources carries the host in a plain `URIs:` URL, so the SAME host-swap sed
    # applies; it must be guarded like the *.list rewrite and reuse the apt mirror value.
    p = RewritePackageSources.params_model(mirror="corp")
    frag = RewritePackageSources().fragment(p, (_mirror(apt="https://m"),))
    (run,) = frag.instructions
    assert "ls /etc/apt/sources.list.d/*.sources" in run
    assert "sed -ri 's#https?://[^/]+#https://m#g' /etc/apt/sources.list.d/*.sources" in run


def test_rewrite_fragment_apt_only_omits_apk() -> None:
    p = RewritePackageSources.params_model(mirror="corp")
    frag = RewritePackageSources().fragment(p, (_mirror(apt="https://m"),))
    (run,) = frag.instructions
    assert "/etc/apt/sources.list" in run
    assert "/etc/apk/repositories" not in run


def test_set_timezone_has_no_resource_refs() -> None:
    p = SetTimezone.params_model(zone="Europe/Paris")
    assert SetTimezone().resource_refs(p) == ()


def test_set_timezone_fragment_is_pure_no_context() -> None:
    p = SetTimezone.params_model(zone="Europe/Paris")
    frag = SetTimezone().fragment(p, ())
    assert frag.context_files == ()
    assert frag.instructions == (
        "RUN ln -snf /usr/share/zoneinfo/Europe/Paris /etc/localtime "
        "&& echo Europe/Paris > /etc/timezone",
        "ENV TZ=Europe/Paris",
    )


def _upgrade_run(epoch: str = "2026-10-10") -> str:
    p = UpgradePackages.params_model(epoch=epoch)
    frag = UpgradePackages().fragment(p, ())
    assert frag.context_files == ()
    (run,) = frag.instructions  # one RUN: update and upgrade must share a layer
    return run


def test_upgrade_packages_needs_no_resources() -> None:
    p = UpgradePackages.params_model(epoch="2026-10-10")
    assert UpgradePackages().resource_refs(p) == ()


def test_upgrade_packages_is_one_run_with_the_epoch_marker() -> None:
    run = _upgrade_run("2026-10-10")
    assert run.startswith(
        "RUN --mount=type=cache,target=/var/cache/apt,sharing=locked set -eux; "
        ': "knock-upgrade-epoch=2026-10-10"; '
    )
    # A new epoch must change the instruction text, or BuildKit serves the cached layer.
    assert _upgrade_run("2026-10-11") != run


def test_upgrade_packages_apt_branch() -> None:
    run = _upgrade_run()
    apt = run[run.index("if command -v apt-get") : run.index("elif command -v apk")]
    assert "export DEBIAN_FRONTEND=noninteractive" in apt
    assert "apt-get update" in apt
    assert "apt-get -o APT::Get::Always-Include-Phased-Updates=true -y upgrade" in apt
    assert "rm -rf /var/lib/apt/lists/*" in apt
    # docker-clean would empty the cache mount: set aside for the upgrade, restored after it.
    aside = apt.index("mv /etc/apt/apt.conf.d/docker-clean /tmp/knock-docker-clean")
    upgrade = apt.index("-y upgrade")
    restore = apt.index("mv /tmp/knock-docker-clean /etc/apt/apt.conf.d/docker-clean")
    assert aside < upgrade < restore
    # The keep-cache snippet is knock's, and does not survive into the image.
    added = apt.index("> /etc/apt/apt.conf.d/knock-keep-cache")
    removed = apt.index("rm -f /etc/apt/apt.conf.d/knock-keep-cache")
    assert added < upgrade < removed


def test_upgrade_packages_apk_branch() -> None:
    run = _upgrade_run()
    apk = run[run.index("elif command -v apk") : run.index("else ")]
    assert "apk upgrade --no-cache" in apk


def test_upgrade_packages_fails_loudly_without_a_package_manager() -> None:
    run = _upgrade_run()
    assert run.endswith('else echo "upgradePackages: no apt-get or apk in image" >&2; exit 1; fi')


def test_upgrade_packages_never_emits_a_syntax_directive() -> None:
    # A `# syntax=` line would make buildkitd pull the frontend image from a public registry.
    assert "syntax=" not in _upgrade_run()
