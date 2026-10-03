# Tanteo

Implementación: `betting/bets.py` (BET SCORE), `scoring/scoring.py` (LANCE SCORE y
aplicación), `scoring/score.py` (GAME SCORE), `game/lance_flow.py` (cuándo se anota).

## Tres niveles

| Nivel | Tipo | Qué es |
|---|---|---|
| BET SCORE | `BetState`, `rejection_points` | lo que produce la apuesta de un lance |
| LANCE SCORE | `LanceOutcome`, `ScoreEntry` | cómo terminó el lance y qué entradas de tanteo genera |
| GAME SCORE | `GameScore` | tantos del juego en curso y juegos ganados por pareja |

## Cuándo se anota (C.VII-2)

1. **En el acto**, al cerrarse un lance con "no quiero":
   - primera apuesta del lance rechazada → **negada**: 1 tanto (Voc. "Negada");
   - revoque rechazado → lo ya querido, **+1 de deje** en pares, juego y punto
     (C.VII-1, Voc. "Deje"; D-16).
2. **Al final de la jugada**, tras enseñar las cuatro manos (C.VII-9), en orden
   grande → chica → pares → juego o punto:

| Lance | En paso | Querido | No querido | Una sola pareja |
|---|---|---|---|---|
| Grande / chica | 1 al ganador | envite al ganador | — (ya anotado) | — |
| Pares | valor de los pares de la pareja ganadora | envite + valor | valor de los pares de la pareja que envidó (D-17) | valor de sus pares |
| Juego | valor del juego de la pareja ganadora | envite + valor | valor del juego de la pareja que envidó (D-17) | valor de su juego |
| Punto | 1 al ganador | envite + 1 | 1 a la pareja que envidó (D-26) | — |

Valores (D-02): pareja 1, medias 2, duples 3; juego de 31 vale 3, otro juego 2; punto 1.
El valor de pares o juego de una pareja es la **suma** de las jugadas de sus dos
jugadores (si ambos las tienen).

El ganador "a cartas" es el mejor entre los participantes del lance; los empates los
gana el más cercano a la mano (D-09).

## Final del juego y de la partida

- En cuanto una pareja alcanza `target_score` (≥, D-23) se detiene el recuento (D-22):
  las entradas posteriores no se anotan. Puede ocurrir a mitad de jugada por una
  negada.
- Los envites se cuentan aunque superen el tanteo (C.VI-6): el marcador puede pasar de 40.
- **Órdago aceptado** (C.VI-6, Voc. "Órdago"): se enseñan las cartas, se resuelve el
  lance y la pareja ganadora suma lo que le falte para el tanteo. Anula los envites
  aceptados en lances anteriores (C.VII-12); lo ya anotado se conserva.
- Al ganar un juego se emite `GameWon`. Si la pareja llega a `games_to_win`, termina la
  partida (`GameFinished`, `GAME_OVER`); si no, se reinicia el tanteo y se reparte una
  nueva jugada (reparte el que fue mano, D-15).

## Amarracos

El marcador se lleva en tantos; `GameScore.amarracos_of(team, 5)` da
`(amarracos, tantos sueltos)` sólo como representación (D-19).

## Desviación conocida

D-24a: no se modelan las penalizaciones por aceptar un órdago siendo postre con la
jugada mínima (C.VI-9…12, C.VI-24), porque su legalidad depende de las cartas del
compañero y el motor no puede rechazar la acción sin revelarlas.
