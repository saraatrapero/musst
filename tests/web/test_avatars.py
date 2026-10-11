from __future__ import annotations

import copy
from typing import Any

import pytest

from mus_web.avatars_pack import MOMENTS, AvatarPackError, avatars_by_id, load_pack, parse_pack


def test_pack_has_the_eight_characters() -> None:
    notice, avatars = load_pack()
    assert "parodia" in notice
    assert [a.nickname for a in avatars] == [
        "La Marquesa",
        "El Tentador",
        "La Superviviente",
        "El Tronista",
        "La Abuela del Mus",
        "El Cantante de Verbena",
        "El Presentador",
        "La Influencer",
    ]
    for avatar in avatars:
        assert set(avatar.phrases) <= MOMENTS
        assert {"gana_lance", "pierde_lance", "gana_partida", "pierde_partida"} <= set(
            avatar.phrases
        )
        assert avatar.public() == {
            "id": avatar.id,
            "nickname": avatar.nickname,
            "style": avatar.style,
            "color": avatar.color,
        }
    assert set(avatars_by_id()) == {a.id for a in avatars}


def _valid() -> dict[str, Any]:
    return {
        "aviso": "parodia",
        "avatars": [
            {"id": "a", "nickname": "A", "style": "s", "color": "#000", "phrases": {"pasa": ["x"]}}
        ],
    }


def test_minimal_pack_parses() -> None:
    notice, (avatar,) = parse_pack(_valid())
    assert notice == "parodia"
    assert avatar.phrases == {"pasa": ("x",)}


def _broken(change: Any) -> dict[str, Any]:
    data = copy.deepcopy(_valid())
    change(data)
    return data


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"aviso": "x"},
        _broken(lambda d: d.pop("aviso")),
        _broken(lambda d: d.update(aviso="  ")),
        _broken(lambda d: d.update(avatars=[])),
        _broken(lambda d: d["avatars"].append("no")),
        _broken(lambda d: d["avatars"][0].pop("nickname")),
        _broken(lambda d: d["avatars"][0].update(color="")),
        _broken(lambda d: d["avatars"][0].update(phrases=[])),
        _broken(lambda d: d["avatars"][0]["phrases"].update(inventado=["x"])),
        _broken(lambda d: d["avatars"][0]["phrases"].update(pasa=[])),
        _broken(lambda d: d["avatars"][0]["phrases"].update(pasa="x")),
        _broken(lambda d: d["avatars"][0]["phrases"].update(pasa=[" "])),
        _broken(lambda d: d["avatars"].append(copy.deepcopy(d["avatars"][0]))),
    ],
)
def test_broken_packs_are_rejected(data: object) -> None:
    with pytest.raises(AvatarPackError):
        parse_pack(data)
