"""
Cryptographic Security, Password Hashing, and Rate Limiting for ZYROX AI SaaS Platform.
Standards:
- NIST & OWASP recommended PBKDF2-HMAC-SHA256 with 600,000 iterations.
- 128-bit cryptographic salts (secrets.token_hex(16)).
- Constant-time comparison (hmac.compare_digest) to prevent timing attacks.
- SHA-256 session token hashing to protect database dumps from credential exposure.
"""

import time
import hmac
import hashlib
import secrets
import threading
import logging
import os
import hashlib
from typing import Tuple, Dict, Any, Optional

PBKDF2_ITERATIONS = 600_000
PBKDF2_HASH_ALGO = "sha256"
logger = logging.getLogger("taikry.saas.security")


def hash_password(password: str) -> Tuple[str, str]:
    """
    Hashes a password with PBKDF2-HMAC-SHA256 and a cryptographically random salt.
    Returns (hashed_hex, salt_hex).
    """
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    salt = secrets.token_hex(16)
    salt_bytes = bytes.fromhex(salt)
    key = hashlib.pbkdf2_hmac(
        PBKDF2_HASH_ALGO,
        password.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS
    )
    return key.hex(), salt


def verify_password(password: str, hashed_hex: str, salt_hex: str) -> bool:
    """
    Verifies a password against the stored hash and salt using constant-time comparison.
    """
    try:
        salt_bytes = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(hashed_hex)
        candidate_key = hashlib.pbkdf2_hmac(
            PBKDF2_HASH_ALGO,
            password.encode("utf-8"),
            salt_bytes,
            PBKDF2_ITERATIONS
        )
        return hmac.compare_digest(candidate_key, expected_key)
    except Exception:
        return False


def generate_session_token() -> Tuple[str, str]:
    """
    Generates a 256-bit secure session token for the client,
    and returns (raw_token, sha256_hash_for_db).
    The raw token is only sent to the client (cookie/header); the DB only stores the hash.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a session or verification token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


class LoginRateLimiter:
    """
    Thread-safe in-memory rate limiter for authentication abuse protection.
    Limits failed login attempts per key (e.g. IP or email) to prevent brute-force attacks.
    """
    def __init__(self, max_attempts: int = 5, window_seconds: int = 900):
        self._lock = threading.Lock()
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        # key -> [timestamps of failed attempts]
        self._failed_attempts: Dict[str, list] = {}
        self._redis_client = None
        self._redis_retry_after = 0.0

    def _redis(self):
        """Use Redis when configured and reachable; keep local fallback available."""
        if os.getenv("AUTH_RATE_LIMIT_BACKEND", "auto").strip().lower() == "memory":
            return None
        if time.monotonic() < self._redis_retry_after:
            return None
        if self._redis_client is not None:
            return self._redis_client
        try:
            from redis import Redis
            from taikry.config import REDIS_URL
            client = Redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
                health_check_interval=30,
            )
            client.ping()
            self._redis_client = client
            return client
        except Exception as exc:
            self._redis_retry_after = time.monotonic() + 60.0
            logger.warning("Shared auth rate limit is unavailable; using process-local fallback (%s).", type(exc).__name__)
            return None

    @staticmethod
    def _redis_key(key: str) -> str:
        key_hash = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
        return f"taikry:auth:failed:{key_hash}"

    def is_rate_limited(self, key: str) -> Tuple[bool, int]:
        """
        Returns (is_limited, seconds_remaining).
        """
        now = time.time()
        client = self._redis()
        if client is not None:
            redis_key = self._redis_key(key)
            try:
                client.zremrangebyscore(redis_key, "-inf", now - self.window_seconds)
                attempts = int(client.zcard(redis_key))
                if attempts >= self.max_attempts:
                    oldest = client.zrange(redis_key, 0, 0, withscores=True)
                    seconds_remaining = int(self.window_seconds - (now - oldest[0][1])) if oldest else 1
                    return True, max(1, seconds_remaining)
                return False, 0
            except Exception as exc:
                self._redis_client = None
                self._redis_retry_after = time.monotonic() + 60.0
                logger.warning("Shared auth rate limit failed; using process-local fallback (%s).", type(exc).__name__)
        with self._lock:
            attempts = self._failed_attempts.get(key, [])
            # prune old attempts
            valid_attempts = [t for t in attempts if (now - t) < self.window_seconds]
            self._failed_attempts[key] = valid_attempts

            if len(valid_attempts) >= self.max_attempts:
                oldest = valid_attempts[0]
                seconds_remaining = int(self.window_seconds - (now - oldest))
                return True, max(1, seconds_remaining)
            return False, 0

    def record_failure(self, key: str):
        now = time.time()
        client = self._redis()
        if client is not None:
            try:
                redis_key = self._redis_key(key)
                client.zadd(redis_key, {secrets.token_urlsafe(12): now})
                client.expire(redis_key, self.window_seconds + 60)
                return
            except Exception as exc:
                self._redis_client = None
                self._redis_retry_after = time.monotonic() + 60.0
                logger.warning("Shared auth rate limit failed; using process-local fallback (%s).", type(exc).__name__)
        with self._lock:
            attempts = self._failed_attempts.get(key, [])
            attempts.append(now)
            self._failed_attempts[key] = attempts

    def reset(self, key: str):
        client = self._redis()
        if client is not None:
            try:
                client.delete(self._redis_key(key))
            except Exception as exc:
                self._redis_client = None
                self._redis_retry_after = time.monotonic() + 60.0
                logger.warning("Shared auth rate limit reset failed (%s).", type(exc).__name__)
        with self._lock:
            if key in self._failed_attempts:
                del self._failed_attempts[key]


# Global rate limiter instance
auth_rate_limiter = LoginRateLimiter(max_attempts=5, window_seconds=900)

