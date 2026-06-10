from datetime import UTC, datetime

from houba.domain.plan import ImportPlan, build_plan
from houba.domain.properties import parse_properties

YAML = """
source:
  registry: docker.io
  repository: library/busybox
destination:
  harbor: blue
  project: lib
  repository: busybox
flags:
  add_apt_repos: true
  update_keystore: true
  set_timezone: true
eol:
  product: busybox
"""


def test_build_plan_basic_fields() -> None:
    plan = build_plan(
        tag="1.36",
        properties=parse_properties(YAML),
        src_digest="sha256:abc",
        eol_date="2027-01-01",
        now=datetime(2026, 5, 21, tzinfo=UTC),
    )

    assert isinstance(plan, ImportPlan)
    assert plan.tag == "1.36"
    assert plan.src_image == "docker.io/library/busybox:1.36"
    assert plan.dst_image == "lib/busybox:1.36"
    assert plan.flags["add_apt_repos"] is True
    assert plan.flags["add_yum_repos"] is False
    assert plan.labels["io.houba.source.digest"] == "sha256:abc"
    assert plan.labels["io.houba.eol.date"] == "2027-01-01"


def test_build_plan_without_eol() -> None:
    yaml_no_eol = """
    source:
      registry: docker.io
      repository: library/busybox
    destination:
      harbor: blue
      project: lib
      repository: busybox
    """
    plan = build_plan(
        tag="1.36",
        properties=parse_properties(yaml_no_eol),
        src_digest="sha256:abc",
        eol_date=None,
        now=datetime(2026, 5, 21, tzinfo=UTC),
    )

    assert "io.houba.eol.product" not in plan.labels
    assert "io.houba.eol.date" not in plan.labels
