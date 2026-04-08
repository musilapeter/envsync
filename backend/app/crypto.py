from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def derive_key(passphrase: str, project_id: str) -> bytes:
    """Derive a deterministic Fernet key from passphrase and project ID."""
    raw = f"{passphrase}:{project_id}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_env(plaintext: str, key: bytes) -> str:
    """Encrypt a .env payload into an opaque token."""
    fernet = Fernet(key)
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_env(ciphertext: str, key: bytes) -> str:
    """Decrypt an opaque token back into the original .env payload."""
    fernet = Fernet(key)
    return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
