"""Base de datos (SQLAlchemy 2): usuarios, sesiones y partidas terminadas.

PostgreSQL en producción (``MUSST_DATABASE_URL``) y SQLite en desarrollo y tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    avatar_id: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    consent_at: Mapped[datetime] = mapped_column(default=utcnow)
    games_played: Mapped[int] = mapped_column(default=0)
    games_won: Mapped[int] = mapped_column(default=0)

    sessions: Mapped[list[LoginSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    seats: Mapped[list[GameSeat]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class LoginSession(Base):
    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]

    user: Mapped[User] = relationship(back_populates="sessions")


class GameRow(Base):
    """Una partida terminada: el registro permite reproducirla entera."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    finished_at: Mapped[datetime] = mapped_column(default=utcnow)
    mode: Mapped[str] = mapped_column(String(20))
    signals: Mapped[bool]
    winner_team: Mapped[str | None] = mapped_column(String(1))
    final_tantos: Mapped[list[int]] = mapped_column(JSON)
    final_games: Mapped[list[int]] = mapped_column(JSON)
    record: Mapped[dict[str, Any]] = mapped_column(JSON)

    seats: Mapped[list[GameSeat]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class GameSeat(Base):
    """Quién ocupó cada asiento (un usuario o un bot)."""

    __tablename__ = "game_seats"

    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), primary_key=True)
    seat: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    bot: Mapped[str | None] = mapped_column(String(40))
    avatar_id: Mapped[str] = mapped_column(String(40))
    won: Mapped[bool]

    game: Mapped[GameRow] = relationship(back_populates="seats")
    user: Mapped[User | None] = relationship(back_populates="seats")


class Database:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite"):
            memory = url in ("sqlite://", "sqlite:///:memory:")
            self.engine: Engine = create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool if memory else None,
            )
            event.listen(self.engine, "connect", _sqlite_foreign_keys)
        else:  # pragma: no cover - PostgreSQL sólo en producción
            self.engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            yield session


def _sqlite_foreign_keys(connection: Any, _record: Any) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
