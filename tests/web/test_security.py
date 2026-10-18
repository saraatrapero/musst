from __future__ import annotations

import pytest

from mus_web.security import (
    CredentialError,
    check_password,
    check_username,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    stored = hash_password("una contraseña", n=16)
    assert stored.startswith("scrypt$16$")
    assert verify_password("una contraseña", stored)
    assert not verify_password("otra", stored)


def test_same_password_gets_different_salts() -> None:
    assert hash_password("x" * 8, n=16) != hash_password("x" * 8, n=16)


@pytest.mark.parametrize("stored", ["", "scrypt$1$2", "bcrypt$16$8$1$aa$bb", "scrypt$16$8$1$zz$bb"])
def test_malformed_hashes_never_verify(stored: str) -> None:
    assert not verify_password("loquesea", stored)


def test_tokens_are_random_and_digested() -> None:
    a, b = new_token(), new_token()
    assert a != b
    assert len(token_digest(a)) == 64
    assert token_digest(a) != a


@pytest.mark.parametrize("name", ["sara", "Ana_99", "a.b-c"])
def test_valid_usernames(name: str) -> None:
    assert check_username(name) == name


@pytest.mark.parametrize("name", ["ab", "x" * 25, "con espacio", "<script>", 3, None])
def test_invalid_usernames(name: object) -> None:
    with pytest.raises(CredentialError):
        check_username(name)


def test_password_length() -> None:
    assert check_password("12345678") == "12345678"
    for bad in ("1234567", "x" * 129, None):
        with pytest.raises(CredentialError):
            check_password(bad)
