"""Contraseñas, sesiones y validación de credenciales.

- Contraseñas con ``scrypt`` (biblioteca estándar) y sal aleatoria por usuario.
- Las sesiones son tokens aleatorios; en la base de datos sólo se guarda su SHA-256, de
  modo que una copia de la base de datos no permite suplantar a nadie.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
MIN_PASSWORD = 8
MAX_PASSWORD = 128


class CredentialError(ValueError):
    """Nombre de usuario o contraseña con formato no válido."""


def hash_password(password: str, *, n: int = SCRYPT_N) -> str:
    """``scrypt$n$r$p$sal$clave`` (hexadecimal)."""
    salt = secrets.token_bytes(SALT_BYTES)
    key = hashlib.scrypt(password.encode(), salt=salt, n=n, r=SCRYPT_R, p=SCRYPT_P, dklen=KEY_BYTES)
    return f"scrypt${n}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(key)
        actual = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_username(username: object) -> str:
    if not isinstance(username, str) or not USERNAME_RE.fullmatch(username):
        raise CredentialError(
            "El usuario debe tener entre 3 y 24 caracteres: letras, números, '_', '.' o '-'"
        )
    return username


def check_password(password: object) -> str:
    if not isinstance(password, str) or not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise CredentialError(
            f"La contraseña debe tener entre {MIN_PASSWORD} y {MAX_PASSWORD} caracteres"
        )
    return password
