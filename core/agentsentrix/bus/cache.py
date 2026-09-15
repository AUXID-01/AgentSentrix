import json
import time
import warnings
import logging
from typing import Any, Optional
import redis
from ..schema.events import RiskAssessment

logger = logging.getLogger("agentsentrix.cache")

class StateCache:
    """Cache and Quarantine State Store supporting Redis with in-memory fallback."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, socket_timeout: float = 2.0) -> None:
        self.host = host
        self.port = port
        self.db = db
        self.using_redis = False
        self._redis_client: Optional[redis.Redis] = None
        self._memory_store: dict[str, tuple[str, float]] = {}

        try:
            r = redis.Redis(host=self.host, port=self.port, db=self.db, socket_timeout=socket_timeout, decode_responses=True)
            if r.ping():
                self._redis_client = r
                self.using_redis = True
                logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as exc:
            warnings.warn(
                f"Redis connection failed ({self.host}:{self.port}): {exc}. Operating in fallback mode.",
                UserWarning
            )
            self.using_redis = False

    def is_redis_connected(self) -> bool:
        """Check if Redis connection is active."""
        if not self.using_redis or self._redis_client is None:
            return False
        try:
            return bool(self._redis_client.ping())
        except Exception:
            return False

    # --- Verdict Cache ---

    def set_verdict(self, action_hash: str, assessment: RiskAssessment | dict, ttl: int = 3600) -> None:
        """Store action_hash -> RiskAssessment with TTL."""
        key = f"verdict:{action_hash}"
        if isinstance(assessment, RiskAssessment):
            payload_str = assessment.model_dump_json()
        elif isinstance(assessment, dict):
            payload_str = json.dumps(assessment)
        else:
            payload_str = str(assessment)

        if self.using_redis and self._redis_client:
            self._redis_client.set(key, payload_str, ex=ttl)
        else:
            expire_at = time.time() + ttl
            self._memory_store[key] = (payload_str, expire_at)

    def get_verdict(self, action_hash: str) -> Optional[RiskAssessment]:
        """Retrieve cached RiskAssessment for action_hash."""
        key = f"verdict:{action_hash}"
        payload_str: Optional[str] = None

        if self.using_redis and self._redis_client:
            payload_str = self._redis_client.get(key)
        else:
            if key in self._memory_store:
                data, expire_at = self._memory_store[key]
                if time.time() < expire_at:
                    payload_str = data
                else:
                    del self._memory_store[key]

        if payload_str:
            try:
                data = json.loads(payload_str)
                return RiskAssessment.model_validate(data)
            except Exception as exc:
                logger.warning(f"Error deserializing cached verdict for {action_hash}: {exc}")
                return None
        return None

    # --- Quarantine Pending Store ---

    def set_quarantine(self, event_id: str, data: dict[str, Any], ttl: int = 86400) -> None:
        """Store event_id -> quarantine state dict (e.g. {"status": "quarantined", ...}) with TTL."""
        key = f"quarantine:{event_id}"
        payload_str = json.dumps(data)

        if self.using_redis and self._redis_client:
            self._redis_client.set(key, payload_str, ex=ttl)
        else:
            expire_at = time.time() + ttl
            self._memory_store[key] = (payload_str, expire_at)

    def get_quarantine(self, event_id: str) -> Optional[dict[str, Any]]:
        """Retrieve quarantine state for event_id."""
        key = f"quarantine:{event_id}"
        payload_str: Optional[str] = None

        if self.using_redis and self._redis_client:
            payload_str = self._redis_client.get(key)
        else:
            if key in self._memory_store:
                data, expire_at = self._memory_store[key]
                if time.time() < expire_at:
                    payload_str = data
                else:
                    del self._memory_store[key]

        if payload_str:
            try:
                return json.loads(payload_str)
            except Exception as exc:
                logger.warning(f"Error deserializing quarantine data for {event_id}: {exc}")
                return None
        return None
