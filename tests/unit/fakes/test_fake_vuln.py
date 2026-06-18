def test_fake_vuln_evaluator_journals_and_returns_seeded_sarif() -> None:
    from houba.ports.sbom import SbomDocument
    from tests.fakes.vuln import FakeVulnEvaluatorPort

    fake = FakeVulnEvaluatorPort(sarif=b'{"runs":[]}')
    doc = SbomDocument(format="spdx-json", media_type="application/spdx+json", content=b"{}")
    out = fake.evaluate(doc)
    assert out.sarif == b'{"runs":[]}'
    assert fake.evaluated == [doc]
