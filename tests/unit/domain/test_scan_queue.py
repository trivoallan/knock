from houba.domain.scan_queue import (
    classify_exception,
    classify_failure,
    coverage_gap,
    enqueue_refs,
    gap_by_owner,
    should_dead_letter,
)


def test_enqueue_refs_only_applied_ops_with_out_digest():
    report = {
        "policies": [
            {
                "targets": [
                    {
                        "dest_repo": "registry.example:5000/demo/busybox",
                        "variants": [
                            {
                                "operations": [
                                    {"applied": True, "out_digest": "sha256:aaa"},
                                    {"applied": True, "out_digest": None},  # planned only
                                    {"applied": False, "out_digest": "sha256:bbb"},  # failed
                                ]
                            }
                        ],
                    }
                ]
            }
        ]
    }
    # ref = dest_repo@out_digest (dest_repo is ALREADY host-qualified — do NOT re-prefix)
    assert enqueue_refs(report) == ["registry.example:5000/demo/busybox@sha256:aaa"]


def test_enqueue_refs_empty_report():
    assert enqueue_refs({}) == []
    assert enqueue_refs({"policies": []}) == []


def test_should_dead_letter_only_past_max():
    assert should_dead_letter(delivery_count=3, max_deliveries=3) is False
    assert should_dead_letter(delivery_count=4, max_deliveries=3) is True


def test_classify_failure_permanent_image_gone():
    f = classify_failure(stage="scan", exit_code=1, stderr="manifest unknown: 404 Not Found")
    assert f.kind == "permanent"
    assert "drop" in f.suggested_action.lower()


def test_classify_failure_transient_registry_5xx():
    f = classify_failure(stage="scan", exit_code=1, stderr="received unexpected HTTP status: 503")
    assert f.kind == "transient"
    assert "replay" in f.suggested_action.lower()


def test_classify_failure_signer_missing():
    f = classify_failure(stage="attach", exit_code=2, stderr="CosignError: no signer configured")
    assert f.kind == "transient"
    assert "HOUBA_ATTEST_SIGNER" in f.suggested_action


def test_coverage_gap_is_placed_minus_fresh_confirmed():
    placed = {"sha256:a", "sha256:b", "sha256:c"}
    fresh_confirmed = {"sha256:b"}
    assert sorted(coverage_gap(placed, fresh_confirmed)) == ["sha256:a", "sha256:c"]


def test_coverage_gap_empty_when_all_confirmed():
    assert coverage_gap({"sha256:a"}, {"sha256:a"}) == []


def test_gap_by_owner_counts_per_owner_ref():
    gap = ["sha256:a", "sha256:b", "sha256:c"]
    owners = {"sha256:a": "team-x", "sha256:b": "team-x", "sha256:c": "team-y"}
    assert gap_by_owner(gap, owners) == {"team-x": 2, "team-y": 1}


def test_gap_by_owner_unknown_owner_bucket():
    assert gap_by_owner(["sha256:z"], {}) == {"<unknown>": 1}


def test_classify_exception_signer_is_transient():
    f = classify_exception("attach", "CosignError", "no signer configured")
    assert f.kind == "transient"
    assert "signer" in f.suggested_action.lower()


def test_classify_exception_registry_404_is_permanent():
    f = classify_exception("attach", "RegctlError", "manifest unknown: 404")
    assert f.kind == "permanent"


def test_classify_exception_other_is_transient():
    f = classify_exception("attach", "RegctlError", "registry 503 service unavailable")
    assert f.kind == "transient"
