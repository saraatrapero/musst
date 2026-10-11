# Diseño de la IA de MUS.ST y de la plataforma de bots

> Estado: **PROPUESTA PARA REVISIÓN**. Nada de esto está implementado todavía.
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
| 2.1 | API pública de bots sin tocar el juego | 1,0 | pendiente |
| 2.2 | Tests automáticos para bots nuevos | 0,5 | pendiente |
| 2.3 | Documentación online con referencia del API y tutorial | 0,5 | pendiente (hay docs en el repo, no publicadas) |
| 3.1 | Bot propio (0,5 × dificultad 5 = 2,5 por bot) | — | pendiente |
| 3.2 / 3.3 | Bots para/de otros equipos por PR | — | fuera de este diseño |
| 4.1 | Torneo robusto (un bot que falla pierde, el torneo sigue) | 1,0 | pendiente |
| 4.2 | Clasificación publicada y actualizada automáticamente | 0,5 | pendiente |
| C.1 | Repo ordenado: README, **LICENSE**, .gitignore | 0,5 | falta LICENSE |
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

## 2. Señas (ampliación del motor)

Hoy las señas están fuera del motor (`docs/rules.md` §3). Para tu idea hay que
modelarlas, y el reglamento las regula con detalle (C.VIII):

| Regla | Cita | Cómo se modela |
|---|---|---|
| Sólo las señas oficiales | C.VIII-1, C.VIII-2 | `Sena` enum: dos reyes, dos ases, pares, medias de reyes, medias de ases, medias, duples, juego, treinta y una, treinta, veintinueve, ciego, cortar el mus, envidar más |
| No antes de cortar el mus | C.VIII-3 | sólo en fases posteriores al corte |
| Sólo para transmitir la jugada que se tiene | C.VIII-4 | **el motor sólo permite señas verdaderas** (no se puede mentir) |
| Medias que no sean de reyes, después de grande; treinta, tras "juego no" | C.VIII-5, C.VIII-2 | restricciones de momento |
| Nada de señas parciales | C.VIII-6 | duples se señalan como duples |
| El rival no está obligado a confirmar | C.VIII-7 | la seña vista no da certeza de nada más |

**Ver o no ver la seña** (tu regla de ventaja):

- `SenaAction(sena)` la puede hacer cualquier jugador, no sólo el que tiene el turno,
  una vez por seña y jugada.
- El motor decide con su generador determinista si **el compañero la ve**
  (probabilidad `p_ver`) y si **cada rival la intercepta** (probabilidad
  `p_interceptar`), según parámetros de configuración (habilidad para disimular y
  atención de cada jugador).
- Resultado en eventos **privados**: el compañero recibe `SenaVista`; el rival que la
  intercepta recibe `SenaInterceptada`. Quien hace la seña **no sabe** quién la ha visto.
- Para personas en la web: botón "hacer seña" y aviso cuando ves una.

Esto mantiene todas las garantías del motor: determinista, legal si y sólo si figura
en las acciones legales, sin fugas.

---

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

- **Cuándo señar**: compara la ventaja de que el compañero sepa mi jugada con el riesgo
  de que me la intercepten (según la atención observada de cada rival).
- **Leer al compañero**: incorpora sus señas vistas a la inferencia (son verdad por
  reglamento).
- **Aprovechar intercepciones**: una seña rival interceptada es información cierta.
- Aprende la tasa real de intercepción de cada rival.

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
    def on_hand_end(self, observation: Observation) -> None: ...   # manos enseñadas
    def on_game_end(self, observation: Observation) -> None: ...   # aprender
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

## 6. Plan por fases

Se mantiene el método anterior: implementación, tests, documentación y revisión antes
de pasar a la siguiente.

| Fase | Contenido | Requisito |
|---|---|---|
| A | Señas en el motor (C.VIII) | base de la IA |
| B | API de bots, bots base (aleatorio y heurístico sencillo), tests de conformidad, torneo | 2.1, 2.2, 4.1, 3.1 |
| C | Interfaz web (Streamlit): persona + bot compañero contra 2 bots; publicación | 1.2, 1.3 |
| D | Fuerza de manos, CardCounting y ScoreAgent; bot **Medio** | 3.1 |
| E | Perfiles de jugador y memoria persistente | 3.1 |
| F | Inferencia de manos, EquityAgent, orquestador, explicaciones | 3.1 |
| G | Señas: SignalAgent | 3.1 |
| H | Aprendizaje de derrotas y curvas de aprendizaje; bot **Profesional** | 3.1 |
| I | Clasificación automática publicada; documentación MkDocs/ReadTheDocs con tutorial; LICENSE | 4.2, 2.3, C.1 |

Propongo B y C pronto porque el **punto de control** (unas 3 semanas antes de la
entrega) pide las secciones 1 y 2.

---

## 7. Decisiones que necesito

| ID | Pregunta | Propuesta |
|---|---|---|
| IA-1 | ¿Las señas siempre verdaderas (C.VIII-4) o se permite señar en falso como farol? | Verdaderas, como dice el reglamento |
| IA-2 | Probabilidades por defecto de ver e interceptar una seña | compañero 80 %, cada rival 15 %; ajustables por jugador |
| IA-3 | ¿Dónde se guarda lo aprendido? | archivos JSON versionados por bot en `data/` (fáciles de inspeccionar en la defensa) |
| IA-4 | ¿La memoria de un bot se reinicia en cada torneo? | No: es lo que demuestra el aprendizaje; el torneo oficial se repite también "sin memoria" para comparar |
| IA-5 | "Piedras" | = tantos; amarraco = 5 tantos (D-19) |
| IA-6 | Interfaz web | Streamlit (todo en Python, recomendado en la práctica) |
| IA-7 | Orden de fases | A → B → C → D … (checkpoint primero) |
| IA-8 | Licencia del repositorio | MIT |
