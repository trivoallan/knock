from scripts.scan_queue import enqueue_refs


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
