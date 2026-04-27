import asyncio
from datetime import datetime, timedelta
from enum import Enum


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class MLCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.state = State.CLOSED
        self.failures = 0
        self.threshold = failure_threshold
        self.last_failure = None
        self.timeout = recovery_timeout

    async def call(self, primary_fn, fallback_fn, *args, **kwargs):
        if self.state == State.OPEN:
            if (self.last_failure and
                    datetime.now() - self.last_failure > timedelta(seconds=self.timeout)):
                self.state = State.HALF_OPEN
            else:
                return await fallback_fn(*args, **kwargs)
        try:
            result = await primary_fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            return await fallback_fn(*args, **kwargs)

    def _on_failure(self):
        self.failures += 1
        self.last_failure = datetime.now()
        if self.failures >= self.threshold:
            self.state = State.OPEN

    def _on_success(self):
        self.failures = 0
        self.state = State.CLOSED
