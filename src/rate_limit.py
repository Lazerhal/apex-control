"""Limits failed logins per client address. Kept in memory: a restart clears it."""
import ipaddress
import math
import time
from collections import deque

from fastapi import Request

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60


class FailureLimiter:
    def __init__(self, limit: int = MAX_FAILURES, window: float = WINDOW_SECONDS,
                 clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._failures: dict[str, deque] = {}

    def retry_after(self, key: str) -> int:
        """Seconds until this key may try again; 0 if it may now."""
        times = self._recent(key)
        if len(times) < self.limit:
            return 0
        return max(1, math.ceil(times[0] + self.window - self.clock()))

    def record_failure(self, key: str) -> None:
        for other in list(self._failures):  # forget addresses with nothing recent
            self._recent(other)
        self._failures.setdefault(key, deque()).append(self.clock())

    def reset(self) -> None:
        self._failures.clear()

    def _recent(self, key: str) -> deque:
        times = self._failures.get(key)
        if times is None:
            return deque()
        while times and times[0] <= self.clock() - self.window:
            times.popleft()
        if not times:
            del self._failures[key]
        return times


def client_ip(request: Request) -> str:
    """The caller's address.

    Behind the tunnel or the dashboard proxy the connection comes from this machine, so the
    address Cloudflare reports is used then. It is ignored on any other connection.
    """
    peer = request.client.host if request.client else "unknown"
    try:
        if ipaddress.ip_address(peer).is_loopback:
            return str(ipaddress.ip_address(request.headers.get("cf-connecting-ip", "")))
    except ValueError:
        pass
    return peer


login_limiter = FailureLimiter()
