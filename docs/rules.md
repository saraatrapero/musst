# Reglas del motor y trazabilidad con el Reglamento FEM

Fuente de verdad: `docs/reglamento/reglamento-fem.pdf` (Reglamento de Juego,
Federación Española de Mus, 13 páginas).
Notación de citas: **C.VI-7** = Capítulo VI, Artículo 7. **Voc.** = vocabulario de
C.VIII-8. **Intro-E** = apartado E de la Introducción.

Cada regla implementada tendrá aquí: cita → decisión → test(s).

---

## 1. Naturaleza del reglamento (hallazgo clave)

El reglamento FEM es un **reglamento de competición y conducta**: regula sorteos,
reparto físico, tiempos, señas, comunicación entre compañeros, errores humanos y
sus penalizaciones, arbitraje. **Presupone** que se conocen las reglas básicas del
Mus y **no define** varios elementos esenciales para un motor:

- valor en tantos de pareja / medias / duples, del juego (31 y resto), del punto y
  del lance de grande/chica "en paso";
- valor de cada carta para juego y punto (figuras = 10, etc.);
- orden completo del juego (sólo dice que 31 es la máxima y 33 la mínima);
- regla explícita de desempate por la mano;
- rotación del reparto entre jugadas;
- número mínimo/máximo de cartas a descartar;
- si la partida termina en cuanto una pareja llega al tanteo, a mitad de recuento.

Esos puntos se resolvieron como decisiones explícitas aprobadas (sección 4); no
proceden del reglamento y así se indica en el código y en los tests.

---

## 2. Reglas confirmadas por el reglamento

| ID | Regla | Cita | Consecuencia en el motor |
|---|---|---|---|
| R-01 | Baraja española de 40 naipes | C.II-3, C.III-1 | `Deck.standard()` = 40 cartas, 10 rangos × 4 palos |
| R-02 | Ocho reyes y ocho ases: treses valen como reyes, doses como ases | C.II-3 | `RankingPolicy` con `kings_are_threes`, `aces_are_twos` |
| R-03 | Mano = jugador a la derecha del que reparte | Voc. "Mano" | `mano = next_player(dealer)` |
| R-04 | En pares o juego, el primer jugador que los tiene es **mano del lance** | Voc. "Mano" | `lance_mano(state, lance)` distinto de `mano` |
| R-05 | Se reparte de uno en uno, de derecha a izquierda (empezando por la mano) | C.III-2 | reparto 1 a 1 desde la mano |
| R-06 | Primer reparto por sorteo: se baraja, corta el de la izquierda del que baraja, y el palo del naipe que sale asigna el reparto (oros → 1º a la derecha del que cortó, copas → 2º, espadas → 3º, bastos → el que lo muestra) | C.III-1, C.III-3 | procedimiento simulado con la semilla (D-03) |
| R-07 | El mus se puede cortar con cualquier naipe | C.IV-2 | `CutMusAction` siempre legal en su turno |
| R-08 | Orden del mus: el 2º (mano de la pareja postre) no puede cortar hasta que el mano haya dado mus; el 3º puede cortar en cualquier momento; el 4º una vez que la pareja mano lo ha dado | C.IV-4 | hablar en orden mano → 2º → 3º → 4º satisface todas las restricciones (D-04) |
| R-09 | "Paso" del mano en el mus = cortar el mus | Voc. "Paso" | equivalencia documentada; no hay acción extra |
| R-10 | Orden de descarte: empieza el que reparte y termina el mano | C.III-11 | `DISCARD` en orden postre → 3º → 2º → mano |
| R-11 | En los descartes se sirve de una vez a cada jugador | C.III-2 | reposición en bloque por jugador (orden: D-06) |
| R-12 | Si se acaba el mazo, el que reparte recoge **todo el descarte**, lo baraja y sirve | C.III-15 | rebarajado de la pila completa de descartes (D-07) |
| R-13 | Prohibido contar los naipes que quedan en el mazo | C.III-16 | la observación **no** expone el tamaño del mazo |
| R-14 | Lances en orden grande, chica, pares, juego o punto; se habla y se tantea en ese orden | C.VII-2, Voc. "Lance" | `LanceType` ordenado; recuento en ese orden |
| R-15 | Juego = los cuatro naipes suman 31 o más; si no, "no juego" ≡ punto | Voc. "No Juego" | `has_juego = total >= 31` |
| R-16 | Jugada máxima: cuatro reyes (grande), cuatro ases (chica), 31 (juego), 30 (punto); mínima: dos ases (pares), 33 (juego) | C.VI-7, C.VI-8 | tests de extremos de cada evaluador; 33 es el peor juego, pareja de ases el peor par |
| R-17 | Cuatro reyes es la jugada máxima también en pares ⇒ cuatro iguales cuentan como duples | C.VI-7 (lista de jugadas máximas por lance) | `ParesCategory.DUPLES` incluye 4 iguales (D-12) |
| R-18 | Categorías de pares: pares (pareja), medias, duples | C.VI-17, C.VIII-2 | `ParesCategory` = {NONE, PAREJA, MEDIAS, DUPLES} |
| R-19 | En pares y juego sólo hablan los que los tienen | C.VI-5, C.VI-22, C.VI-23 | `eligible` del `BetState` |
| R-20 | Declarar pares/juego obliga a decir la verdad | C.VI-17, C.IX-1 | declaración automática por el motor (no se puede mentir) |
| R-21 | Envido = 2 tantos; "envido N" = apuesta de N | Voc. "Envido" | `BetAction(amount)` |
| R-22 | Órdago = apostar el juego completo | Voc. "Órdago" | `OrdagoAction`; si se acepta, el ganador gana el juego |
| R-23 | Nunca ordaguear a dos o más lances a la vez | C.IV-6 | el órdago siempre es del lance en curso |
| R-24 | Con un envite en litigio, el compañero del que envidó no puede subir hasta que contesten los rivales | C.VI-2 | en estado `PENDING` sólo actúan los rivales |
| R-25 | Si un rival quiere y su compañero no, vale el quiero | C.VI-4 | aceptar basta con uno; rechazar requiere a todos los rivales elegibles |
| R-26 | No contestar / mandar hablar al siguiente lance = no aceptar | C.VI-21 | `RejectAction` |
| R-27 | Negada = tanto ganado por no aceptar la **primera** apuesta de un lance | Voc. "Negada" | rechazo del primer envite → 1 tanto |
| R-28 | Pares, juego y punto tienen deje; deje = tanto **sumado** a los ya ganados por un revoque no aceptado en pares, juego o punto | C.VII-1, Voc. "Deje" | ver D-16 (interpretación necesaria) |
| R-29 | Negadas y envites no aceptados se apuntan **en cada lance**; envites aceptados, valor de las jugadas (grande y chica en paso, punto) y valor de pares y juego, **al final** | C.VII-2 | dos momentos de anotación |
| R-30 | Los envites aceptados se cuentan al final y por orden de lances, aunque superen el tanteo del juego | C.VI-6 | importe de envite sin máximo |
| R-31 | Sólo el órdago aceptado permite enseñar las cartas y resolver el juego | C.VI-6 | órdago aceptado ⇒ resolución inmediata |
| R-32 | Un órdago aceptado anula todos los envites aceptados en lances anteriores, aunque con ellos los perdedores ganasen el juego | C.VII-12 | al aceptar órdago se descartan los envites aceptados pendientes |
| R-33 | Si la mano no acepta un envite y llevaba la jugada máxima, el lance lo ganan los rivales | C.VI-7 | tras "no quiero", el lance es del proponente (incluido su valor de pares/juego, D-17) |
| R-34 | Al terminar juego/punto, los cuatro jugadores enseñan todas sus cartas | C.VII-9 | al final de la jugada se revelan las 4 manos (evento público) |
| R-35 | Partida = N juegos ganados (5 en preclasificación); juego a entre 40 y 60 tantos según la organización | Intro-E | `GameConfig.target_score` (40 por defecto) y `games_to_win` |
| R-36 | Amarracos: los conserva un jugador de cada pareja; sirven para tantear | C.VII-3, C.VII-7 | representación de marcador, no regla (D-19) |

### Interpretaciones de orden de mesa (fase 2)

- **Sentido de juego.** Los asientos `0..3` se numeran en orden de habla:
  `next_player(s)` es el jugador "a la derecha" de `s` (Voc. "Mano": la mano está a la
  derecha del que reparte y habla primero). "A la izquierda" es, por tanto, quien habla
  antes (`previous_player`).
- **Orden de descarte (C.III-11).** "El primero en descartarse será el que los da; el
  descarte continuará de izquierda a derecha hasta el mano": postre, 3º, 2º, mano
  (`discard_order`).
- **"Será mano el que corte el mus" (C.III-1).** Se interpreta como que el mano es el
  primero en decidir si hay mus; es coherente con C.IV-4 y con Voc. "Paso" ("cortar el
  mus si se es mano"). No altera la definición de mano (Voc. "Mano").
- **Corte del sorteo (C.III-3).** Corta "el jugador a la izquierda del que los haya
  barajado" (`cutter_for`); el palo del naipe asigna el primer reparto (C.III-1,
  `first_dealer_by_suit`).

Tests: `tests/rules/test_fem_seating.py` (R-03, R-04, R-06, R-08, R-10, D-15).

### Mus y descartes (fase 4)

Implementado en `rules/mus.py` y `game/handlers/mus.py`. Tests con cita en
`tests/rules/test_fem_mus.py`: C.IV-4 (orden), C.IV-2 (cortar con cualquier naipe),
Voc. "Paso", C.III-11 (orden de descarte), C.III-2 (servir de una vez y en el mismo
orden), C.III-15 / D-07 (rebarajar todo el descarte), D-13 (límites), D-14 (sin límite
de rondas). Reparto: `tests/rules/test_fem_dealing.py` (C.III-1, C.III-2).

### Grande y chica (fase 5)

Implementado en `rules/grande.py`, `rules/chica.py` y `rules/evaluation.py`.

- **Fuerza de una jugada**: tupla de rangos efectivos (C.II-3), ordenada de mayor a menor
  en grande y de menor a mayor en chica (C.VI-16, D-10), comparada carta a carta. En
  chica se niegan los valores para que en ambos lances "mayor es mejor". Los palos no
  cuentan.
- **Empates** (D-09): `resolve()` toma la fuerza máxima y, si varios la comparten, da el
  lance al más cercano a la mano. El desempate es explícito y no depende del orden de
  los datos (test específico).
- Hay 330 jugadas distintas en ocho reyes; la máxima de grande es cuatro reyes y la de
  chica cuatro ases (C.VI-7), comprobado sobre las 91 390 manos posibles.
- Los tantos (envites, paso) no los decide el evaluador: corresponden a las fases de
  envites y tanteo.

Tests: `tests/rules/test_fem_grande_chica.py`; propiedades frente a una implementación
de referencia independiente en `tests/property/test_grande_chica_properties.py`.

### Pares (fase 6)

Implementado en `rules/pares.py` y `rules/participation.py`.

- **Clasificación** por rangos efectivos (C.II-3): sin pares, pareja, medias, duples
  (R-18). Cuatro iguales = duples con los dos pares del mismo rango (R-17, D-12).
- **Fuerza**: `(categoría, rangos)`: pareja → rango del par; medias → rango del trío;
  duples → par mayor y par menor (D-11). Los naipes sueltos no cuentan; si la fuerza
  coincide, decide la mano (D-09).
- Extremos comprobados sobre las 91 390 manos: máxima = cuatro reyes (C.VI-7), mínima con
  pares = dos ases (C.VI-8).
- **Valor** (D-02): `pares_points(categoría, config)` → 1 / 2 / 3.
- **Participación** (R-19, D-20): `Participation.from_holders(jugadores_con_pares, mano)`
  da el orden de habla, la mano del lance (Voc. "Mano") y si el lance tiene envites (las
  dos parejas), lo cobra una sola pareja o no se juega. Se reutilizará para juego.

Tests: `tests/rules/test_fem_pares.py`, `tests/unit/test_pares.py`,
`tests/unit/test_participation.py`, `tests/property/test_pares_properties.py`.

### Juego y punto (fase 7)

Implementado en `rules/juego.py` y `rules/punto.py`.

- **Total** con el valor de D-01 (figuras y treses 10, ases y doses 1). Se separan
  *tener juego* (`JuegoHand.has_juego`, total ≥ 31, Voc. "No Juego") y *qué juego*
  (`JuegoHand.total` y su posición en `JUEGO_ORDER`).
- **Orden del juego** (D-08): 31, 32, 40, 37, 36, 35, 34, 33. Extremos del reglamento
  verificados sobre todas las manos: máxima 31 (C.VI-7), mínima 33 (C.VI-8).
  Juegos posibles: 31–37 y 40; **38 y 39 no existen** con la baraja española.
- No hay "31 real": 7-7-7-sota es un 31 como cualquier otro (no figura en el reglamento).
- **Punto**: gana el total mayor; máxima 30 (C.VI-7). `PuntoEvaluator` rechaza jugadas con
  juego, porque nunca pueden ir a punto.
- **Lance**: `juego_or_punto(manos)` → juego si alguien lo tiene; si no, punto (D-20).
- **Valor** (D-02): `juego_points` → 3 con 31, 2 con otro juego; `punto_points` → 1.

Tests: `tests/rules/test_fem_juego_punto.py`, `tests/unit/test_juego_punto.py`,
`tests/property/test_juego_punto_properties.py`.

---

## 3. Fuera de alcance del motor (y por qué)

| Tema | Cita | Motivo |
|---|---|---|
| Sorteos de mesas, suplencias, tiempos, actas, árbitros, conducta | C.I, C.V, C.X, C.XI, C.XII | organización de torneo, no reglas del juego |
| Mus visto, naipes vistos, naipes de más/de menos, contar el mazo, barajas defectuosas | C.II-4, C.III-6…14, C.III-16 | el motor reparte; estos errores son imposibles por construcción |
| Señas, boquilla, consejos al compañero, declarar naipes | C.IV-3, C.IV-5, C.VI-15…20, C.VI-23, C.VIII | comunicación entre jugadores; el motor no tiene canal de mesa. Puede añadirse más adelante como capa aparte |
| Envites simultáneos de dos compañeros, plurales e imperativos | C.VI-1, C.VI-3, C.VI-5, C.VI-13 | el motor serializa las acciones: no existe simultaneidad |
| Enseñar naipes / meterse en baraja durante un envite | C.VII-10, C.VII-11, C.VI-25 | acciones físicas no representables; el motor nunca muestra cartas antes de tiempo |
| Corte del mus "a falta de tanto" en cualquier momento | C.IV-7 | en un motor por turnos cada jugador puede cortar en su turno; ver D-05 |

---

## 4. Decisiones adoptadas (huecos y ambigüedades)

Formato: duda → qué dice el reglamento → decisión. **Todas las propuestas fueron
aprobadas el 2026-10-03** (incluida D-24a). La columna "Decisión" es normativa
para el motor.

### Valores y órdenes no definidos en el reglamento

| ID | Duda | Reglamento | Decisión |
|---|---|---|---|
| D-01 | Valor de cada carta para juego/punto | No lo define | figuras (sota, caballo, rey) y treses = 10; ases y doses = 1; resto, su número |
| D-02 | Tantos de cada jugada | C.VII-2 dice que pares, juego, punto y grande/chica en paso **tienen valor**, pero no cuánto | pareja 1, medias 2, duples 3; juego 31 = 3, otro juego = 2; punto = 1; grande/chica en paso = 1 |
| D-08 | Orden del juego | Sólo 31 máxima y 33 mínima (C.VI-8, C.VI-9) | 31 > 32 > 40 > 39 > 38 > 37 > 36 > 35 > 34 > 33 (38 y 39 no pueden darse con la baraja española: verificado sobre todas las manos) |
| D-09 | Desempates | No hay regla explícita; C.VI-7 y C.VI-8 lo presuponen (mano con jugada máxima, postre con jugada mínima) | empate en cualquier lance ⇒ gana el jugador más cercano a la mano |
| D-10 | Comparación en grande/chica | C.VI-16: los naipes se cantan de mayor a menor (grande) y de menor a mayor (chica) | comparar carta a carta en ese orden; sólo cuentan los rangos efectivos (palos irrelevantes) |
| D-11 | Comparación dentro de pares | No la define | por categoría; dentro: rango del trío/par; duples: par mayor y luego par menor |
| D-12 | Cuatro iguales | C.VI-7 lo incluye como jugada máxima | duples (dos parejas iguales) |

### Flujo de la jugada

| ID | Duda | Reglamento | Decisión |
|---|---|---|---|
| D-03 | Primer repartidor | C.III-1 describe el sorteo por palo | simular el procedimiento con la semilla (barajador = asiento 0, configurable); también se puede fijar por config |
| D-04 | Orden del mus | C.IV-4 permite al 3º cortar "en cualquier momento" | orden estricto mano → 2º → 3º → 4º; un único corte termina el mus |
| D-05 | Excepción "a falta de tanto" (C.IV-7) | no define "a falta de tanto" | no modelarla (no cambia el resultado en un motor por turnos) |
| D-06 | Orden en que se **reponen** las cartas tras el descarte | C.III-2: "de una vez a cada jugador y por el mismo orden"; C.III-11: se descarta del que reparte al mano | se declaran los descartes en orden postre → mano (C.III-11) y se sirve en ese mismo orden |
| D-07 | Mazo agotado | C.III-15: se recoge "todo el descarte" | literal: se rebaraja toda la pila de descartes, incluidas las cartas descartadas en esa misma ronda |
| D-13 | Mínimo y máximo de cartas a descartar | No lo define | mínimo 1, máximo 4 |
| D-14 | Número de rondas de mus | No hay límite | sin límite |
| D-15 | Rotación del reparto | No lo define | reparte el siguiente jugador en el orden de juego (el mano de esta jugada reparte la siguiente) |
| D-20 | Pares/juego de una sola pareja | No lo define explícitamente | si sólo una pareja tiene pares (o juego) no hay envites y cobra al final; si nadie tiene juego se juega punto |

### Apuestas y tanteo

| ID | Duda | Reglamento | Decisión |
|---|---|---|---|
| D-16 | Cuánto vale un revoque no aceptado | Voc. "Negada" (1 tanto la primera apuesta) y "Deje" ("tanto sumado a los ya ganados" en pares, juego, punto); C.VII-2 "tantos de envites revocados y no aceptados" | **grande/chica**: lo ya querido antes del revoque. **pares/juego/punto**: lo ya querido + 1 (el deje). Requiere tu confirmación: es la lectura literal pero no es la práctica habitual en muchas mesas |
| D-17 | Tras un "no quiero" en pares/juego, ¿quién cobra el valor de las jugadas? | C.VI-7: "ganando el lance sus rivales" | el lance es de la pareja que envidó: cobra la negada/deje y, al final, el valor de **sus** pares/juego |
| D-18 | Importe mínimo de envite y de revoque | Voc.: envido = 2; "envido N"; "reenvido: doblar el valor" | envite ≥ 2; revoque = "N más" con N ≥ 2. Alternativa literal: sólo envido 2/N y reenvido = doblar |
| D-21 | ¿Puede responderse con órdago a un envite? | C.VI-1, C.VI-21 mencionan "envite, revoque u órdago" en litigio, sin prohibirlo | sí, el órdago es un revoque válido (no se puede revocar un órdago) |
| D-22 | Fin del juego a mitad de jugada | C.VI-6: envites aceptados al final y por orden de lances; C.VII-2: negadas en cada lance. No dice si se para al llegar al tanteo | el juego termina en el momento en que una pareja alcanza el tanteo (≥ 40), sea por una negada durante los lances o en el recuento final; el recuento se detiene ahí |
| D-23 | Ganar con exactamente 40 o ≥ 40 | No lo define | ≥ `target_score` |
| D-19 | Amarracos | C.VII-3/7 los usan pero no fijan equivalencia | el marcador se lleva en tantos; amarraco = 5 tantos sólo como vista |

### Penalizaciones con efecto en el tanteo (requieren decisión de modelo)

C.III-14, C.VI-9…12 y C.VI-24 regulan casos de **postre que acepta un órdago con la
jugada mínima** (dos ases a pares, 33 a juego): "queda expresamente prohibido querer
un órdago a juego con treinta y tres de postre" (C.VI-9), penalización de 2 tantos
+ negada (C.VI-11), excepción si el compañero cantó pares/juego (C.VI-12), tanto de
negada en el acto con dos ases (C.VI-24).

Problema: la legalidad depende en parte de las cartas **del compañero** (C.VI-12). Si
el motor rechazara la acción, revelaría información privada del compañero.

| ID | Opción | Pros | Contras |
|---|---|---|---|
| D-24a | **No modelar** las penalizaciones (aceptar se permite y se pierde a cartas) | simple, sin fugas | se aparta de C.VI-9…12, C.VI-24 |
| D-24b | Prohibir sólo el caso que depende de las cartas propias (postre con 33 / dos ases cuyo compañero no tiene la jugada) y no aplicar el resto | respeta "prohibido" de C.VI-9 | la regla depende del compañero ⇒ fuga de información |
| D-24c | Permitir la acción y aplicar la penalización reglamentaria al resolver | fiel al reglamento, sin fugas | más complejo; textos ambiguos ("postre del lance", "continuará el juego de la manera habitual") |

Decisión: **D-24a en la primera versión** (desviación documentada), dejando un
punto de extensión para D-24c.
