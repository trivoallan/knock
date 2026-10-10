"""`knock promote`: place what a filtered staged rebuilds file still names, and nothing else."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from knock.config import RegistryConfig
from knock.domain.attestation import COSIGN_ATTESTATION_ARTIFACT_TYPE
from knock.domain.gate import StagedEntry, StagedRebuilds
from knock.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from knock.domain.sbom import media_type_for
from knock.errors import ConfigError
from knock.ports.registry import ImageInfo, Referrer
from knock.use_cases.promote import promote_staged
from knock.use_cases.report import Operation, RunReport, report_exit_code
from tests.fakes.attestor import FakeAttestor
from tests.fakes.registry import FakeRegistryPort
from tests.fakes.reporter import FakeReporter

NOW = datetime(2026, 6, 11, tzinfo=UTC)
SRC = "docker.io/library/busybox"
DEST = "reg.local/demo/busybox"
STAGED = "stage.local/demo/busybox"
ROSTER = {
    "local": RegistryConfig(host="reg.local"),
    "stage": RegistryConfig(host="stage.local", tls_verify=False),
}
SPDX = media_type_for("spdx-json")

POLICY = """
apiVersion: knock.io/v1alpha1
kind: MirrorPolicy
metadata: { name: busybox }
spec:
  artifactType: image
  admit: {admit}
  source: { registry: docker.io, repository: library/busybox }
  imports:
    - name: stable
      tags: { includeRegex: "^1\\\\.3[67]\\\\.0$", aliases: ["1"] }
      transform: [ { setTimezone: { zone: UTC } } ]
      destinations: [{ registry: local, project: demo, repository: busybox }]
"""


def _policy(admit: bool = False) -> MirrorPolicy:
    return parse_mirror_policy(POLICY.replace("{admit}", str(admit).lower()))


def _digest(tag: str) -> str:
    return f"sha256:staged-{tag}"


def _entry(tag: str = "1.37.0", **over: object) -> StagedEntry:
    fields: dict[str, object] = dict(
        policy="busybox",
        variant="default",
        kind="import",
        destination=DEST,
        tag=tag,
        source=SRC,
        sourceTag=tag,
        sourceDigest=f"sha256:src-{tag}",
        staged=STAGED,
        stagedDigest=_digest(tag),
        aliases=["1"] if tag == "1.37.0" else [],
    )
    fields["import"] = "stable"
    fields.update(over)
    return StagedEntry.model_validate(fields)


def _stamp(tag: str, **over: str) -> dict[str, str]:
    stamp = {
        "org.opencontainers.image.base.digest": f"sha256:src-{tag}",
        "io.knock.policy": "busybox",
        "io.knock.import": "stable",
        "io.knock.variant": "default",
    }
    stamp.update(over)
    return stamp


def _evidence(tag: str) -> list[Referrer]:
    return [
        Referrer(digest="sha256:sbom", artifact_type=SPDX, annotations={}, subject_tag=tag),
        Referrer(
            digest="sha256:att",
            artifact_type=COSIGN_ATTESTATION_ARTIFACT_TYPE,
            annotations={},
            subject_tag=tag,
        ),
    ]


def _registry(
    *tags: str,
    placed: dict[str, str] | None = None,
    stamps: dict[str, dict[str, str]] | None = None,
    staged_digests: dict[str, str] | None = None,
    **fake: object,
) -> FakeRegistryPort:
    """The staging registry holds `tags`, stamped and with their evidence; `placed` maps a
    destination tag to the digest it already resolves to."""
    tags = tags or ("1.37.0",)
    infos: dict[str, ImageInfo] = {}
    referrers: dict[str, list[Referrer]] = {}
    for tag in tags:
        stamp = (stamps or {}).get(tag, _stamp(tag))
        digest = (staged_digests or {}).get(tag, _digest(tag))
        info = ImageInfo(digest=digest, created=NOW, annotations=stamp)
        infos[f"{STAGED}:{tag}"] = info
        infos[f"{STAGED}@{digest}"] = info
        referrers[f"{STAGED}@{digest}"] = _evidence(tag)
    for tag, digest in (placed or {}).items():
        infos[f"{DEST}:{tag}"] = ImageInfo(digest=digest, created=NOW, annotations={})
    return FakeRegistryPort(
        tags={DEST: list(placed or {})},
        infos=infos,
        referrers=referrers,
        **fake,  # type: ignore[arg-type]
    )


def _attestor(**over: object) -> FakeAttestor:
    return FakeAttestor(**over)  # type: ignore[arg-type]


def _promote(
    registry: FakeRegistryPort,
    *entries: StagedEntry,
    policy: MirrorPolicy | None = None,
    **over: object,
) -> RunReport:
    kwargs: dict[str, object] = dict(
        registry=registry,
        roster=ROSTER,
        label_prefix="io.knock",
        sbom_formats=["spdx-json"],
        attestor=_attestor(),
        reporter=FakeReporter(),
    )
    kwargs.update(over)
    return promote_staged(
        StagedRebuilds(entries=list(entries)),
        [policy or _policy()],
        **kwargs,  # type: ignore[arg-type]
    )


def _ops(report: RunReport) -> list[Operation]:
    return [
        op for p in report.policies for t in p.targets for v in t.variants for op in v.operations
    ]


def _error(report: RunReport) -> str:
    [op] = [op for op in _ops(report) if op.error is not None]
    assert op.error is not None
    return f"{op.error.type}: {op.error.message}"


D37 = _digest("1.37.0")
BY_DIGEST = (f"{STAGED}@{D37}", f"{DEST}@{D37}")
TAG_WRITE = (f"{DEST}@{D37}", f"{DEST}:1.37.0")
ALIAS_WRITE = (f"{DEST}:1.37.0", f"{DEST}:1")


def test_an_entry_is_copied_by_digest_verified_then_tagged_then_aliased() -> None:
    registry, attestor = _registry(), _attestor()
    report = _promote(registry, _entry(), attestor=attestor)

    assert registry.copied == [BY_DIGEST, TAG_WRITE, ALIAS_WRITE]
    assert registry.copied_with_referrers == [BY_DIGEST]  # only the first carries evidence
    assert attestor.attested_checks == [
        (f"{DEST}@{D37}", "https://knock.dev/predicate/transform/v1")
    ]
    assert [op.kind for op in _ops(report)] == ["imported", "aliased"]
    assert _ops(report)[0].out_digest == D37
    assert report.status == "ok" and report_exit_code(report) == 0
    assert (report.totals.imported, report.totals.aliased) == (1, 1)


@pytest.mark.parametrize("kind", ["update", "rebuild"])
def test_an_update_or_a_rebuild_is_reported_as_updated(kind: str) -> None:
    report = _promote(_registry(), _entry(kind=kind))
    assert _ops(report)[0].kind == "updated"


def test_an_admitting_policy_is_signed_after_the_tag_is_written() -> None:
    registry, attestor = _registry(), _attestor()
    _promote(registry, _entry(), policy=_policy(admit=True), attestor=attestor)
    assert attestor.signed == [f"{DEST}@{D37}"]


def test_a_non_admitting_policy_is_not_signed() -> None:
    attestor = _attestor()
    _promote(_registry(), _entry(), attestor=attestor)
    assert attestor.signed == []


def test_an_admitting_policy_without_a_signer_is_refused_before_anything_is_placed() -> None:
    registry = _registry()
    with pytest.raises(ConfigError, match="admit"):
        _promote(registry, _entry(), policy=_policy(admit=True), attestor=None)
    assert registry.copied == []


def test_without_a_signer_the_sbom_referrers_are_still_required() -> None:
    registry = _registry()
    report = _promote(registry, _entry(), attestor=None)
    assert report.status == "ok" and TAG_WRITE in registry.copied

    lost = _registry(lose_referrers=True)
    report = _promote(lost, _entry(), attestor=None)
    assert "PromotionRefusedError" in _error(report) and TAG_WRITE not in lost.copied


def test_promoting_twice_changes_nothing() -> None:
    registry = _registry(placed={"1.37.0": D37, "1": D37})
    attestor = _attestor(image_signed=True)
    report = _promote(registry, _entry(), policy=_policy(admit=True), attestor=attestor)

    assert report.status == "ok" and report_exit_code(report) == 0
    assert registry.copied_with_referrers == [] and TAG_WRITE not in registry.copied
    assert attestor.signed == []  # already signed: not signed again
    assert _ops(report)[0].kind == "skipped"


def test_an_empty_file_places_nothing() -> None:
    registry = _registry()
    report = _promote(registry)
    assert report.status == "ok" and report_exit_code(report) == 0
    assert registry.copied == []


# --- an entry promote cannot trust ---


def _refused(registry: FakeRegistryPort, entry: StagedEntry, **over: object) -> str:
    report = _promote(registry, entry, **over)
    assert report_exit_code(report) != 0
    # nothing reached the destination tag, and no alias was written
    assert TAG_WRITE not in registry.copied and ALIAS_WRITE not in registry.copied
    return _error(report)


def test_refuses_an_unknown_policy() -> None:
    assert "no policy named 'other'" in _refused(_registry(), _entry(policy="other"))


def test_refuses_a_destination_the_policy_does_not_declare() -> None:
    registry = _registry()
    error = _refused(registry, _entry(destination="reg.local/elsewhere/busybox"))
    assert "does not declare" in error and registry.copied == []


@pytest.mark.parametrize(
    "staged",
    [
        "evil.example/demo/busybox",  # a registry outside the roster
        "stage.local/other/busybox",  # the staging registry, another path
        DEST,  # the destination itself is not a staging location
    ],
)
def test_refuses_a_staged_reference_outside_the_staging_registry(staged: str) -> None:
    registry = _registry()
    error = _refused(registry, _entry(staged=staged))
    assert "PromotionRefusedError" in error and registry.copied == []


def test_refuses_a_staged_digest_that_changed() -> None:
    registry = _registry(staged_digests={"1.37.0": "sha256:rebuilt-since"})
    error = _refused(registry, _entry())
    assert "StagedDigestMismatchError" in error
    assert D37 in error and "sha256:rebuilt-since" in error
    assert registry.copied == []


def test_refuses_a_staged_image_that_is_gone() -> None:
    registry = _registry(fail_inspect={f"{STAGED}:1.37.0"})
    assert "RegctlError" in _refused(registry, _entry())


@pytest.mark.parametrize(
    "stamp",
    [
        {"io.knock.policy": "other"},
        {"io.knock.import": "other"},
        {"io.knock.variant": "other"},
        {"org.opencontainers.image.base.digest": "sha256:another-source"},
    ],
)
def test_refuses_a_stamp_that_names_another_entry(stamp: dict[str, str]) -> None:
    registry = _registry(stamps={"1.37.0": _stamp("1.37.0", **stamp)})
    error = _refused(registry, _entry())
    assert "stamp" in error and registry.copied == []


def test_refuses_when_the_copy_lost_the_referrers() -> None:
    registry = _registry(lose_referrers=True)
    error = _refused(registry, _entry())
    assert "did not arrive" in error and BY_DIGEST in registry.copied


def test_refuses_when_the_attestation_does_not_verify_at_the_destination() -> None:
    error = _refused(_registry(), _entry(), attestor=_attestor(attestation_verifies=False))
    assert "attestation" in error


def test_refuses_an_alias_the_policy_does_not_declare() -> None:
    registry = _registry()
    error = _refused(registry, _entry(aliases=["latest"]))
    assert "alias 'latest'" in error and registry.copied == []


def test_refuses_a_tag_the_import_does_not_select() -> None:
    registry = _registry("9.9.9")
    error = _refused(registry, _entry("9.9.9"))
    assert "does not select" in error and registry.copied == []


def test_one_refused_entry_does_not_stop_the_others() -> None:
    registry = _registry(
        "1.36.0", "1.37.0", stamps={"1.36.0": _stamp("1.36.0", **{"io.knock.policy": "x"})}
    )
    report = _promote(registry, _entry("1.36.0"), _entry("1.37.0"))
    assert report.status == "partial" and report_exit_code(report) == 1
    assert TAG_WRITE in registry.copied
    assert (report.totals.imported, report.totals.failed) == (1, 1)


def test_an_alias_of_a_removed_entry_is_not_written() -> None:
    # 1.37.0 (which carries alias "1") was removed from the file; promoting 1.36.0 moves nothing
    registry = _registry("1.36.0", placed={"1": "sha256:older"})
    report = _promote(registry, _entry("1.36.0"))
    assert report.status == "ok"
    assert not any(dst == f"{DEST}:1" for _src, dst in registry.copied)


def test_entries_run_through_an_executor_keep_their_order() -> None:
    registry = _registry("1.36.0", "1.37.0")
    report = _promote(registry, _entry("1.36.0"), _entry("1.37.0"), max_concurrency=4)
    assert [op.out_tag for op in _ops(report) if op.kind == "imported"] == ["1.36.0", "1.37.0"]
    assert report.status == "ok"
