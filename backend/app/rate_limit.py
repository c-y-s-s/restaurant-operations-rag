from collections import defaultdict
from datetime import UTC, datetime
from threading import Lock


class DailyRateLimiter:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._counts: dict[tuple[str, str], int] = defaultdict(int)
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        today = datetime.now(UTC).date().isoformat()
        bucket = (today, key)
        with self._lock:
            self._counts[bucket] += 1
            count = self._counts[bucket]
            if len(self._counts) > 10_000:
                self._counts = defaultdict(
                    int, {item: value for item, value in self._counts.items() if item[0] == today}
                )
        return count <= self.limit, max(0, self.limit - count)
