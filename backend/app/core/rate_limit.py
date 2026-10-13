# Talentum — backend/app/core/rate_limit.py
# Responsabilidade: Controla tentativas de login com Redis compartilhado ou memória local.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from collections import defaultdict, deque
import hashlib
import time
from threading import Lock
from uuid import uuid4

import redis


class LoginRateLimiter:
    """Limita tentativas de login com Redis ou contador local de contingência."""

    def __init__(self, attempts: int, window_seconds: int, redis_url: str | None = None, redis_required: bool = False) -> None:
        """Configura o máximo de falhas e o armazenamento compartilhado opcional."""
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.redis_required = redis_required  # Sem URL, a flag só é validada na configuração de produção (achado 132).
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True) if redis_url else None
        # O fallback expurga filas apenas quando a mesma chave volta a ser consultada;
        # chaves inativas permanecem no dicionário.
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        """Indica se a chave ainda pode tentar autenticar na janela atual."""
        if self._redis is not None:
            try:
                redis_key = self._redis_key(key)
                now = time.time()
                # Limpeza e contagem são comandos separados; tentativas concorrentes podem passar juntas.
                self._redis.zremrangebyscore(redis_key, 0, now - self.window_seconds)
                return int(self._redis.zcard(redis_key)) < self.attempts
            except redis.RedisError:
                if self.redis_required:
                    raise RuntimeError("Rate limit compartilhado indisponível")
                # Em modo opcional, a falha do Redis direciona esta decisão ao contador local.
                # Se a disponibilidade oscilar, este contador local não inclui os eventos mantidos no Redis.
        # Sem Redis disponível, o contador em memória limita somente este processo da API.
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            return len(events) < self.attempts

    def register_failure(self, key: str) -> None:
        """Registra uma tentativa inválida e remove eventos vencidos."""
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
                # Em modo opcional, registra a tentativa somente no contador deste processo.
                # Uma recuperação entre a consulta e o registro pode separar a contagem entre os dois armazenamentos.
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            events.append(now)

    def reset(self, key: str) -> None:
        """Limpa o histórico de falhas após uma autenticação válida."""
        if self._redis is not None:
            try:
                self._redis.delete(self._redis_key(key))
                return
            except redis.RedisError:
                if self.redis_required:
                    raise RuntimeError("Rate limit compartilhado indisponível")
                # A limpeza local não apaga o histórico Redis; ao recuperar, falhas antigas ainda bloqueiam o login (achado 161).
        with self._lock:
            self._events.pop(key, None)

    @staticmethod
    def _redis_key(key: str) -> str:
        """Oculta a chave de login ao montar o identificador usado no Redis."""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"talentum:login-rate:{digest}"
