# La IA de MUS.ST: agentes implementados

Estado de la arquitectura multiagente de [`ai-design.md`](ai-design.md) §3. Todo vive
en `src/mus_engine/ai/` y **sólo lee la observación** del jugador (nunca el estado
completo de la partida).

| Agente | Fase | Módulo | Estado |
|---|---|---|---|
| Fuerza de mano exacta | D | `ai/classes.py`, `ai/equity.py` | ✅ |
| CardCountingAgent | D | `ai/counting.py` | ✅ |
| ScoreAgent | D | `ai/score.py` | ✅ |
| Bot **medio** | D | `bots/medium_bot.py` | ✅ |
| PlayerProfileAgent | E | — | pendiente |
| HandInferenceAgent, EquityAgent completo | F | — | pendiente |
| SignalAgent | G | — | pendiente |
| LearningAgent, bot **profesional** | H | — | pendiente |

## Fuerza de mano exacta (`classes.py`, `equity.py`)

En el Mus el palo no importa nunca: todos los lances dependen sólo del **rango
efectivo** de cada naipe (en ocho reyes el 3 es rey y el 2 es as). Con 8 rangos
efectivos sólo hay **330 clases de mano** (frente a 91.390 manos concretas). Se
precalcula la fuerza de cada clase en cada lance con los evaluadores del propio motor.

Con eso, la probabilidad de que **mi pareja** gane un lance se calcula **de forma
exacta, sin simular**:

1. para cada jugador se obtiene la distribución de sus clases posibles, pesando cada
   clase por cuántas manos concretas caben en los naipes que quedan
   (`HandClass.weight`) y filtrando por sus declaraciones de pares y juego;
2. se suma sobre las manos posibles de mi compañero la probabilidad de que la mejor
   mano de la pareja gane a las dos rivales, con los empates para el más cercano a la
   mano (C.VI).

Simplificación: las manos de los demás se tratan como independientes (se ignora que dos
rivales no pueden tener el mismo naipe). Un test compara el cálculo con repartos reales
resueltos por el motor: la diferencia es menor de 3 puntos.

`Distribution.window(low, high)` condiciona la mano de un jugador a un tramo de
cuantiles: «sólo envida con su 45 % mejor» se traduce en `window(0.55, 1.0)`. Es la
pieza que usan los envites para razonar sobre lo que significa que alguien quiera o
envide.

## CardCountingAgent (`counting.py`)

Devuelve un `Knowledge` con:

- los naipes que pueden tener los demás: 40 − mi mano − mis descartes de esta jugada
  (los descartes vuelven al mazo si se rebaraja, C.III-15);
- las declaraciones de pares y juego de cada asiento;
- cuántos naipes ha pedido cada uno en cada ronda de descarte (para los perfiles, Fase E).

## ScoreAgent (`score.py`)

Tabla `W(mis tantos, sus tantos)`: probabilidad de ganar el juego. Se calcula con un
modelo de manos independientes cuyos tantos por mano (`HAND_POINTS`) se midieron en 600
partidas entre bots (unos 3,5 tantos por pareja y mano).

| Mis tantos | Sus tantos | P(ganar) |
|---|---|---|
| 20 | 20 | 50 % |
| 30 | 20 | 86 % |
| 38 | 20 | 99,6 % |
| 20 | 38 | 0,4 % |

Cada resultado posible se valora por cómo cambia `W`. De ahí sale sola la agresividad
pedida: con el rival a punto de ganar, perder unos tantos más apenas cambia nada y
arriesgar sale a cuenta; con la partida encarrilada, cualquier riesgo cuesta.

## Bot medio (`bots/medium_bot.py`)

- **Mus**: corta si la ventaja esperada en tantos (probabilidad exacta de ganar cada
  lance, ponderada) supera un umbral.
- **Descarte**: prueba **todas** las formas de quedarse con 0–3 naipes y, para cada una,
  todas las clases de naipes que pueden entrar con su probabilidad exacta; se queda con
  la de mayor valor esperado.
- **Envites**: para cada acción legal (pasar, envidar, subir, querer, no querer, órdago)
  calcula su valor esperado **en probabilidad de ganar la partida** y elige la mayor.
  Modelo de los rivales, mientras no haya perfiles: quieren y envidan sólo con sus
  mejores manos (constantes `ACCEPT_*`, `*_WITH`); «me han envidado» condiciona la mano
  del que envida a ese tramo y se recalcula exactamente.
- **Señas**: como el bot sencillo.

Ejemplo (test `test_ordago_response_depends_on_the_score`): con un solo rey en grande,
el medio **quiere** el órdago rival si va perdiendo 20–37 y lo **rechaza** si va ganando
37–20; y con esa misma mano **echa** él el órdago si va perdiendo y sólo envida si va
ganando.

### Resultados

Torneo `python -m mus_engine.arena --games 100 --seed 7` (100 partidas por pareja de
bots, alternando lados):

| Bot | % victorias | Elo |
|---|---|---|
| medio | 70,5 | 1671 |
| sencillo | 60,5 | 1568 |
| aleatorio | 19,0 | 1260 |

Cara a cara, en 600 partidas no usadas para ajustar los parámetros: medio 65 % contra
sencillo y 84 % contra aleatorio. `tests/bots/test_medium_bot.py` exige ≥ 58 % y ≥ 75 %
con semillas fijas.

### Cómo se llegó aquí

La primera versión **perdía** contra el sencillo (37 %). Separando sus piezas se vio que
envidar «en abierto» ya era bueno (58 %) y que el fallo estaba en responder: suponía que
quien envida se retira la mitad de las veces si le suben, cuando quien ha envidado casi
siempre quiere. Con un modelo separado para quien ya ha envidado
(`PROPOSER_ACCEPTS_*`) y órdagos más prudentes, llegó al 65 %. Los parámetros de los
rivales son la parte más frágil: la Fase E los sustituirá por el perfil aprendido de
cada jugador.

Durante la fase apareció un fallo del bot sencillo: con dos jugadas de 31 se subían el
envite sin fin y la partida no terminaba. Ahora no sube cuando lo que hay en juego ya
basta para ganar (test de regresión `tests/regression/test_bots_finish_games.py`).
