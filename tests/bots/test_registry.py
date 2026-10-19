"""Descubrimiento de bots contribuidos (requisito 2.1)."""

import sys
import textwrap

import pytest

from mus_engine.bots import RandomBot, RegistryError, SimpleBot, all_bots
from mus_engine.bots.registry import discover_contrib


def test_builtin_bots() -> None:
    bots = all_bots()
    assert bots["aleatorio"] is RandomBot
    assert bots["sencillo"] is SimpleBot


def _package(tmp_path, monkeypatch, name: str, modules: dict[str, str]) -> str:  # type: ignore[no-untyped-def]
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    for module, code in modules.items():
        (root / f"{module}.py").write_text(textwrap.dedent(code), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return name


BOT_CODE = """
    from mus_engine.bots import Bot, RandomBot

    class {cls}(RandomBot):
        name = {name!r}
"""


def test_contributed_bot_is_discovered(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    package = _package(
        tmp_path,
        monkeypatch,
        "contrib_ok",
        {"equipo_x": BOT_CODE.format(cls="Listo", name="listo")},
    )
    found = discover_contrib(package)
    assert [cls.name for cls in found] == ["listo"]
    assert set(all_bots(package)) == {"aleatorio", "sencillo", "medio", "listo"}
    sys.modules.pop(f"{package}.equipo_x", None)


def test_duplicate_names_are_rejected(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    package = _package(
        tmp_path, monkeypatch, "contrib_dup", {"a": BOT_CODE.format(cls="Copia", name="sencillo")}
    )
    with pytest.raises(RegistryError, match="repetido"):
        all_bots(package)


def test_missing_name_is_rejected(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    code = """
        from mus_engine import PassAction
        from mus_engine.bots import Bot

        class SinNombre(Bot):
            def decide(self, observation):
                return PassAction()
    """
    package = _package(tmp_path, monkeypatch, "contrib_noname", {"b": code})
    with pytest.raises(RegistryError, match="name"):
        all_bots(package)


def test_contrib_package_exists_and_is_empty_by_default() -> None:
    assert discover_contrib() == ()
