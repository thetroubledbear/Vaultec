"""Content-addressed encrypted blob storage helper."""

import base64
import os
from pathlib import Path

from app.config import get_settings


def store_blob(enc: dict) -> str:
    """
    Store encrypted blob using content-addressing (plaintext SHA256).

    Args:
        enc: dict with keys {wrapped_dek, dek_nonce, blob_nonce, ciphertext, plaintext_sha256}
             where ciphertext and plaintext_sha256 are base64-encoded

    Returns:
        relative storage path as string (e.g. "ab/cd/abcd1234...enc")

    Raises:
        ValueError: if base64 decoding fails
    """
    settings = get_settings()

    # Decode plaintext_sha256 (base64) to bytes, then hex
    try:
        sha256_bytes = base64.b64decode(enc["plaintext_sha256"])
    except Exception as e:
        raise ValueError("Failed to decode plaintext_sha256 from base64") from e

    sha256_hex = sha256_bytes.hex()

    # Construct path: <hex[0:2]>/<hex[2:4]>/<hex>.enc
    subdir1 = sha256_hex[0:2]
    subdir2 = sha256_hex[2:4]
    filename = f"{sha256_hex}.enc"

    storage_path = os.path.join(subdir1, subdir2, filename)
    full_path = os.path.join(settings.vault_blob_dir, storage_path)

    # Ensure directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    # Decode ciphertext from base64
    try:
        ciphertext_bytes = base64.b64decode(enc["ciphertext"])
    except Exception as e:
        raise ValueError("Failed to decode ciphertext from base64") from e

    # Write only if file doesn't exist (dedup)
    if not os.path.exists(full_path):
        with open(full_path, "wb") as f:
            f.write(ciphertext_bytes)

    return storage_path


def read_blob(storage_path: str) -> bytes:
    """
    Read raw ciphertext bytes from vault blob storage.

    Args:
        storage_path: relative path under vault_blob_dir (e.g. "ab/cd/abcd1234...enc")

    Returns:
        raw ciphertext bytes

    Raises:
        FileNotFoundError: if blob file doesn't exist
    """
    settings = get_settings()
    full_path = os.path.join(settings.vault_blob_dir, storage_path)

    with open(full_path, "rb") as f:
        return f.read()
