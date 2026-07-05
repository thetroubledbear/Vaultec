"""
Envelope encryption core: AES-256-GCM with per-file DEK wrapped by master KEK.
Master KEK derived via Argon2id from user passphrase.
"""

import base64
import hashlib
import os
from typing import Optional

from argon2.low_level import hash_secret_raw, Type, ARGON2_VERSION
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# Module-level KEK holder (memory-only)
_master_key: Optional[bytes] = None


def set_master_key(key: bytes) -> None:
    """Set the master KEK in memory. Must be 32 bytes."""
    global _master_key
    if len(key) != 32:
        raise ValueError("Master key must be 32 bytes")
    _master_key = key


def get_master_key() -> bytes:
    """Get the master KEK. Raises if not yet unlocked."""
    if _master_key is None:
        raise RuntimeError("Vault is locked; KEK not set")
    return _master_key


def is_unlocked() -> bool:
    """Check if vault is unlocked (KEK in memory)."""
    return _master_key is not None


def lock() -> None:
    """Lock the vault: clear the master KEK from memory."""
    global _master_key
    _master_key = None


def derive_kek(passphrase: str, salt: bytes) -> bytes:
    """
    Derive a 32-byte master KEK using Argon2id.

    Args:
        passphrase: user's master passphrase
        salt: 16+ byte salt (recommend 16)

    Returns:
        32-byte derived key
    """
    if len(salt) < 16:
        raise ValueError("Salt must be at least 16 bytes")

    # Argon2id: high security defaults
    # time_cost=2, parallelism=1, memory_cost=65536 (64 MB)
    # hash_secret_raw returns the raw derived key bytes (not the encoded string form).
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=2,
        memory_cost=65536,
        parallelism=1,
        hash_len=32,
        type=Type.ID,
        version=ARGON2_VERSION,
    )


def encrypt_blob(plaintext: bytes) -> dict:
    """
    Encrypt a blob using envelope encryption.

    1. Generate random 32-byte DEK
    2. AES-256-GCM encrypt plaintext with DEK
    3. AES-256-GCM wrap DEK with master KEK
    4. Return dict with base64-encoded fields

    Args:
        plaintext: bytes to encrypt

    Returns:
        dict with keys: wrapped_dek, dek_nonce, blob_nonce, ciphertext, plaintext_sha256
    """
    # Generate random DEK and nonces
    dek = os.urandom(32)
    dek_nonce = os.urandom(12)
    blob_nonce = os.urandom(12)

    # Encrypt plaintext with DEK
    blob_cipher = AESGCM(dek)
    ciphertext = blob_cipher.encrypt(blob_nonce, plaintext, None)

    # Wrap DEK with master KEK
    kek = get_master_key()
    kek_cipher = AESGCM(kek)
    wrapped_dek = kek_cipher.encrypt(dek_nonce, dek, None)

    # Compute plaintext hash
    plaintext_sha256 = hashlib.sha256(plaintext).digest()

    return {
        "wrapped_dek": base64.b64encode(wrapped_dek).decode("ascii"),
        "dek_nonce": base64.b64encode(dek_nonce).decode("ascii"),
        "blob_nonce": base64.b64encode(blob_nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "plaintext_sha256": base64.b64encode(plaintext_sha256).decode("ascii"),
    }


def decrypt_blob(
    wrapped_dek: str,
    dek_nonce: str,
    blob_nonce: str,
    ciphertext: str,
    plaintext_sha256: str = None,
) -> bytes:
    """
    Decrypt a blob using envelope encryption (inverse of encrypt_blob).

    Args:
        wrapped_dek: base64-encoded wrapped DEK
        dek_nonce: base64-encoded DEK nonce
        blob_nonce: base64-encoded blob nonce
        ciphertext: base64-encoded ciphertext
        plaintext_sha256: optional base64-encoded expected SHA256 for verification

    Returns:
        decrypted plaintext bytes

    Raises:
        ValueError: if decryption fails or hash verification fails
    """
    # Decode from base64
    wrapped_dek_bytes = base64.b64decode(wrapped_dek)
    dek_nonce_bytes = base64.b64decode(dek_nonce)
    blob_nonce_bytes = base64.b64decode(blob_nonce)
    ciphertext_bytes = base64.b64decode(ciphertext)

    # Unwrap DEK with master KEK
    kek = get_master_key()
    kek_cipher = AESGCM(kek)
    try:
        dek = kek_cipher.decrypt(dek_nonce_bytes, wrapped_dek_bytes, None)
    except Exception as e:
        raise ValueError("Failed to unwrap DEK") from e

    # Decrypt plaintext with DEK
    blob_cipher = AESGCM(dek)
    try:
        plaintext = blob_cipher.decrypt(blob_nonce_bytes, ciphertext_bytes, None)
    except Exception as e:
        raise ValueError("Failed to decrypt blob") from e

    # Verify hash if provided
    if plaintext_sha256 is not None:
        computed_hash = hashlib.sha256(plaintext).digest()
        expected_hash = base64.b64decode(plaintext_sha256)
        if computed_hash != expected_hash:
            raise ValueError("Plaintext hash mismatch")

    return plaintext
