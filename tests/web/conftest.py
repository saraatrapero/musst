"""Fixtures de la web: aplicación con base de datos en memoria y bots sin pausas.

Con ``MUSST_TEST_DATABASE_URL`` (p. ej. ``postgresql+psycopg://musst@127.0.0.1/musst``)
los tests usan esa base de datos, que se vacía al crear cada aplicación.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from mus_web.app import Settings, create_app
from mus_web.db import Base

TEST_DATABASE_URL = os.environ.get("MUSST_TEST_DATABASE_URL", "sqlite://")


def fast_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": TEST_DATABASE_URL,
        "bot_delay": 0.0,
        "hand_pause": 0.0,
        "tick_interval": 0.01,
        "password_n": 16,
        "seed_source": lambda: 7,
    }
    values.update(overrides)
    if values["database_url"] != "sqlite://":
        engine = create_engine(values["database_url"])
        Base.metadata.drop_all(engine)
        engine.dispose()
    return Settings(**values)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(fast_settings())) as test_client:
        yield test_client


def register(
    client: TestClient, username: str = "sara", avatar: str = "marquesa"
) -> dict[str, Any]:
    response = client.post(
        "/api/register",
        json={"username": username, "password": "contraseña1", "avatar": avatar, "consent": True},
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data
