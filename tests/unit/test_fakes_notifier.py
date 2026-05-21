from __future__ import annotations

import pytest

from houba.errors import AdapterError
from tests.fakes.notifier import FakeNotifierPort


def test_send_records_payload() -> None:
    fake = FakeNotifierPort()
    fake.send({"title": "ok", "items": [1, 2]})
    assert fake.payloads == [{"title": "ok", "items": [1, 2]}]


def test_send_when_failing_raises() -> None:
    fake = FakeNotifierPort(fail=True)
    with pytest.raises(AdapterError):
        fake.send({})
