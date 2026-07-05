"""Vault lifecycle management: initialization, unlocking, and master key verification."""

import os
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app import crypto
from app.models import VaultConfig


# Sentinel plaintext for KEK verification
_SENTINEL = b"VAULTEC_OK"


def is_initialized(db: Session) -> bool:
    """
    Check if the vault has been initialized.

    Returns:
        True if a vault_config row exists, False otherwise.
    """
    config = db.query(VaultConfig).filter(VaultConfig.id == 1).first()
    return config is not None


def initialize(db: Session, passphrase: str) -> None:
    """
    Initialize the vault: generate salt, derive KEK, encrypt sentinel, store config.

    Must only be called once (raises if already initialized).

    Args:
        db: database session
        passphrase: master passphrase for vault

    Raises:
        ValueError: if vault is already initialized
    """
    if is_initialized(db):
        raise ValueError("Vault is already initialized")

    # Generate 16-byte salt
    salt = os.urandom(16)

    # Derive KEK from passphrase
    kek = crypto.derive_kek(passphrase, salt)

    # Generate random nonce for sentinel encryption
    nonce = os.urandom(12)

    # Encrypt sentinel with KEK using AES-256-GCM
    cipher = AESGCM(kek)
    ciphertext = cipher.encrypt(nonce, _SENTINEL, None)

    # Create and store vault_config row
    config = VaultConfig(
        id=1,
        kdf_salt=salt,
        kek_check_nonce=nonce,
        kek_check_ct=ciphertext,
    )
    db.add(config)
    db.commit()

    # Set KEK in memory
    crypto.set_master_key(kek)


def unlock(db: Session, passphrase: str) -> bool:
    """
    Unlock the vault: load salt, derive KEK, verify sentinel, set master key.

    Args:
        db: database session
        passphrase: master passphrase for vault

    Returns:
        True if passphrase is correct and vault unlocked, False otherwise.
        Does NOT set the master key if verification fails.
    """
    config = db.query(VaultConfig).filter(VaultConfig.id == 1).first()
    if config is None:
        return False

    try:
        # Derive KEK from passphrase and stored salt
        kek = crypto.derive_kek(passphrase, config.kdf_salt)

        # Decrypt sentinel with derived KEK
        cipher = AESGCM(kek)
        plaintext = cipher.decrypt(config.kek_check_nonce, config.kek_check_ct, None)

        # Verify sentinel matches
        if plaintext != _SENTINEL:
            return False

        # Set KEK in memory
        crypto.set_master_key(kek)
        return True
    except Exception:
        # Decryption failed (wrong passphrase)
        return False
