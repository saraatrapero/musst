# La web de MUS.ST (`mus_web`)

Fase C1 del plan (`docs/ai-design.md` §5bis y §5ter): cuentas, salas para los tres modos
y la mesa en el navegador con avatares, miradas, señas y frases.

```bash
python -m pip install -e ".[web]"
python -m mus_web                     # http://127.0.0.1:8000
```

Variables de entorno: `MUSST_DATABASE_URL` (por defecto `sqlite:///musst.db`; en
producción, PostgreSQL), `MUSST_SECURE=1` (cookies sólo por HTTPS), `HOST` y `PORT`.

## Arquitectura

```text
Navegador (static/app.js)        Servidor (FastAPI)                       Base de datos
pantallas de acceso, lobby  ◄─►  REST  /api/...   cuentas, salas     ◄─►  users, login_sessions,
y mesa; sólo recibe su           WS    /ws/rooms/{código}  la mesa        games, game_seats
observación                      Hub: una tarea asyncio por sala
                                 Room: asientos, motor, bots, frases
```

| Módulo | Qué hace |
|---|---|
| `app.py` | API REST, WebSocket, cabeceras de seguridad, `Hub` (salas activas y bucle de cada partida) |
| `rooms.py` | `Room`: modos, asientos, arranque, turnos de personas y bots, reloj de miradas. Síncrono y determinista |
| `codec.py` | traducción motor ⇄ JSON; entrada estricta (`CodecError`) |
| `phrases.py` | qué dicen los bots y cuándo, sólo a partir de eventos públicos |
| `avatars_pack.py` + `avatars/pack.json` | los 8 personajes: apodo, estilo, color y frases |
| `db.py` | modelos SQLAlchemy |
| `security.py` | contraseñas (scrypt), tokens de sesión, validación de credenciales |
| `static/` | `index.html`, `app.js` (sin compilación), `style.css`, `avatars/<id>/<pose>.png` |

### Bucle de una sala

Al empezar, `Hub.launch` crea una tarea que, hasta el final de la partida:

1. si le toca a un bot, espera `bot_delay` (o `hand_pause` si acaba de empezar una mano,
   para ver las cartas enseñadas), deja hacer señas a los bots y juega el bot;
2. si le toca a una persona, espera a su acción; con señas, cada `tick_interval`
   segundos da un «momento» del reloj (`Game.tick()`): las miradas cambian y los bots
   pueden hacer señas;
3. tras cada paso envía a cada persona conectada **su** vista;
4. al terminar guarda la partida (`games` + `game_seats`) y actualiza las estadísticas.

## Modos

| `mode` | Personas (asientos) | Bots |
|---|---|---|
| `con_bot` | 0 | 1, 2, 3 (el 2 es tu compañero) |
| `dos_humanos` | 0 y 2 (pareja) | 1 y 3 |
| `cuatro` | 0, 1, 2 y 3 | ninguno |

Quien crea la sala se sienta en el asiento 0 y es quien la empieza. El resto se une con
el código de 6 caracteres (sin O/0/I/1 para que no haya confusiones). Al crear la sala se
elige el nivel de los bots: `medio` (por defecto) o `sencillo`.

## Protocolo de la mesa (WebSocket)

El servidor envía, tras cada cambio:

```json
{
  "room": {"code": "K7P2QX", "mode": "con_bot", "signals": true, "seats": [...], ...},
  "seat": 0,
  "phrases": [{"id": 12, "seat": 1, "text": "¡Órdago! De peores islas he salido."}],
  "game": { ... observación del asiento 0: codec.observation_to_json ... }
}
```

El navegador envía `{"action": {...}}` con una de estas acciones:

```json
{"type": "mus"}  {"type": "cut"}  {"type": "pass"}  {"type": "accept"}  {"type": "reject"}
{"type": "ordago"}  {"type": "bet", "amount": 2}  {"type": "raise", "amount": 2}
{"type": "discard", "cards": ["12O", "1B"]}  {"type": "signal", "signal": "duples"}
```

Cualquier otra cosa (campos de más, tipos raros, importes fuera de 1..1000, más de 4
naipes, mensajes de más de 4 KB) se rechaza con `{"error": "..."}` sin tocar la
partida; y aun así la última palabra la tiene el motor, que vuelve a validar.

## API REST

| Método y ruta | Uso |
|---|---|
| `GET /api/avatars` | personajes (sin frases) y aviso de parodia; `images`: poses dibujadas disponibles |
| `POST /api/register` | `{username, password, avatar, consent}`; abre sesión |
| `POST /api/login`, `POST /api/logout` | sesión por cookie |
| `GET /api/me`, `PUT /api/me/avatar` | perfil |
| `GET /api/me/games` | últimas 50 partidas |
| `GET /api/me/profile` | cómo juegas según la IA: estilo, confianza y frecuencias (Fase E) |
| `GET /api/me/export` | todos mis datos en JSON, perfil incluido (derecho de acceso) |
| `DELETE /api/me` | `{password}`: borra la cuenta, sus sesiones y su participación; su nombre se sustituye por «(cuenta borrada)» en los registros guardados |
| `POST /api/rooms` | `{mode, signals, phrases, level}` (`level`: `medio` o `sencillo`) |
| `GET /api/rooms/{código}` · `POST .../join` · `POST .../leave` · `POST .../start` | salas |

## Seguridad

- **Cartas**: el servidor nunca envía el `GameState`; sólo `Observation` (lista blanca) y
  eventos ya filtrados por visibilidad. Hay un test que comprueba, con cuatro personas,
  que cada una recibe sólo sus naipes.
- **Contraseñas**: `scrypt` con sal aleatoria; nunca en claro.
- **Sesiones**: cookie `HttpOnly`, `SameSite=Lax` (y `Secure` con `MUSST_SECURE=1`); en
  la base de datos sólo se guarda el SHA-256 del token. Caducan a los 30 días.
- **Fuerza bruta**: tras 5 intentos fallidos, el usuario queda bloqueado 5 minutos.
- **WebSocket**: exige sesión, estar sentado en la sala y un `Origin` del mismo sitio
  (evita que otra web abra la mesa en nombre del usuario).
- **XSS**: el cliente construye el DOM con `textContent`; la cabecera CSP sólo permite
  scripts y estilos del propio servidor; `X-Frame-Options: DENY`.
- **Datos personales**: consentimiento al registrarse, exportación y borrado.

## Avatares y frases

Los 8 personajes viven en `avatars/pack.json` (datos, no código). Las frases se eligen
al azar entre las de cada momento (`pide_mus`, `corta_mus`, `pasa`, `envida`, `ordago`,
`acepta`, `rechaza`, `gana_lance`, `pierde_lance`, `gana_partida`, `pierde_partida`,
`revela_31`). Sólo hablan los bots, como mucho dos por paso, y **sólo reaccionan a
hechos públicos**: una frase nunca da pistas sobre cartas ocultas. Se desactivan al
crear la sala o con «Silenciar frases» en la mesa.

Mientras no haya dibujos, la mesa pinta una cara provisional cuyas pupilas giran hacia
donde mira el jugador (compañero, rival o mesa) y que sonríe o se fastidia según el
último lance. Para poner las caricaturas: `static/avatars/LEEME.md`.

## Despliegue (C2)

Guía paso a paso en [`deploy.md`](deploy.md): Render con el `render.yaml` de la raíz
(web y PostgreSQL gratuitos). `GET /healthz` comprueba servidor y base de datos.

## Tests

`tests/web/` usa SQLite en memoria. Para probar contra PostgreSQL (se vacía la base de
datos):

```bash
MUSST_TEST_DATABASE_URL=postgresql+psycopg://musst@127.0.0.1:5432/musst python -m pytest tests/web
```

## Límites conocidos (C1)

- Si una persona se desconecta, su asiento espera a que vuelva (no hay tiempo límite
  ni sustitución por un bot todavía).
- Las salas no sobreviven a un reinicio del servidor (las partidas terminadas sí).
- Sin espectadores: sólo quien está sentado recibe la mesa.

## Reparto, resumen y naipes

- Cada jugada empieza con el botón **Repartir nueva jugada**: el servidor
  espera el mensaje `{"deal": n}` antes de que hablen los bots, y la web
  anima el reparto carta a carta desde la baraja de quien reparte (a la
  izquierda de la mano).
- Al acabar la jugada se explica la puntuación lance a lance (Grande,
  Chica, Pares, Juego) y después el resultado con amarracos y piedras.
- Los naipes se dibujan en SVG (`static/cards.js`). Para usar imágenes de
  una baraja real basta con dejar `static/cards/<código>.png` (ver
  `static/cards/LEEME.md`); `/api/deck` indica cuáles hay.
- Las frases de los avatares se leen en voz alta con la síntesis de voz
  del navegador (botón 🔊 para activarla o silenciarla).

## Reglas de casa en la web

La web juega con una opción de `GameConfig` que pidió la usuaria (el motor, por
defecto, sigue el reglamento):

- Las señas, como en el reglamento: sólo se puede señar lo que se lleva (no hay señas
  falsas; `false_signals` existe en el motor pero la web no lo activa).
- `negadas_at_end=True`: las negadas y los envites no queridos no se suman en el
  acto, sino en el recuento final en orden de lances (grande, chica, pares, juego).
  Gana la primera pareja que llega al tanteo en ese orden y siempre se ven las cartas
  al acabar la jugada.

## Torneo, compañero y meta (ideas de PC Mus)

- **Torneo (3 rondas)**: cuartos (bots sencillos), semifinal y gran final (bots
  medios) contra tres parejas distintas. Si se pierde una ronda, el torneo acaba.
  El progreso se guarda en el navegador (`localStorage`, clave `torneo`); cada
  partida es una sala normal con `tournament_round` 1-3 y los rivales elegidos.
- **Elegir compañero** (y, en el torneo, los rivales): `partner` y `rivals` al crear
  la sala, sólo en el modo con un humano. Cada personaje tiene una frase de muestra
  (`sample`) para escuchar su voz.
- **Meta del juego**: a 40 o a 30 tantos (`target`).
- En la mesa, «Faltan N» en el marcador y el botón «🤫 Echar seña» (se abre solo
  cuando tu compañero te mira).
- **Se canta en voz alta**: cada jugador (bots y personas) dice lo que hace con su
  voz: «Mus», «No hay mus», «Dame dos», «Paso», «Envido», «Quiero», «No quiero»,
  «¡Órdago!», y «Pares sí/no» y «Juego sí/no» en orden desde la mano. Los bots
  piensan 1,3 s por jugada para que dé tiempo a oírlo.
- Al acabar la jugada, «Jugada terminada» al menos 2,5 s (y hasta que terminen de
  hablar) antes del resumen.
- Si tu compañero contesta un envite antes que tú, un aviso lo explica: con que
  quiera uno de la pareja basta, así que a ti ya no te pregunta.

## Administración

Son administradores los usuarios de `MUSST_ADMINS` (en Render, `render.yaml`: `sara`)
y los que otro administrador nombre desde el panel (tabla `admins`). En el lobby ven
«Abrir el panel de administración», con cuatro pestañas:

- **Resumen**: usuarios (nuevos y activos en 7 días), partidas (total, semana, hoy),
  partidas en juego, personas conectadas y sesiones abiertas; gráficas de partidas y
  altas por día (30 días); reparto por modo, con o sin señas y estilo de juego según
  la IA; y los mejores jugadores.
- **Usuarios**: buscador, tabla con partidas, % ganadas, estilo, última actividad y
  alta, y descarga en CSV. Por usuario:
  - **Ver**: su perfil de juego y sus últimas 20 partidas; cerrar sus sesiones.
  - **Editar**: nombre, avatar, contraseña nueva (cierra sus sesiones) y permisos de
    administrador.
  - **Borrar**: como si borrara la cuenta su dueño (su nombre sale de los registros).
- **Partidas**: las últimas 20, con quién jugó en cada pareja y quién ganó.
- **Bots**: cómo les va a los bots contra personas (porcentaje con intervalo de
  Wilson del 95 %).

Límites: nadie se borra ni se quita sus propios permisos desde el panel, y a un
administrador de `MUSST_ADMINS` no se le cambia el nombre, ni se le quitan los
permisos, ni se le borra (se hace en la configuración).

API: `GET /api/admin/stats`, `GET /api/admin/users`, `GET|PATCH|DELETE
/api/admin/users/{id}`, `POST /api/admin/users/{id}/logout` y `POST
/api/admin/password`.
