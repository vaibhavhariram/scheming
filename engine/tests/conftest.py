from datetime import datetime, timedelta, timezone

import pytest


class TickClock:
    """Deterministic clock: each call advances by `step` seconds."""

    def __init__(self, start: datetime | None = None, step: int = 1):
        self.t = start or datetime(2026, 9, 19, 11, 0, 0, tzinfo=timezone.utc)
        self.step = timedelta(seconds=step)

    def __call__(self) -> datetime:
        now = self.t
        self.t += self.step
        return now


@pytest.fixture
def clock():
    return TickClock()
