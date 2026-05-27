#!/usr/bin/env python3
"""Generate a Fernet key to paste into .env for local encrypted storage."""

from cryptography.fernet import Fernet

print(Fernet.generate_key().decode("ascii"))
