from collections import defaultdict, deque
import hashlib
import time
from threading import Lock
from uuid import uuid4

import redis


class LoginRateLimiter:
    """Small process-local guard for credential stuffing during local deployment.

    Production deployments with more than one API worker should put this counter
    behind a shared store such as Redis; the application remains safe by default
    for the single-process and Docker setups used by the MVP.
    """

    def __init__(self, attempts: int, window_seconds: int, redis_url: str | None = None, redis_required: bool = False) -> None:
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.redis_required = redis_required
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True) if redis_url else None
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        if self._redis is not None:
            try:
                redis_key = self._redis_key(key)
                now = time.time()
                self._redis.zremrangebyscore(redis_key, 0, now - self.window_seconds)
                return int(self._redis.zcard(redis_key)) < self.attempts
            except redis.RedisError:
                if self.redis_required:
                    raise RuntimeError("Rate limit compartilhado indisponível")
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            return len(events) < self.attempts

    def register_failure(self, key: str) -> None:
        if self._redis is not None:
            try:
                redis_key = self._redis_key(key)
                now = time.time()
                self._redis.zadd(redis_key, {f"{now}:{uuid4().hex}": now})
                self._redis.expire(redis_key, self.window_seconds + 5)
                return
            except redis.RedisError:
                if self.redis_required:
                    raise RuntimeError("Rate limit compartilhado indisponível")
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            events.append(now)

    def reset(self, key: str) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(self._redis_key(key))
                return
            except redis.RedisError:
                if self.redis_required:
                    raise RuntimeError("Rate limit compartilhado indisponível")
        with self._lock:
            self._events.pop(key, None)

    @staticmethod
    def _redis_key(key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"talentum:login-rate:{digest}"
