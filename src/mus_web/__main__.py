"""``python -m mus_web``: arranca el servidor (variables ``HOST``, ``PORT``)."""

from __future__ import annotations

import os

import uvicorn

from mus_web.app import Settings, create_app


def main() -> None:  # pragma: no cover - arranque del servidor
    uvicorn.run(
        create_app(Settings.from_env()),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        proxy_headers=True,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
