from __future__ import annotations

import pytest

from houba.errors import EolSourceError
from houba.ports.eol_source import EolEntry
from tests.fakes.eol_source import FakeEolSourcePort


def test_fetch_returns_seeded() -> None:
    entries = [
        EolEntry(cycle="1.36", eol="2027-06-01", latest="1.36.1"),
        EolEntry(cycle="1.37", eol="2028-06-01", latest="1.37.0"),
    ]
    fake = FakeEolSourcePort(entries={"busybox": entries})
    assert fake.fetch_eol("busybox") == entries


def test_fetch_unknown_raises() -> None:
    fake = FakeEolSourcePort()
    with pytest.raises(EolSourceError):
        fake.fetch_eol("missing")
