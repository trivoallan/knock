from __future__ import annotations

import pytest
from pydantic import ValidationError

from knock.domain.gate import (
    Gate,
    PlannedOperation,
    ReconcilePlan,
    RemediationOrder,
    reconcile_plan_json_schema,
)


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
    assert op["properties"]["transformed"]["type"] == "boolean"
    assert "transformed" not in op["required"]  # a plan written before the field still loads


def test_a_plan_entry_says_whether_knock_rebuilds_it() -> None:
    assert _op().transformed is False
    built = _op().model_copy(update={"transformed": True})
    doc = ReconcilePlan(operations=[built]).model_dump(mode="json", by_alias=True)
    assert doc["operations"][0]["transformed"] is True
    assert ReconcilePlan.model_validate(doc).operations == [built]


def test_an_approval_is_not_bound_to_the_transformed_fact() -> None:
    built = _op().model_copy(update={"transformed": True})
    assert built.key() == _op().key()
    # an orchestrator may hand back a plan it stripped of the field: the digest is what binds
    assert Gate.from_plan(ReconcilePlan(operations=[_op()])).admits(built)


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


def test_only_a_remediation_is_staged() -> None:
    assert stages(remediated=True)
    # a copy is byte-identical to the judged source; a transform-only rebuild is not judged again
    assert not stages(remediated=False)


def test_a_remediation_order_is_outside_the_key_and_kept_by_the_gate() -> None:
    ordered = _op().model_copy(update={"remediate": RemediationOrder(epoch="20261016T020000Z")})
    assert ordered.key() == _op().key()
    gate = Gate.from_plan(ReconcilePlan(operations=[ordered]))
    assert gate.admits(_op())
    assert gate.order(_op()) is not None and gate.order(_op()).epoch == "20261016T020000Z"


def test_an_unordered_operation_has_no_order() -> None:
    gate = Gate.from_plan(ReconcilePlan(operations=[_op()]))
    assert gate.order(_op()) is None


@pytest.mark.parametrize("epoch", ["", "x; rm -rf /", "a b", "e\n", "x" * 65])
def test_an_unsafe_epoch_refuses_the_plan(epoch: str) -> None:
    with pytest.raises(ValidationError):
        ReconcilePlan.model_validate(
            {"operations": [{**_op().model_dump(by_alias=True), "remediate": {"epoch": epoch}}]}
        )


def test_plan_out_writes_no_order_and_no_remediated_flag_by_default() -> None:
    dumped = _op().model_dump(by_alias=True)
    assert dumped["remediate"] is None and dumped["remediated"] is False


def test_the_documented_staged_example_is_a_valid_document() -> None:
    from pathlib import Path

    doc = StagedRebuilds.model_validate_json(Path("docs/examples/gate/staged.json").read_text())
    [entry] = doc.entries
    assert entry.staged == staged_repository(
        entry.destination, destination_host="harbor.example", staging_host="staging.example"
    )
