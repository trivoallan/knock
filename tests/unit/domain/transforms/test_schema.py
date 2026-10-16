import json

from knock.domain.mirror_policy import mirror_policy_json_schema
from knock.domain.transforms.schema import transform_steps_schema


def test_transform_steps_schema_is_oneof_of_single_key_maps() -> None:
    schema = transform_steps_schema()
    branches = schema["oneOf"]
    keys = {next(iter(b["properties"])) for b in branches}
    assert keys == {"injectCA", "rewritePackageSources", "setTimezone", "upgradePackages"}
    for b in branches:
        assert b["additionalProperties"] is False
        assert len(b["required"]) == 1


def test_inject_ca_branch_constrains_certs() -> None:
    schema = transform_steps_schema()
    inject = next(b for b in schema["oneOf"] if "injectCA" in b["properties"])
    params = inject["properties"]["injectCA"]
    assert "certs" in params["properties"]


def test_mirror_policy_schema_embeds_the_oneof_and_serializes() -> None:
    schema = mirror_policy_json_schema()
    json.dumps(schema)  # still serializable
    assert schema["$defs"]["TransformStep"]["oneOf"]


def test_upgrade_packages_branch_takes_no_params() -> None:
    # A policy declares the step bare: its epoch comes with the plan's remediation order.
    schema = transform_steps_schema()
    upgrade = next(b for b in schema["oneOf"] if "upgradePackages" in b["properties"])
    params = upgrade["properties"]["upgradePackages"]
    assert params.get("properties", {}) == {}
    assert params["additionalProperties"] is False
