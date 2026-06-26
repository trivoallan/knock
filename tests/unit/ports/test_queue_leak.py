import inspect

from houba.ports.queue import QueuePort, Reservation

_BANNED = ("xadd", "xack", "xautoclaim", "xtrim", "stream", "msg_id", "redis")


def test_port_surface_is_broker_agnostic():
    """No QueuePort method name or parameter may leak Redis-Streams semantics.
    The stream id is wrapped in Reservation.token (opaque)."""
    for name, member in inspect.getmembers(QueuePort, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        assert not any(b in name.lower() for b in _BANNED), f"method {name} leaks broker"
        for param in inspect.signature(member).parameters:
            assert not any(b in param.lower() for b in _BANNED), f"{name}({param}) leaks broker"
    fields = set(Reservation.__dataclass_fields__)
    assert "msg_id" not in fields and "stream" not in fields
