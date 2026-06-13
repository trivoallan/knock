from __future__ import annotations

from datetime import UTC, datetime

import pytest

from houba.config import RegistryConfig
from houba.domain.lifecycle import (
    PENDING_DELETION_ARTIFACT_TYPE,
    build_pending_deletion_annotations,
)
from houba.errors import ConfigError
from houba.ports.registry import ImageInfo, Referrer
from houba.use_cases.purge import purge_exit_code, purge_marks
from tests.fakes.registry import FakeRegistryPort
from tests.fakes.usage_oracle import FakeUsageOraclePort

NOW = datetime(2026, 6, 13, tzinfo=UTC)
_ROSTER = {"harbor": RegistryConfig(host="harbor.example")}


def _mark(tag: str) -> Referrer:
    return Referrer(
        digest=f"sha256:ref-{tag}",
        artifact_type=PENDING_DELETION_ARTIFACT_TYPE,
        annotations=build_pending_deletion_annotations(
            prefix="io.houba",
            marked_at=NOW,
            reason="dropped-from-selection",
            policy="redis",
            import_name="v7",
            variant="default",
        ),
        subject_tag=tag,
    )


def _registry(**kw: object) -> FakeRegistryPort:
    host = "harbor.example"
    repo = f"{host}/lib/redis"
    return FakeRegistryPort(
        repositories={host: ["lib/redis"]},
        tags={repo: ["7.1", "7.2"]},
        infos={
            f"{repo}:7.1": ImageInfo(digest="sha256:d71", created=None, annotations={}),
            f"{repo}:7.2": ImageInfo(digest="sha256:d72", created=None, annotations={}),
        },
        referrers={
            f"{repo}:7.1": [_mark("7.1")],
            f"{repo}:7.2": [_mark("7.2")],
        },
        **kw,
    )


def test_apply_purges_only_the_unused_tag_and_clears_its_mark() -> None:
    reg = _registry()
    oracle = FakeUsageOraclePort(
        last_seen={"sha256:d72": datetime(2026, 6, 8, tzinfo=UTC)}
    )
    report = purge_marks(
        registry=reg,
        oracle=oracle,
        roster=_ROSTER,
        only_registry=None,
        label_prefix="io.houba",
        min_idle_days=15,
        now=NOW,
        apply=True,
    )
    assert reg.deleted == ["harbor.example/lib/redis:7.1"]
    assert reg.unmarked == ["harbor.example/lib/redis@sha256:ref-7.1"]
    assert {o.image_ref: o.decision for o in report.outcomes} == {
        "harbor.example/lib/redis:7.1": "purge",
        "harbor.example/lib/redis:7.2": "protect",
    }
    assert purge_exit_code(report) == 0


def test_dry_run_mutates_nothing() -> None:
    reg = _registry()
    oracle = FakeUsageOraclePort(last_seen={})
    report = purge_marks(
        registry=reg,
        oracle=oracle,
        roster=_ROSTER,
        only_registry=None,
        label_prefix="io.houba",
        min_idle_days=15,
        now=NOW,
        apply=False,
    )
    assert reg.deleted == []
    assert reg.unmarked == []
    assert all(o.decision == "purge" and o.applied is False for o in report.outcomes)
    assert report.mode == "dry-run"


def test_oracle_error_is_fail_closed_protect_not_purge() -> None:
    reg = _registry()
    oracle = FakeUsageOraclePort(fail={"sha256:d71", "sha256:d72"})
    report = purge_marks(
        registry=reg,
        oracle=oracle,
        roster=_ROSTER,
        only_registry=None,
        label_prefix="io.houba",
        min_idle_days=15,
        now=NOW,
        apply=True,
    )
    assert reg.deleted == []
    assert all(o.decision == "uncertain" for o in report.outcomes)
    assert purge_exit_code(report) == 0


def test_delete_failure_is_recorded_and_reddens_exit() -> None:
    reg = _registry(fail_delete={"harbor.example/lib/redis:7.1"})
    oracle = FakeUsageOraclePort(last_seen={})
    report = purge_marks(
        registry=reg,
        oracle=oracle,
        roster=_ROSTER,
        only_registry=None,
        label_prefix="io.houba",
        min_idle_days=15,
        now=NOW,
        apply=True,
    )
    errs = [o for o in report.outcomes if o.error is not None]
    assert len(errs) == 1 and errs[0].image_ref == "harbor.example/lib/redis:7.1"
    assert "harbor.example/lib/redis:7.2" in reg.deleted
    assert purge_exit_code(report) == 2


def test_unknown_only_registry_raises_config_error() -> None:
    with pytest.raises(ConfigError):
        purge_marks(
            registry=_registry(),
            oracle=FakeUsageOraclePort(),
            roster=_ROSTER,
            only_registry="nope",
            label_prefix="io.houba",
            min_idle_days=15,
            now=NOW,
            apply=True,
        )
