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
el código de 6 caracteres (sin O/0/I/1 para que no haya confusiones). Por ahora los bots
de la web son el bot `sencillo`; los niveles llegarán con las fases D–H.

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
| `GET /api/me/export` | todos mis datos en JSON (derecho de acceso) |
| `DELETE /api/me` | `{password}`: borra la cuenta, sus sesiones y su participación; su nombre se sustituye por «(cuenta borrada)» en los registros guardados |
| `POST /api/rooms` | `{mode, signals, phrases}` |
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
