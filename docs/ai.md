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
| PlayerProfileAgent | E | `ai/profiles.py` | ✅ (análisis y memoria; ver abajo) |
| Inferencia por el mus y los pases | E | `ai/inference.py` | ✅ (desactivada en el bot medio) |
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

## Fase E: perfiles de jugador (`profiles.py`, `inference.py`)

### Qué se mide de cada jugador

`ProfileTracker` lee **sólo eventos públicos** (lo que cada uno hace y las manos que se
enseñan al final) y cruza cada decisión con la fuerza de la mano con que se tomó, en
percentil entre las manos que pueden jugar ese lance:

| Tramo | Percentil | Para qué |
|---|---|---|
| mala | < 30 % | faroles (envidar con el 30 % peor) |
| regular | 30–60 % | |
| buena | 60–80 % | |
| muy buena | ≥ 80 % | ir de tapado (pasar con el 20 % mejor) |

`PlayerProfile` guarda contadores (sumables entre partidas, JSON) y da, con **priors
Beta** (un jugador nuevo parte del comportamiento medio):

- frecuencia de envite, órdago, querer, querer órdagos y cortar el mus;
- envite / órdago / querer **por tramo de fuerza**; farol y tapado;
- tantos envidados de media por tramo (las «piedras» con buenas y con malas);
- si envida distinto cuando va perdiendo;
- con qué manos corta o pide mus (`mus_beta`);
- etiqueta (`style`): por conocer, imprevisible, farolero, arriesgado, conservador,
  cauto, de tapado o equilibrado, con un nivel de confianza.

En 30 partidas entre bots: el `sencillo` sale **conservador** (envida el 6 %, nunca
órdago), el `aleatorio` **imprevisible** (envida igual con malas que con buenas) y un
bot farolero de prueba, **imprevisible/farolero** (farol del 55 %).

### Memoria y web

Al terminar cada partida, la web suma lo aprendido de cada persona a su perfil
(tabla `player_profiles`). Al empezar la siguiente, los bots lo reciben en
`BotContext.profiles`. La persona ve su estilo en el lobby (`GET /api/me/profile`), lo
descarga con sus datos y se borra con su cuenta.

### Inferencia por el mus y los pases (`inference.py`)

Cortar el mus es una señal fuerte (400 partidas entre bots):

| Señal | P(pares) | P(juego) | percentil medio en grande |
|---|---|---|---|
| corta | 73 % | 60 % | 0,70 |
| pide mus | 41 % | 3,5 % | 0,37 |
| no habla | 54 % | 28 % | 0,51 |

Cada señal se convierte en una inclinación `exp(β·(percentil − ½))` de las manos
posibles; el perfil de cada jugador la ajusta con sus propias manos enseñadas. Con ella
la probabilidad que calcula el bot **se calibra mucho mejor** (aceptando envites,
predecía 40 % y ganaba 25 %; con la inferencia, 37 % frente a 35 % en grande).

### Qué se probó y qué se decidió

Partidas no usadas para ajustar (400 por fila, margen ±2,5 puntos):

| Bot medio… | contra sencillo | contra farolero |
|---|---|---|
| como en la Fase D (sin perfiles ni inferencia) | **65 %** | **56–60 %** |
| con perfiles de los rivales | 63–66 % | 56 % |
| con perfiles e inferencia por mus y pases | 61 % | 57–59 % |
| con perfil del farolero aprendido en 40 partidas | — | 55 % |

Conclusión: los perfiles **describen bien** a cada jugador, pero usarlos para decidir,
con el modelo de decisión actual (umbrales fijos más una tasa de faroles), no gana más
partidas que los valores ajustados de la Fase D. La inferencia mejora la calibración pero
tampoco se traduce en victorias. Por eso el bot medio los deja **desactivados**
(`MediumBot.use_profiles`, `MediumBot.infer_from_mus_and_passes`): están probados y
listos para la Fase F, en la que la inferencia pondera cada mano posible por toda la
secuencia de acciones de cada jugador (§3.3) y el valor esperado se estima simulando
sus respuestas según su perfil (§3.6).

Lecciones del proceso (para la defensa):

1. Un primer intento con perfiles bajó al 55 %: el modelo bayesiano por tramos era más
   tosco que los umbrales ajustados. Se cambió por «umbral + fuga», que sin datos
   reproduce exactamente la Fase D.
2. Con un perfil correcto del farolero el bot ganaba *menos*: sus probabilidades estaban
   mal calibradas (ignoraba que quien corta el mus va fuerte). Los valores ajustados a
   ojo compensaban ese sesgo; al darle datos reales, la compensación desaparecía.
3. Deducir que «quien pasa va flojo» de forma tajante hundía el rendimiento: con buenas
   manos también se pasa. La versión suave usa P(pasa | fuerza) del perfil.

### Órdagos prudentes (petición de la usuaria)

El bot medio sólo echa (o devuelve) un órdago si, cuando se lo quieran, calcula al
menos un 60 % de ganar el lance (`ORDAGO_MIN_WIN`), salvo que la partida esté casi
perdida (P(ganar) < 15 %, `DESPERATE`), en cuyo caso arriesga como antes. Además de
hacer las partidas contra personas menos «a una carta», gana más: 68 % contra el
sencillo (400 partidas) y 85 % contra el aleatorio (200).

Después, jugando en la web, los bots seguían echando demasiados órdagos (entre bots
medios, uno por jugada; uno de cada cinco «desesperado» con cualquier mano). Ahora:

- Nunca hay órdago hasta que alguna pareja llega a 30 tantos (`ORDAGO_LATE`): al
  principio, con una mano segura se envida para cobrar más.
- Después, sólo con un 90 % de ganar el lance si se lo quieren (`ORDAGO_MIN_WIN`).
- Desesperado (P(ganar la partida) < 15 %), sólo con al menos un 50 % de ganar el lance
  (`DESPERATE_MIN_WIN`), no con cualquier cosa.

Resultado: de 140 órdagos en 140 jugadas a 15 en 152 (partidas entre bots medios), y
el bot gana lo mismo: 71 % contra el sencillo (300 partidas).
