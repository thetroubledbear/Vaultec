"""Password hashing and session token utilities."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Argon2id hasher with secure defaults
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.

    Args:
        password: plaintext password

    Returns:
        hashed password string
    """
    return _hasher.hash(password)


def verify_password(password: str, hash_str: str) -> bool:
    """
    Verify a password against an Argon2id hash.

    Args:
        password: plaintext password to verify
        hash_str: stored hash

    Returns:
        True if password matches, False otherwise
    """
    try:
        _hasher.verify(hash_str, password)
        return True
    except VerifyMismatchError:
        return False


def create_session_token() -> str:
    """
    Create a cryptographically random session token.

    Returns:
        URL-safe base64-encoded token
    """
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    Hash a session token using SHA256.

    Args:
        token: plaintext token

    Returns:
        hex-encoded SHA256 hash
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
