from __future__ import annotations

import pytest
from pydantic import ValidationError

from knock.domain.gate import Gate, PlannedOperation, ReconcilePlan, reconcile_plan_json_schema


def _op(**over: str) -> PlannedOperation:
    fields = dict(
        policy="redis",
        kind="update",
        destination="harbor.corp/hub/redis",
        tag="7.2.5",
        source="docker.io/library/redis",
        sourceTag="7.2.5",
        sourceDigest="sha256:a",
    )
    fields.update(over)
    return PlannedOperation.model_validate(fields)


def test_plan_round_trips_through_its_camel_case_json() -> None:
    plan = ReconcilePlan(operations=[_op()])
    doc = plan.model_dump(mode="json", by_alias=True)
    assert doc["apiVersion"] == "knock.io/v1alpha1"
    assert doc["kind"] == "ReconcilePlan"
    assert doc["operations"][0]["sourceDigest"] == "sha256:a"
    assert ReconcilePlan.model_validate(doc) == plan


def test_plan_refuses_unknown_kind_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _op(kind="delete")
    with pytest.raises(ValidationError):
        _op(verdict="pass")


def test_recording_gate_admits_everything_and_records_it() -> None:
    gate = Gate()
    assert gate.admits(_op())
    assert gate.planned == [_op()]


def test_filtered_gate_admits_only_an_exact_match() -> None:
    gate = Gate.from_plan(ReconcilePlan(operations=[_op()]))
    assert gate.admits(_op())
    assert not gate.admits(_op(sourceDigest="sha256:b"))  # upstream moved since the plan
    assert not gate.admits(_op(kind="rebuild"))
    assert not gate.admits(_op(policy="other"))
    assert not gate.admits(_op(destination="harbor.corp/hub/other"))
    assert not gate.admits(_op(tag="7.2.6"))
    assert gate.planned == []  # a filtered gate applies; it does not record


def test_schema_is_derived_from_the_model() -> None:
    schema = reconcile_plan_json_schema()
    op = schema["$defs"]["PlannedOperation"]
    assert set(op["properties"]["kind"]["enum"]) == {"import", "update", "rebuild"}
    assert "sourceDigest" in op["required"]


# --- the second seam: staged rebuilds ---

from knock.domain.gate import (  # noqa: E402
    StagedEntry,
    StagedRebuilds,
    staged_rebuilds_json_schema,
    staged_repository,
    stages,
)


def _entry(**over: object) -> StagedEntry:
    fields: dict[str, object] = dict(
        policy="redis",
        kind="import",
        destination="harbor.corp/hub/redis",
        tag="7.2.5",
        source="docker.io/library/redis",
        sourceTag="7.2.5",
        sourceDigest="sha256:a",
        variant="default",
        staged="stage.local:5000/hub/redis",
        stagedDigest="sha256:b",
        aliases=["7.2"],
    )
    fields["import"] = "v7"
    fields.update(over)
    return StagedEntry.model_validate(fields)


def test_staged_rebuilds_round_trip_through_camel_case_json() -> None:
    doc = StagedRebuilds(entries=[_entry()]).model_dump(mode="json", by_alias=True)
    assert doc["apiVersion"] == "knock.io/v1alpha1"
    assert doc["kind"] == "StagedRebuilds"
    entry = doc["entries"][0]
    assert entry["import"] == "v7"
    assert entry["stagedDigest"] == "sha256:b"
    assert entry["aliases"] == ["7.2"]
    assert StagedRebuilds.model_validate(doc) == StagedRebuilds(entries=[_entry()])


def test_staged_entry_refuses_unknown_kind_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _entry(kind="delete")
    with pytest.raises(ValidationError):
        _entry(verdict="pass")


def test_staged_entry_aliases_default_to_none() -> None:
    fields = _entry().model_dump(by_alias=True)
    del fields["aliases"]
    assert StagedEntry.model_validate(fields).aliases == ()


def test_staged_schema_is_derived_from_the_model() -> None:
    entry = staged_rebuilds_json_schema()["$defs"]["StagedEntry"]
    assert {"import", "staged", "stagedDigest", "sourceDigest"} <= set(entry["required"])
    assert "aliases" not in entry["required"]


@pytest.mark.parametrize(
    ("destination", "host", "staging", "expected"),
    [
        ("harbor.corp/hub/redis", "harbor.corp", "stage:5000", "stage:5000/hub/redis"),
        # two destinations of one policy keep distinct staged repositories
        ("harbor.corp/team/redis", "harbor.corp", "stage:5000", "stage:5000/team/redis"),
        ("reg:5000/hub/a/b", "reg:5000", "stage", "stage/hub/a/b"),
    ],
)
def test_staged_repository_re_roots_the_destination(
    destination: str, host: str, staging: str, expected: str
) -> None:
    assert staged_repository(destination, destination_host=host, staging_host=staging) == expected


def test_staged_repository_refuses_a_destination_outside_its_host() -> None:
    with pytest.raises(ValueError, match="not under"):
        staged_repository("other.corp/hub/redis", destination_host="harbor.corp", staging_host="s")


def test_only_an_operation_that_builds_is_staged() -> None:
    assert stages(transformed=True)
    assert not stages(transformed=False)  # a copy is byte-identical to the judged source


def test_the_documented_staged_example_is_a_valid_document() -> None:
    from pathlib import Path

    doc = StagedRebuilds.model_validate_json(Path("docs/examples/gate/staged.json").read_text())
    [entry] = doc.entries
    assert entry.staged == staged_repository(
        entry.destination, destination_host="harbor.example", staging_host="staging.example"
    )
