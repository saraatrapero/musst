"""Campeonatos: inscripción, cuadro, partidos de personas y de bots, y administración."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mus_web import championships as rules
from mus_web.app import create_app
from mus_web.db import Championship, ChampMatch, ChampTeam

from .conftest import fast_settings, register
from .test_app import play_over_socket

LATER = (datetime.now(UTC) + timedelta(days=3)).isoformat()


def admin_client() -> TestClient:
    return TestClient(create_app(fast_settings(admins=frozenset({"sara"}))))


def login(client: TestClient, username: str) -> None:
    client.post("/api/logout")
    body = {"username": username, "password": "contraseña1"}
    assert client.post("/api/login", json=body).status_code == 200


def new_championship(client: TestClient, **extra: Any) -> dict[str, Any]:
    body = {"name": "Copa de Otoño", "starts_at": LATER, "size": 8} | extra
    response = client.post("/api/admin/championships", json=body)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


def hub_of(client: TestClient) -> Any:
    return client.app.state.hub  # type: ignore[attr-defined]


# --- Reglas del cuadro (sin web) --------------------------------------------------------------


def test_round_names() -> None:
    assert [rules.round_name(8, r) for r in (1, 2, 3)] == [
        "Cuartos de final",
        "Semifinales",
        "Final",
    ]
    assert rules.round_name(16, 1) == "Octavos de final"
    assert rules.round_name(32, 1) == "Ronda 1"
    assert rules.round_count(32) == 5


def test_simulated_match_is_reproducible() -> None:
    first = rules.simulate(30, 11)
    assert first == rules.simulate(30, 11)
    winner, score = first
    assert max(score) >= 30
    assert score[winner] == max(score)


def test_bot_seats_and_avatars() -> None:
    a = ChampTeam(id=1, name="A", captain_id=5, partner_id=None, bot_avatars=["x"])
    b = ChampTeam(id=2, name="B", captain_id=None, partner_id=None, bot_avatars=["y", "z"])
    c = ChampTeam(id=3, name="C", captain_id=6, partner_id=7, bot_avatars=["w"])
    teams = {1: a, 2: b, 3: c}
    match = ChampMatch(round=1, slot=0, team_a_id=1, team_b_id=2)
    assert rules.seats_for(match, teams) == {5: 0}
    assert rules.bot_avatars_for(match, teams) == {2: "x", 1: "y", 3: "z"}
    match = ChampMatch(round=1, slot=0, team_a_id=3, team_b_id=1)
    assert rules.seats_for(match, teams) == {6: 0, 7: 2, 5: 1}
    assert rules.bot_avatars_for(match, teams) == {3: "x"}


def test_due_needs_date_and_teams() -> None:
    champ = Championship(name="x", starts_at=datetime(2026, 1, 1), size=8, status="inscripcion")
    champ.teams = []
    assert not rules.due(champ, datetime(2026, 2, 1))
    champ.teams = [ChampTeam(name="A", captain_id=1, bot_avatars=["x"])]
    assert rules.due(champ, datetime(2026, 2, 1))
    assert not rules.due(champ, datetime(2025, 12, 1))


def test_bot_team_names_are_enough_and_unique() -> None:
    assert len(set(rules.BOT_TEAM_NAMES)) == len(rules.BOT_TEAM_NAMES) >= 31


# --- Administración ---------------------------------------------------------------------------


def test_only_admins_create_and_validation() -> None:
    with admin_client() as client:
        register(client, "pepe")
        body: dict[str, object] = {"name": "Copa", "starts_at": LATER}
        assert client.post("/api/admin/championships", json=body).status_code == 403
        login_new = register(client, "sara")
        assert login_new["admin"] is True
        bads: list[dict[str, object]] = [
            {"name": " "},
            {"name": "x" * 61},
            {"size": 4},
            {"size": 12},
            {"target": 35},
        ]
        for bad in bads:
            assert client.post("/api/admin/championships", json=body | bad).status_code == 422
        naive = body | {"starts_at": "2030-05-01T18:00:00"}
        champ = client.post("/api/admin/championships", json=naive).json()
        assert champ["starts_at"] == "2030-05-01T18:00:00"
        madrid = body | {"starts_at": "2030-05-01T20:00:00+02:00"}
        assert client.post("/api/admin/championships", json=madrid).json()["starts_at"] == (
            "2030-05-01T18:00:00"
        )
        detail = new_championship(client, size=16, target=30, signals=True)
        assert detail["status"] == "inscripcion"
        assert [r["name"] for r in detail["rounds"]] == [
            "Octavos de final",
            "Cuartos de final",
            "Semifinales",
            "Final",
        ]
        assert all(r["matches"] == [] for r in detail["rounds"])
        assert len(client.get("/api/championships").json()) == 3
        assert client.delete(f"/api/admin/championships/{detail['id']}").json() == {"ok": True}
        assert client.get(f"/api/championships/{detail['id']}").status_code == 404
        assert client.delete("/api/admin/championships/999").status_code == 404


# --- Inscripción ------------------------------------------------------------------------------


def test_sign_up_join_and_leave() -> None:
    with admin_client() as client:
        for name in ("pepe", "lucia", "andres"):
            register(client, name)
        register(client, "sara")
        champ = new_championship(client)
        url = f"/api/championships/{champ['id']}"
        login(client, "pepe")
        assert (
            client.post(f"{url}/teams", json={"team_name": "x", "partner": "?"}).status_code == 422
        )
        bad_avatar = {"team_name": "x", "bot_avatar": "nadie"}
        assert client.post(f"{url}/teams", json=bad_avatar).status_code == 422
        assert client.post(f"{url}/teams", json={"team_name": "  "}).status_code == 409
        mine = {"team_name": "Los de Pepe", "partner": "persona"}
        detail = client.post(f"{url}/teams", json=mine).json()
        assert detail["signed_up"] is True
        (team,) = detail["team_list"]
        assert team["players"] == ["pepe"]
        assert team["partner_open"] is True
        assert client.post(f"{url}/teams", json=mine | {"team_name": "Otra"}).status_code == 409
        login(client, "lucia")
        same = {"team_name": "los de pepe"}
        assert client.post(f"{url}/teams", json=same).status_code == 409
        assert client.post(f"{url}/leave").status_code == 409  # no está apuntada
        joined = client.post(f"{url}/teams/{team['id']}/join").json()
        assert joined["team_list"][0]["players"] == ["pepe", "lucia"]
        assert joined["team_list"][0]["partner_open"] is False
        assert client.post(f"{url}/teams/{team['id']}/join").status_code == 409
        login(client, "andres")
        assert client.post(f"{url}/teams/{team['id']}/join").status_code == 409  # ya completa
        assert client.post(f"{url}/teams/999/join").status_code == 409
        with_bot = {"team_name": "Andrés y su bot", "bot_avatar": "verbena"}
        own = client.post(f"{url}/teams", json=with_bot).json()
        assert own["team_list"][1]["bot_avatars"] == ["verbena"]
        assert client.post(f"{url}/teams/{team['id']}/join").status_code == 409  # ya apuntado
        assert len(client.post(f"{url}/leave").json()["team_list"]) == 1
        login(client, "lucia")  # la compañera se va: queda la plaza libre
        left = client.post(f"{url}/leave").json()["team_list"][0]
        assert left["players"] == ["pepe"]
        assert left["partner_open"] is True
        login(client, "pepe")  # quien apuntó la pareja se va: se va la pareja
        assert client.post(f"{url}/leave").json()["team_list"] == []
        assert client.get("/api/championships").json()[0]["signed_up"] is False


def test_championship_full() -> None:
    with admin_client() as client:
        register(client, "sara")
        champ = new_championship(client)
        db = hub_of(client).db
        with db.session() as session:
            row = session.get(Championship, champ["id"])
            for k in range(8):
                row.teams.append(ChampTeam(name=f"P{k}", captain_id=None, bot_avatars=[]))
        full = client.post(f"/api/championships/{champ['id']}/teams", json={"team_name": "Yo"})
        assert full.status_code == 409


# --- Cuadro y partidos ------------------------------------------------------------------------


def my_match(detail: dict[str, Any]) -> dict[str, Any]:
    return next(m for r in detail["rounds"] for m in r["matches"] if m["mine"] and m["ready"])


def test_bracket_with_one_person_reaches_the_final() -> None:
    with admin_client() as client:
        register(client, "sara")
        champ = new_championship(client, target=30)
        url = f"/api/championships/{champ['id']}"
        assert client.post(f"/api/admin/championships/{champ['id']}/start").status_code == 409
        client.post(f"{url}/teams", json={"team_name": "Las de Sara"})
        assert client.post("/api/admin/championships/999/start").status_code == 404
        detail = client.post(f"/api/admin/championships/{champ['id']}/start").json()
        assert detail["status"] == "en_juego"
        assert len(detail["team_list"]) == 8
        assert sum(t["bot"] for t in detail["team_list"]) == 7
        assert client.post(f"/api/admin/championships/{champ['id']}/start").status_code == 409
        assert client.post(f"{url}/teams", json={"team_name": "Tarde"}).status_code == 409
        quarters = detail["rounds"][0]["matches"]
        assert sum(m["winner_team_id"] is not None for m in quarters) == 3  # los de bots
        rounds_played = 0
        while detail["status"] == "en_juego":
            match = my_match(detail)
            room = client.post(f"{url}/matches/{match['id']}/play").json()
            assert room["mode"] == "campeonato"
            assert len(room["human_seats"]) == 1  # pareja A en 0 y 2, pareja B en 1 y 3
            assert "Las de Sara" in room["team_names"]
            again = client.post(f"{url}/matches/{match['id']}/play").json()
            assert again["code"] == room["code"]  # la misma mesa
            client.post(f"/api/rooms/{room['code']}/start")
            play_over_socket(client, room["code"], seed=rounds_played)
            hub = hub_of(client)
            hub.save(hub.rooms[room["code"]])
            detail = client.get(url).json()
            played = next(
                m for r in detail["rounds"] for m in r["matches"] if m["id"] == match["id"]
            )
            assert played["winner_team_id"] is not None
            assert max(played["score"]) >= 30
            rounds_played += 1
            mine = detail["my_team_id"]
            if played["winner_team_id"] != mine:
                break
        assert 1 <= rounds_played <= 3
        final = detail["rounds"][-1]["matches"][0]
        assert final["winner_team_id"] is not None
        assert detail["status"] == "terminado"
        assert detail["champion"] is not None
        listed = client.get("/api/championships").json()[0]
        assert listed["champion"] == detail["champion"]


def test_play_errors_and_walkover() -> None:
    with admin_client() as client:
        register(client, "pepe")
        register(client, "sara")
        champ = new_championship(client)
        url = f"/api/championships/{champ['id']}"
        client.post(f"{url}/teams", json={"team_name": "Sara"})
        login(client, "pepe")
        client.post(f"{url}/teams", json={"team_name": "Pepe"})
        login(client, "sara")
        detail = client.post(f"/api/admin/championships/{champ['id']}/start").json()
        assert client.post(f"{url}/matches/999/play").status_code == 409
        sara_match = my_match(detail)
        later = detail["rounds"][1]["matches"][0]
        assert client.post(f"{url}/matches/{later['id']}/play").status_code == 409
        others = [
            m
            for m in detail["rounds"][0]["matches"]
            if m["ready"] and not m["mine"] and m["id"] != sara_match["id"]
        ]
        if others:  # el de Pepe (si no les ha tocado jugar entre ellos)
            assert client.post(f"{url}/matches/{others[0]['id']}/play").status_code == 403
        win = f"/api/admin/championships/{champ['id']}/matches/{sara_match['id']}/winner"
        assert client.post(win, json={"team_id": 999}).status_code == 409
        loser = sara_match["team_b"]["id"]
        if loser == detail["my_team_id"]:
            loser = sara_match["team_a"]["id"]
        decided = client.post(win, json={"team_id": loser}).json()
        done = next(m for m in decided["rounds"][0]["matches"] if m["id"] == sara_match["id"])
        assert done["walkover"] is True
        assert done["winner_team_id"] == loser
        assert client.post(win, json={"team_id": loser}).status_code == 409  # ya jugado
        bad = f"/api/admin/championships/{champ['id']}/matches/999/winner"
        assert client.post(bad, json={"team_id": loser}).status_code == 409
        login(client, "pepe")
        assert client.post(win, json={"team_id": loser}).status_code == 403


def test_two_people_play_against_each_other() -> None:
    settings = fast_settings(admins=frozenset({"sara"}))
    app = create_app(settings)
    with TestClient(app) as sara, TestClient(app) as pepe:
        register(pepe, "pepe")
        register(sara, "sara")
        champ = new_championship(sara)
        url = f"/api/championships/{champ['id']}"
        sara.post(f"{url}/teams", json={"team_name": "Sara"})
        pepe.post(f"{url}/teams", json={"team_name": "Pepe"})
        db = hub_of(sara).db
        with db.session() as session:  # cuadro a mano: Sara contra Pepe en cuartos
            row = session.get(Championship, champ["id"])
            row.teams += [ChampTeam(name=f"Bots {k}", bot_avatars=["marquesa"]) for k in range(6)]
            session.flush()
            ids = [t.id for t in row.teams]
            for slot in range(4):
                a, b = ids[2 * slot], ids[2 * slot + 1]
                row.matches.append(ChampMatch(round=1, slot=slot, team_a_id=a, team_b_id=b))
            row.matches += [ChampMatch(round=2, slot=k) for k in range(2)]
            row.matches.append(ChampMatch(round=3, slot=0))
            row.status = "en_juego"
            session.flush()
            match_id = row.matches[0].id
        room = sara.post(f"{url}/matches/{match_id}/play").json()
        assert room["human_seats"] == [0, 1]
        assert sara.post(f"/api/rooms/{room['code']}/start").status_code == 409  # falta Pepe
        register(TestClient(app), "intrusa")  # alguien que no juega ese partido
        with TestClient(app) as intrusa:
            login(intrusa, "intrusa")
            assert intrusa.post(f"/api/rooms/{room['code']}/join").status_code == 409
        assert pepe.post(f"{url}/matches/{match_id}/play").json()["code"] == room["code"]
        assert pepe.post(f"/api/rooms/{room['code']}/start").status_code == 200
        hub = hub_of(sara)
        live = hub.rooms[room["code"]]
        assert [o.user_id is not None for o in live.seats] == [True, True, False, False]
        assert sara.get(url).json()["rounds"][0]["matches"][0]["room"] == room["code"]


def test_starts_on_its_date_and_deleted_players_become_bots() -> None:
    with admin_client() as client:
        register(client, "pepe")
        register(client, "sara")
        champ = new_championship(client)
        url = f"/api/championships/{champ['id']}"
        login(client, "pepe")
        client.post(f"{url}/teams", json={"team_name": "Pepe"})
        client.request("DELETE", "/api/me", json={"password": "contraseña1"})
        login(client, "sara")
        detail = client.get(url).json()
        assert detail["team_list"][0]["players"] == []  # su sitio es ahora de un bot
        assert detail["status"] == "inscripcion"
        db = hub_of(client).db
        with db.session() as session:
            row = session.get(Championship, champ["id"])
            row.starts_at = datetime(2020, 1, 1)
        listed = client.get("/api/championships").json()[0]
        assert listed["status"] == "terminado"  # sólo bots: se juega entero solo


def test_finished_match_room_is_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    with admin_client() as client:
        register(client, "sara")
        champ = new_championship(client)
        url = f"/api/championships/{champ['id']}"
        client.post(f"{url}/teams", json={"team_name": "Sara"})
        detail = client.post(f"/api/admin/championships/{champ['id']}/start").json()
        match = my_match(detail)
        first = client.post(f"{url}/matches/{match['id']}/play").json()["code"]
        hub = hub_of(client)
        monkeypatch.setattr(type(hub.rooms[first]), "finished", property(lambda _: True))
        second = client.post(f"{url}/matches/{match['id']}/play").json()["code"]
        assert second != first


def test_match_room_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from mus_web.rooms import RoomError

    with admin_client() as client:
        register(client, "sara")
        champ = new_championship(client)
        url = f"/api/championships/{champ['id']}"
        client.post(f"{url}/teams", json={"team_name": "Sara"})
        detail = client.post(f"/api/admin/championships/{champ['id']}/start").json()
        match = my_match(detail)
        hub = hub_of(client)

        def full(*_: object, **__: object) -> None:
            raise RoomError("Hay demasiadas salas abiertas")

        monkeypatch.setattr(hub, "create", full)
        assert client.post(f"{url}/matches/{match['id']}/play").status_code == 503


def test_result_after_deleting_or_awarding() -> None:
    with admin_client() as client:
        register(client, "sara")
        champ = new_championship(client)
        url = f"/api/championships/{champ['id']}"
        client.post(f"{url}/teams", json={"team_name": "Sara"})
        detail = client.post(f"/api/admin/championships/{champ['id']}/start").json()
        match = my_match(detail)
        code = client.post(f"{url}/matches/{match['id']}/play").json()["code"]
        client.post(f"/api/rooms/{code}/start")
        win = f"/api/admin/championships/{champ['id']}/matches/{match['id']}/winner"
        client.post(win, json={"team_id": detail["my_team_id"]})  # se lo dan antes de acabar
        play_over_socket(client, code)
        hub = hub_of(client)
        hub.save(hub.rooms[code])  # no falla: el partido ya tenía ganador
        after = client.get(url).json()
        done = next(m for r in after["rounds"] for m in r["matches"] if m["id"] == match["id"])
        assert done["walkover"] is True
        # Y si el campeonato se borra mientras se juega, la partida se guarda igual.
        nxt = my_match(after) if after["status"] == "en_juego" else None
        if nxt is not None:
            code = client.post(f"{url}/matches/{nxt['id']}/play").json()["code"]
            client.post(f"/api/rooms/{code}/start")
            client.delete(f"/api/admin/championships/{champ['id']}")
            play_over_socket(client, code)
            hub.save(hub.rooms[code])
            assert client.get("/api/me/games").json()
