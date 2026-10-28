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
from typing import Tuple, Dict, Any, Optional

PBKDF2_ITERATIONS = 600_000
PBKDF2_HASH_ALGO = "sha256"


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

    def is_rate_limited(self, key: str) -> Tuple[bool, int]:
        """
        Returns (is_limited, seconds_remaining).
        """
        now = time.time()
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
        with self._lock:
            attempts = self._failed_attempts.get(key, [])
            attempts.append(now)
            self._failed_attempts[key] = attempts

    def reset(self, key: str):
        with self._lock:
            if key in self._failed_attempts:
                del self._failed_attempts[key]


# Global rate limiter instance
auth_rate_limiter = LoginRateLimiter(max_attempts=5, window_seconds=900)
