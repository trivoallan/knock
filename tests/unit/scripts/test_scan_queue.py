from scripts.scan_queue import classify_failure, enqueue_refs, should_dead_letter


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
