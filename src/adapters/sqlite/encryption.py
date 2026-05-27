"""Fernet encryption used for local sensitive text fields."""

import hashlib

from cryptography.fernet import Fernet


class FieldCipher:
    def __init__(self, key: str) -> None:
        if key.startswith("<"):
            raise ValueError("Genera FIELD_ENCRYPTION_KEY antes de iniciar la aplicacion.")
        self._fernet = Fernet(key.encode("ascii"))

    def encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode("utf-8"))

    def decrypt(self, value: bytes) -> str:
        return self._fernet.decrypt(value).decode("utf-8")


def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
