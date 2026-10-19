# Diseño de la IA de MUS.ST y de la plataforma de bots

> Estado: **APROBADO**. Implementación por fases (sección 6).
> Base: el motor `mus_engine` (en `main`) y el enunciado de la práctica
> *Implementación de Juegos y Jugadores de IA* (IA, 3 MAT-A, 2026/2027).

---

## 0. Objetivos

Lo que pides, en orden de importancia:

1. **Aprender de las partidas perdidas y no repetir los errores.**
2. **Perfilar a cada jugador**: arriesgado, cauto, conservador, farolero…; qué hace con
   buenas y con malas cartas; cuántos tantos (piedras) envida en cada caso.
3. **Intuir las cartas de los rivales** a partir de ese perfil y de lo que hacen en la
   mesa.
4. **Contar cartas**: descartes, cartas que quedan, declaraciones.
5. **Llevar el marcador**: más agresiva cuando va perdiendo y cerca de perder, más
   conservadora cuando va ganando.
6. **Señas**: pasarlas al compañero con ventaja; si los rivales las ven, la ventaja es
   para ellos.

Y lo que exige la práctica (apartado 5), con el estado actual:

| Req | Requisito | Puntos | Estado |
|---|---|---|---|
| 1.1 | Librería instalable, partida completa sin interfaz | 1,5 | ✅ `mus_engine` |
| 1.2 | Interfaz web: una persona juega contra bots | 1,0 | pendiente |
| 1.3 | Web publicada en URL pública | 0,5 | pendiente |
| 2.1 | API pública de bots sin tocar el juego | 1,0 | ✅ `mus_engine.bots` |
| 2.2 | Tests automáticos para bots nuevos | 0,5 | ✅ `check_bot` + CI |
| 2.3 | Documentación online con referencia del API y tutorial | 0,5 | pendiente (hay docs en el repo, no publicadas) |
| 3.1 | Bot propio (0,5 × dificultad 5 = 2,5 por bot) | — | pendiente |
| 3.2 / 3.3 | Bots para/de otros equipos por PR | — | fuera de este diseño |
| 4.1 | Torneo robusto (un bot que falla pierde, el torneo sigue) | 1,0 | ✅ `mus_engine.arena` |
| 4.2 | Clasificación publicada y actualizada automáticamente | 0,5 | pendiente |
| C.1 | Repo ordenado: README, LICENSE, .gitignore | 0,5 | ✅ (MIT) |
| C.2 | Ramas, PR y `main` protegida | 0,5 | falta proteger `main` (ajuste de GitHub, lo haces tú) |
| C.3 | Tests en cada PR | 0,5 | ✅ CI |

El temario es **razonamiento con incertidumbre**: el núcleo de la IA (inferencia
bayesiana de manos, Monte Carlo, valor esperado) encaja directamente con él, y eso es
lo que habrá que defender en la oral.

---

## 1. Principio de juego limpio

**Un bot sólo decide con lo que su asiento puede saber legítimamente.**

- Cada bot controla **un asiento** y recibe sólo su `Observation` (ya existe y está
  probada contra fugas). Una pareja son dos instancias del mismo bot, sin memoria
  compartida durante la jugada: lo único que se comunican son **señas**.
- La memoria entre partidas (perfiles, experiencia) se construye **sólo** con
  información observada: acciones públicas y las manos que el reglamento obliga a
  enseñar al final de cada jugada (C.VII-9) o en un órdago (C.VI-6).
- El torneo pasa a los bots únicamente observaciones; nunca `GameState`. Un test lo
  verifica.

Dato clave para el aprendizaje: **casi todas las jugadas terminan enseñando las cuatro
manos** (C.VII-9). Cada jugada produce ejemplos etiquetados del tipo "el jugador X
envidó 5 en grande con esta mano exacta". Es la materia prima del perfil y de la
inferencia de cartas.

---

## 2. Señas y miradas (ampliación del motor)

Hoy las señas están fuera del motor (`docs/rules.md` §3). Se añaden siguiendo el
capítulo VIII del reglamento y un **modelo de miradas** (decisión IA-2).

### 2.1 Qué señas existen y cuándo son legales

| Regla | Cita | Cómo se modela |
|---|---|---|
| Sólo las señas oficiales | C.VIII-1, C.VIII-2 | `Sena`: dos reyes, dos ases, pares, medias de reyes, medias de ases, medias, duples, juego, treinta y una, treinta, veintinueve, ciego |
| Sólo para transmitir la jugada que se tiene; prohibido señar para preguntar o decidir | C.VIII-4 | **sólo señas verdaderas** (IA-1): el motor rechaza una seña que no corresponda a la mano |
| No antes de cortar el mus | C.VIII-3 | sólo después del corte (S-2) |
| Medias que no sean de reyes, después de grande | C.VIII-2, C.VIII-5 | restricción de momento |
| Treinta, cuando los cuatro han dicho "juego no" | C.VIII-2, C.VIII-5 | sólo si nadie tiene juego, tras la declaración |
| Juego no vale para la treinta y una | C.VIII-2 | `JUEGO` = juego distinto de 31 |
| Ciego no se pasa si hay jugada con seña propia | C.VIII-2 | `CIEGO` sólo si ninguna otra seña es verdadera |
| Nada de señas parciales | C.VIII-6 | con duples no se puede señar "dos reyes" ni "dos ases" |
| El rival no está obligado a confirmar | C.VIII-7 | ver una seña no da más información que la propia seña |

Cada jugador puede hacer cada seña una vez por jugada.

### 2.2 Miradas: quién ve la seña

- En cada momento, cada jugador **mira a alguien**: a su compañero, a uno de los rivales
  o a la mesa. Cada mirada dura unos instantes y cambia al azar (generador determinista
  del motor, así que todo sigue siendo reproducible).
- **Hacia dónde mira cada uno es público**, como en una mesa real: los avatares lo
  muestran girando la cara.
- Una seña de S la ven **exactamente los jugadores que en ese momento están mirando
  a S**:
  - si la ve el compañero, juega con ventaja;
  - si la ve un rival, la ventaja es para el rival;
  - si no la ve nadie, se pierde.
- Quien hace la seña sabe quién le estaba mirando, así que sabe quién la ha visto.
- El tiempo avanza con cada acción y, en la web, también con el reloj: los avatares
  sostienen la mirada unos segundos.
- Parámetros configurables (los niveles de bot los usarán): con qué frecuencia y
  cuánto tiempo mira cada jugador a su compañero, a los rivales y a la mesa.

Eventos: `MiradasCambiadas` (público), `SenaVista` (privado, sólo a quien la ve) y
`SenaHecha` (privado, al que la hace, con quién la vio).

Con señas desactivadas (valor por defecto) el juego es exactamente el actual: ningún
test ni partida de referencia cambia.

### 2.3 Ambigüedades del reglamento sobre señas

| ID | Duda | Propuesta |
|---|---|---|
| S-1 | C.VIII-2 incluye "cortar el mus" y "envidar más", pero C.VIII-4 prohíbe señar para tomar decisiones y C.VIII-3 no permite señas antes del corte | **no se implementan** esas dos señas |
| S-2 | C.VIII-3 dice "al comenzar la partida": ¿sólo la primera jugada o todas? | en todas las jugadas, sólo tras el corte |
| S-3 | "Dos reyes" con tres reyes, o "pares" con dos reyes | "dos reyes" = pareja exacta de reyes; con tres reyes se seña medias de reyes; "pares" vale para cualquier pareja |
| S-4 | Veintinueve: el reglamento no fija el momento | como treinta: sólo cuando nadie tiene juego |

## 3. Arquitectura multiagente

Un **orquestador** consulta a agentes especializados. Cada agente es una pieza pequeña
y testeable que sólo lee la observación y la memoria.

```text
                      Observation (sólo lo legítimo)
                                   │
          ┌────────────────────────┼─────────────────────────┐
          ▼                        ▼                         ▼
  CardCountingAgent        PlayerProfileAgent          ScoreAgent
  qué cartas pueden        cómo juega cada jugador     cuánto vale cada tanto
  quedar y dónde           (memoria entre partidas)    según el marcador
          │                        │                         │
          └──────────► HandInferenceAgent ◄──────────────────┘
                       P(mano de cada rival | todo lo visto)
                                   │            ▲
                    SignalAgent ───┘            │ señas vistas/interceptadas
                    cuándo señar, qué leer
                                   ▼
                          EquityAgent (decisión)
                     valor esperado de cada acción legal
                                   ▼
                            Orchestrator ──► Action + explicación
                                   │
                    después de cada partida ▼
                          LearningAgent (post-mortem)
                     analiza errores, sobre todo en derrotas
```

### 3.1 CardCountingAgent: cartas que quedan

En el Mus el conteo es más limitado que en el blackjack: **cada jugada se baraja la
baraja completa** y los descartes ajenos van boca abajo. Aun así da información útil:

- Cartas posibles para los demás = 40 − mi mano − mis descartes (mientras no se
  rebaraje el descarte, C.III-15).
- **Número de cartas que pide cada uno**: quien pide 1 suele tener jugada; quien
  pide 4, nada.
- **Declaraciones** de pares y juego (sí/no): recortan mucho las manos posibles.
- Manos enseñadas en jugadas anteriores: no sirven para contar (nueva baraja), pero
  alimentan el perfil.

Salida: el conjunto de cartas posibles y las restricciones de cada rival.

### 3.2 PlayerProfileAgent: el perfil de cada jugador

Para cada jugador, con datos de manos enseñadas:

- **Fuerza de mano** por lance, en percentil (0 = la peor posible, 1 = la mejor),
  calculada exacta sobre las 91.390 manos.
- Por lance y tramo de fuerza (mala / media / buena):
  - frecuencia de envite, de paso y de órdago;
  - **tantos envidados con buenas y con malas** (tus "piedras");
  - frecuencia de **farol** (envita con mano del 30 % peor);
  - frecuencia de **"ir de tapado"** (pasa con mano del 20 % mejor);
  - cómo responde: quiere, rechaza o sube según su fuerza.
- En el mus: con qué manos pide mus y cuántas cartas descarta.
- Sensibilidad al marcador: ¿juega distinto cuando va perdiendo?

Etiqueta legible, con nivel de confianza:

| Perfil | Señal principal |
|---|---|
| Arriesgado | envida mucho y alto, también con manos medias |
| Farolero | envida a menudo con manos malas |
| Cauto | sólo envida con manos buenas, rechaza a menudo |
| Conservador | envida poco y bajo, evita el órdago |
| De tapado | pasa con manos muy buenas para cazar al rival |
| Imprevisible | conducta poco consistente |

Estadística: conteos con **priors de Dirichlet/Beta** (una persona nueva parte del
comportamiento medio y se va separando con los datos). Se guarda por jugador entre
partidas.

### 3.3 HandInferenceAgent: intuir las cartas

Inferencia bayesiana por **Monte Carlo**:

```text
P(mano del rival | lo visto) ∝ P(mano | cartas posibles, declaraciones)        ← CardCounting
                               × Π P(cada acción observada | mano, perfil)      ← PlayerProfile
                               × P(señas interceptadas | mano)                  ← SignalAgent
```

Se muestrean manos compatibles y se ponderan por cómo de probable es que ese jugador,
con ese perfil, hubiera hecho lo que ha hecho. Ejemplo: un jugador **cauto** que envida
4 a grande hace subir mucho la probabilidad de reyes; si es **farolero**, mucho menos.

### 3.4 ScoreAgent: el marcador

No todos los tantos valen lo mismo: lo importante es **la probabilidad de ganar la
partida**. Se precalcula por simulación una tabla `P(ganar | mis tantos, sus tantos,
juegos)`, y cada resultado posible se valora por cuánto cambia esa probabilidad.

De aquí sale sola la agresividad que pides:

- Rival a 38 y yo a 20: casi cualquier tanto suyo me hace perder, así que un órdago
  con 40 % de opciones es buena jugada.
- Yo a 38 y rival a 20: no arriesgo, rechazo envites dudosos.

Además se añade un parámetro de apetito de riesgo por nivel de bot.

### 3.5 SignalAgent: señas

- **Cuándo señar**: espera al momento en que el compañero le mira y los rivales no
  (las miradas son públicas), y compara la ventaja de que el compañero sepa su jugada
  con el riesgo de que algún rival se gire a tiempo.
- Las miradas son aleatorias (IA-2): el agente no elige dónde mirar, pero sí aprovecha
  el momento en que le miran.
- **Leer al compañero**: incorpora sus señas vistas a la inferencia (son verdad por
  reglamento).
- **Aprovechar intercepciones**: una seña rival interceptada es información cierta.
- Aprende con qué frecuencia mira cada rival a cada jugador.

### 3.6 EquityAgent: decidir

Para cada acción legal estima su **valor esperado en probabilidad de ganar la
partida**:

1. Muestrea manos de los rivales (y del compañero) desde las inferencias.
2. Simula la respuesta de los rivales con su perfil.
3. Resuelve el lance con los evaluadores exactos del motor (`RulesEngine`, sin tocar
   la partida real).

Elige la de mayor valor, con un pequeño término de exploración para no ser predecible.
Devuelve también una **explicación** (agentes consultados, probabilidades y por qué),
útil para el modo entrenamiento y para la defensa.

### 3.7 LearningAgent: aprender de las derrotas sin repetir errores

Matiz importante: en el Mus se puede perder jugando bien (mala suerte) y ganar jugando
mal. **Si castigáramos todo lo que lleva a perder, la IA aprendería supersticiones.**
Por eso el aprendizaje mide la **calidad de la decisión**, no el resultado:

1. Al terminar cada partida, sobre todo si la pierde, revisa cada decisión con la
   información que se enseñó después (las manos reales de cada jugada).
2. Calcula el **arrepentimiento** (*regret*): cuánto mejor habría sido la mejor acción
   frente a la elegida, con lo que realmente había en la mesa.
3. Guarda los errores en una **memoria de experiencia**, por tipo de situación: lance,
   fuerza de mi mano, posición, marcador, perfil del rival y estado del envite.
4. Ajusta las decisiones futuras en esas situaciones (actualización tipo
   Monte Carlo / *Q-learning* con peso mayor en partidas perdidas, como pides).
5. Corrige también los perfiles cuando el rival hizo algo que el modelo no esperaba
   ("este jugador no faroleaba y acaba de hacerlo").

Se demuestra con **curvas de aprendizaje**: porcentaje de victorias contra el mismo
rival a lo largo de N partidas, con la memoria activada frente a desactivada.

---

## 4. Niveles

| Nivel | Agentes | Comportamiento |
|---|---|---|
| **Sencillo** | heurísticas de fuerza de mano + ruido | comprensible, comete errores razonables |
| **Medio** | + conteo, marcador, perfiles básicos | se adapta al rival y al marcador |
| **Profesional** | todos + inferencia, señas y aprendizaje | aprende partida a partida |

La diferencia entre niveles se mide en el torneo (Elo y porcentaje de victorias), no se
supone.

---

## 5. Plataforma de bots (requisitos 2.x y 4.x)

```python
from mus_engine.bots import Bot, Observation, Action


class MiBot(Bot):
    name = "mi-bot"

    def decide(self, observation: Observation) -> Action: ...

    # opcionales
    def on_hand_end(self, observation: Observation) -> None: ...  # manos enseñadas
    def on_game_end(self, observation: Observation) -> None: ...  # aprender
```

- **Registro**: un bot nuevo es un archivo en `bots/` (PR), sin tocar el motor.
- **Tests de conformidad (2.2)**: juega N partidas sin acciones ilegales, sin colgarse
  (tiempo límite por decisión), sin excepciones, y no recibe nunca `GameState`.
- **Torneo (4.1)**: todas las parejas de bots contra todas, varias semillas y
  posiciones. Si un bot falla, se cuelga o hace algo ilegal, **su pareja pierde esa
  partida** y el torneo sigue.
- **Clasificación (4.2)**: una GitHub Action ejecuta el torneo y publica la tabla en
  GitHub Pages.

---

## 5bis. Aplicación web, usuarios y datos

Decisión IA-3: **los usuarios se registran y se guardan todos sus datos**; lo aprendido
de cada persona vive en su cuenta.

Consecuencia de diseño: **el motor tiene que ejecutarse en un servidor**. Si corriera
en el navegador, las manos de todos estarían en la memoria del navegador y cualquiera
podría verlas con las herramientas del desarrollador (requisito 5.1.1 de la práctica:
no revelar información secreta).

```text
Navegador (JS)                     Servidor (Python)                     Base de datos
mesa, avatares, miradas  ◄──WS──►  FastAPI: cuentas, partidas,     ◄──►  PostgreSQL
sólo recibe su observación         mus_engine, bots, aprendizaje          usuarios, partidas,
                                                                          perfiles, memoria IA
```

Qué se guarda por usuario:

- cuenta: nombre de usuario, contraseña con hash (nunca en claro), fecha de alta;
- partidas completas (registro de eventos, que permite el replay);
- perfil de juego calculado por la IA y su evolución;
- estadísticas (victorias, lances, envites…).

Al guardar datos personales:

- pedir los mínimos;
- consentimiento al registrarse;
- opción de borrar la cuenta y todos sus datos.

Las memorias de los bots (lo que aprenden jugando entre ellos o contra cualquiera) se
guardan en la misma base de datos.

## 5ter. Modos de juego, señas y avatares

### Modos de juego

Al crear una partida se elige:

| Modo | Pareja 1 | Pareja 2 |
|---|---|---|
| Solo con bot | tú + bot compañero | 2 bots |
| Pareja humana | 2 personas | 2 bots |
| Cuatro personas | 2 personas | 2 personas (sin bots) |

Y además, **con señas** o **sin señas** (IA-9). Sin señas es el juego del reglamento
sin comunicación entre compañeros (`signals_enabled=False`, ya implementado).

Cada asiento es una persona o un bot: el motor no distingue entre ellos. Las partidas
con varias personas necesitan salas (crear, invitar, unirse) y conexión en tiempo real
(WebSocket), dentro de la fase web.

### Avatares (IA-10)

- **Caricaturas divertidas** de personajes populares, con **apodo inventado**: por
  ejemplo, una caricatura reconocible de una aristócrata televisiva se llama
  "La Marquesa". Nunca se usa el nombre real ni el de ningún programa.
- Cada jugador **elige su avatar** al registrarse o al empezar una partida; los bots
  también tienen el suyo.
- Cada avatar tiene **frases propias**, originales y en su estilo (no citas reales), que
  dice en momentos de la partida: al echar un órdago, al ganar o perder un lance, al
  ver una seña, al cortar el mus…
- La personalidad del avatar de un bot coincide con su estilo de juego (p. ej. una
  conservadora, un farolero, una arriesgada), así el jugador "lee" al rival también
  por su personaje.
- La cara de cada avatar se anima según las miradas del motor (§2.2): gira hacia el
  compañero, un rival o la mesa.
- Los avatares son un **paquete de datos** (imagen, apodo, frases, estilo) separado del
  código: se pueden añadir o cambiar sin programar.
- Criterios: tono amable (nada humillante ni de mal gusto), frases originales y un
  aviso visible de que son parodias sin relación con las personas reales. La ley
  permite la caricatura de personajes públicos "de acuerdo con el uso social"
  (art. 8.2.b de la LO 1/1982).

## 6. Plan por fases

Se mantiene el método anterior: implementación, tests, documentación y revisión antes
de pasar a la siguiente.

| Fase | Contenido | Requisito |
|---|---|---|
| A | Señas en el motor (C.VIII) ✅ | base de la IA |
| B | API de bots, bots base (aleatorio y heurístico sencillo), tests de conformidad, torneo ✅ | 2.1, 2.2, 4.1, 3.1 |
| C | Web (FastAPI + WebSocket + JS): C1 cuentas, salas de los 3 modos, mesa con avatares, señas y frases ✅ (`docs/web.md`); C2 publicación ✅ (`docs/deploy.md`) | 1.2, 1.3 |
| D | Fuerza de manos, CardCounting y ScoreAgent; bot **Medio** ✅ (`docs/ai.md`) | 3.1 |
| E | Perfiles de jugador y memoria persistente ✅ (`docs/ai.md`) | 3.1 |
| F | Inferencia de manos, EquityAgent, orquestador, explicaciones | 3.1 |
| G | Señas: SignalAgent | 3.1 |
| H | Aprendizaje de derrotas y curvas de aprendizaje; bot **Profesional** | 3.1 |
| I | Clasificación automática publicada; documentación MkDocs/ReadTheDocs con tutorial; LICENSE | 4.2, 2.3, C.1 |

Propongo B y C pronto porque el **punto de control** (unas 3 semanas antes de la
entrega) pide las secciones 1 y 2.

---

## 7. Decisiones

Aprobadas:

| ID | Decisión |
|---|---|
| IA-1 | Señas siempre verdaderas (C.VIII-4) |
| IA-2 | Quién ve una seña depende de las miradas de los avatares (§2.2), no de probabilidades fijas |
| IA-3 | Usuarios registrados; todos sus datos y lo aprendido se guardan en base de datos (§5bis) |
| IA-4 | Orden de fases: señas → API de bots y torneo → web → agentes |
| IA-5 | "Piedras" = tantos; amarraco = 5 tantos (D-19) |
| S-1 | No se implementan las señas "cortar el mus" ni "envidar más" |
| S-2 | Señas en todas las jugadas, sólo después del corte |
| S-3 | "Dos reyes" = pareja exacta de reyes; con tres, medias de reyes; "pares" vale para cualquier pareja |
| S-4 | Veintinueve, como treinta: sólo cuando nadie tiene juego |
| IA-6 | Web: FastAPI + JavaScript + PostgreSQL |
| IA-7 | Alojamiento en un servicio con plan gratuito (se concreta en la fase web) |
| IA-8 | Licencia MIT |
| IA-9 | Cada partida se juega con o sin señas, a elección |
| IA-10 | Avatares: caricaturas divertidas con apodo inventado, elegibles, con frases originales (§5ter) |
| IA-11 | Modos: tú + bot contra 2 bots, 2 personas contra 2 bots, 4 personas (§5ter) |
