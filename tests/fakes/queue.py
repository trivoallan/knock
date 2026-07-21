from __future__ import annotations

from knock.ports.queue import Reservation


class FakeQueuePort:
    """In-memory QueuePort fake that journals calls, for use-case tests."""

    def __init__(
        self,
        work: list[str] | None = None,
        placed: list[str] | None = None,
        confirmed: dict[str, float] | None = None,
    ) -> None:
        self._work = list(work or [])
        self.placed = list(placed or [])
        self.confirmed = dict(confirmed or {})
        self._n = 0
        self.acked: list[tuple[str, str]] = []
        self.dead_lettered: list[tuple[str, dict[str, str]]] = []
        self.reaped: list[str] = []
        self.enqueued: list[str] = []

    def enqueue(self, refs: list[str]) -> None:
        self._work.extend(refs)
        self.enqueued.extend(refs)

    def reserve(self) -> Reservation | None:
        if not self._work:
            return None
        ref = self._work.pop(0)
        self._n += 1
        return Reservation(token=f"t{self._n}", ref=ref)

    def ack(self, res: Reservation, *, digest: str, attested_at: str) -> None:
        self.acked.append((digest, attested_at))

    def dead_letter(self, res: Reservation, *, ref: str, reason: dict[str, str]) -> None:
        self.dead_lettered.append((ref, reason))

    def reaper(self, *, min_idle_ms: int, max_deliveries: int) -> list[str]:
        return self.reaped

    def coverage_check(self, placed: list[str], *, max_age_s: int, now: float) -> list[str]:
        fresh = {d for d, ts in self.confirmed.items() if ts >= now - max_age_s}
        return [p for p in placed if p not in fresh]

    def dlq_list(self) -> list[dict[str, str]]:
        return [{"ref": r, **reason} for r, reason in self.dead_lettered]

    def dlq_replay(self, selector: str) -> int:
        return 0

    def dlq_drop(self, selector: str) -> int:
        return 0
