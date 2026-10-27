"""Campeonatos por eliminatorias: inscripción, cuadro y avance de ronda.

Un administrador crea el campeonato (nombre, fecha de comienzo y 8, 16 o 32 parejas).
La gente se apunta en parejas: una persona con un bot de compañero, o dos personas. Al
llegar la fecha se sortea el cuadro y las plazas que falten se llenan con parejas de
bots. Cada ronda empareja a los ganadores de la anterior: octavos, cuartos de final,
semifinales y final. Los partidos entre dos parejas de bots se juegan solos en el
servidor; en los demás juegan las personas de cada pareja (``mus_web.app``).

Todo trabaja sobre una sesión de base de datos abierta: quien llama hace el commit.
"""

from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy.orm import Session

from mus_engine.bots.base import BotContext
from mus_engine.bots.simple_bot import SimpleBot
from mus_engine.config import GameConfig
from mus_engine.game.game import Game
from mus_engine.players.seating import ALL_SEATS, SeatId
from mus_web.db import Championship, ChampMatch, ChampTeam, utcnow

SIZES = (8, 16, 32)  # parejas: como mínimo 8 (cuartos de final, semifinales y final)
ROUND_NAMES = {1: "Final", 2: "Semifinales", 4: "Cuartos de final", 8: "Octavos de final"}
BOT_TEAM_NAMES = (
    "Los Tahúres",
    "Las Piedras Rodantes",
    "Órdago y Medio",
    "La Pareja Imposible",
    "Los Revoques",
    "Duples de Reyes",
    "Los de la 31",
    "Los Amarracos",
    "Mus de Barrio",
    "Envido y Quiero",
    "La Peña del Mus",
    "Los Faroleros",
    "Cuatro Reyes",
    "Los de la Chica",
    "Grande y Libre",
    "Los Mudos",
    "Las Señas Ciegas",
    "Al Punto",
    "Los Pasadores",
    "Medias de Ases",
    "La Mano Inocente",
    "Los del Postre",
    "Treinta y Una",
    "Los Cortamus",
    "La Baraja Loca",
    "Los Sin Juego",
    "Reyes Magos",
    "La Última Piedra",
    "Los Descartes",
    "Pares y Nones",
    "La Vaca del Mus",
)


class ChampionshipError(Exception):
    """Petición imposible en el estado del campeonato (se le explica a la persona)."""


def round_count(size: int) -> int:
    return size.bit_length() - 1


def round_name(size: int, round_no: int) -> str:
    matches = size >> round_no
    return ROUND_NAMES.get(matches, f"Ronda {round_no}")


def members(team: ChampTeam) -> list[int]:
    """Personas de la pareja (0, 1 o 2)."""
    return [u for u in (team.captain_id, team.partner_id) if u is not None]


def team_of(champ: Championship, user_id: int) -> ChampTeam | None:
    return next((t for t in champ.teams if user_id in members(t)), None)


# --- Inscripción ---------------------------------------------------------------------------


def sign_up(
    champ: Championship, user_id: int, name: str, partner_open: bool, bot_avatar: str
) -> ChampTeam:
    """Apunta una pareja nueva: la persona y un bot (o una plaza libre para otra persona)."""
    _check_open(champ)
    name = name.strip()
    if not 1 <= len(name) <= 30:
        raise ChampionshipError("El nombre de la pareja tiene que tener entre 1 y 30 letras")
    if team_of(champ, user_id) is not None:
        raise ChampionshipError("Ya estás apuntado en este campeonato")
    if any(t.name.lower() == name.lower() for t in champ.teams):
        raise ChampionshipError("Ya hay una pareja con ese nombre")
    if len(champ.teams) >= champ.size:
        raise ChampionshipError("El campeonato está completo")
    team = ChampTeam(
        name=name, captain_id=user_id, partner_open=partner_open, bot_avatars=[bot_avatar]
    )
    champ.teams.append(team)
    return team


def join_team(champ: Championship, team_id: int, user_id: int) -> ChampTeam:
    """Ocupa la plaza libre de compañero de una pareja."""
    _check_open(champ)
    if team_of(champ, user_id) is not None:
        raise ChampionshipError("Ya estás apuntado en este campeonato")
    team = _team(champ, team_id)
    if not team.partner_open or team.partner_id is not None:
        raise ChampionshipError("Esa pareja no busca compañero")
    team.partner_id = user_id
    return team


def leave(champ: Championship, user_id: int) -> None:
    """Se borra antes de empezar: si es quien apuntó la pareja, se va la pareja entera."""
    _check_open(champ)
    team = team_of(champ, user_id)
    if team is None:
        raise ChampionshipError("No estás apuntado en este campeonato")
    if team.captain_id == user_id:
        champ.teams.remove(team)
    else:
        team.partner_id = None


def _check_open(champ: Championship) -> None:
    if champ.status != "inscripcion":
        raise ChampionshipError("La inscripción está cerrada: el campeonato ya ha empezado")


def _team(champ: Championship, team_id: int) -> ChampTeam:
    team = next((t for t in champ.teams if t.id == team_id), None)
    if team is None:
        raise ChampionshipError("Esa pareja no está en este campeonato")
    return team


# --- Cuadro -----------------------------------------------------------------------------


def due(champ: Championship, now: datetime | None = None) -> bool:
    """¿Toca empezar? (ha llegado la fecha y hay al menos una pareja apuntada)."""
    moment = now or utcnow()
    return champ.status == "inscripcion" and champ.starts_at <= moment and bool(champ.teams)


def start(session: Session, champ: Championship, rng: random.Random, avatars: list[str]) -> None:
    """Cierra la inscripción, completa con parejas de bots y sortea el cuadro."""
    _check_open(champ)
    if not champ.teams:
        raise ChampionshipError("No hay ninguna pareja apuntada")
    taken = {t.name for t in champ.teams}
    names = [n for n in BOT_TEAM_NAMES if n not in taken]
    for k in range(champ.size - len(champ.teams)):
        name = names[k] if k < len(names) else f"Pareja bot {k + 1}"
        champ.teams.append(ChampTeam(name=name, bot_avatars=rng.sample(avatars, 2)))
    for team in champ.teams:
        team.partner_open = False  # la plaza de compañero que quede libre es para un bot
    session.flush()  # ids de las parejas nuevas
    order = list(champ.teams)
    rng.shuffle(order)
    for round_no in range(1, round_count(champ.size) + 1):
        for slot in range(champ.size >> round_no):
            match = ChampMatch(round=round_no, slot=slot)
            if round_no == 1:
                match.team_a_id, match.team_b_id = order[2 * slot].id, order[2 * slot + 1].id
            champ.matches.append(match)
    champ.status = "en_juego"
    session.flush()
    play_bot_matches(champ, rng)


def match_of(champ: Championship, match_id: int) -> ChampMatch:
    match = next((m for m in champ.matches if m.id == match_id), None)
    if match is None:
        raise ChampionshipError("Ese partido no es de este campeonato")
    return match


def ready(match: ChampMatch) -> bool:
    """Se puede jugar: ya se conocen las dos parejas y aún no hay ganador."""
    return None not in (match.team_a_id, match.team_b_id) and match.winner_team_id is None


def record(
    champ: Championship,
    match: ChampMatch,
    winner_team_id: int,
    score: list[int] | None,
    rng: random.Random,
    game_id: int | None = None,
    walkover: bool = False,
) -> None:
    """Apunta el ganador, lo pasa a la ronda siguiente y juega los partidos de bots."""
    if not ready(match):
        raise ChampionshipError("Ese partido no se puede jugar ahora")
    if winner_team_id not in (match.team_a_id, match.team_b_id):
        raise ChampionshipError("Esa pareja no juega este partido")
    match.winner_team_id = winner_team_id
    match.score = score
    match.game_id = game_id
    match.walkover = walkover
    match.played_at = utcnow()
    if match.round == round_count(champ.size):
        champ.winner_team_id = winner_team_id
        champ.status = "terminado"
        return
    following = next(
        m for m in champ.matches if m.round == match.round + 1 and m.slot == match.slot // 2
    )
    if match.slot % 2 == 0:
        following.team_a_id = winner_team_id
    else:
        following.team_b_id = winner_team_id
    play_bot_matches(champ, rng)


def play_bot_matches(champ: Championship, rng: random.Random) -> None:
    """Juega en el servidor los partidos listos entre dos parejas sin personas."""
    teams = {t.id: t for t in champ.teams}
    for match in list(champ.matches):
        if champ.status != "en_juego":
            return
        if not ready(match):
            continue
        a, b = teams[match.team_a_id or 0], teams[match.team_b_id or 0]
        if members(a) or members(b):
            continue
        winner, score = simulate(champ.target, rng.getrandbits(63))
        record(champ, match, a.id if winner == 0 else b.id, score, rng)


def simulate(target: int, seed: int) -> tuple[int, list[int]]:
    """Partida entera entre bots (pareja 0: asientos 0 y 2). Devuelve ganador y tantos."""
    config = GameConfig(target_score=target, negadas_at_end=True)
    bots = [SimpleBot() for _ in ALL_SEATS]
    for seat, bot in enumerate(bots):
        bot.on_game_start(BotContext(SeatId(seat), config, seed + seat, {}))
    game = Game(config=config, seed=seed)
    game.start()
    while not game.is_finished:
        (seat,) = game.current_actors()
        game.apply_action(seat, bots[seat].decide(game.get_observation(seat)))
    assert game.winner is not None
    return game.winner.value, list(game.get_state().score.tantos)


def seats_for(match: ChampMatch, teams: dict[int, ChampTeam]) -> dict[int, SeatId]:
    """Dónde se sienta cada persona del partido: pareja A en 0 y 2, pareja B en 1 y 3."""
    seats: dict[int, SeatId] = {}
    for team_id, first in ((match.team_a_id, 0), (match.team_b_id, 1)):
        team = teams[team_id or 0]
        for k, user_id in enumerate((team.captain_id, team.partner_id)):
            if user_id is not None:
                seats[user_id] = SeatId(first + 2 * k)
    return seats


def bot_avatars_for(match: ChampMatch, teams: dict[int, ChampTeam]) -> dict[SeatId, str]:
    """Avatares de los bots del partido en sus asientos (los que eligió cada pareja)."""
    chosen: dict[SeatId, str] = {}
    for team_id, first in ((match.team_a_id, 0), (match.team_b_id, 1)):
        team = teams[team_id or 0]
        free = [
            s
            for k, s in enumerate((first, first + 2))
            if (team.captain_id, team.partner_id)[k] is None
        ]
        for seat, avatar in zip(free, team.bot_avatars, strict=False):
            chosen[SeatId(seat)] = avatar
    return chosen
