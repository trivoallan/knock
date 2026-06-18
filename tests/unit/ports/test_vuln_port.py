def test_scan_result_carries_sarif_and_optional_db_version() -> None:
    from houba.ports.vuln import ScanResult

    r = ScanResult(sarif=b"{}")
    assert r.sarif == b"{}"
    assert r.db_version is None
    assert ScanResult(sarif=b"{}", db_version="v6.1.7").db_version == "v6.1.7"
