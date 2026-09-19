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
