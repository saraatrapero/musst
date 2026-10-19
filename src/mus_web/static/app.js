"use strict";
// MUS.ST: cliente sin compilación. Todo el DOM se construye con textContent (sin
// innerHTML) para que ningún nombre de usuario pueda inyectar código.

const state = { me: null, avatars: [], notice: "", room: null, view: null, ws: null, selected: new Set(), bubbles: {}, lastPhrase: 0, quiet: false };

const SUITS = { O: "oros", C: "copas", E: "espadas", B: "bastos" };
const FIGURES = { 1: "As", 10: "Sota", 11: "Caballo", 12: "Rey" };
const LANCES = { grande: "Grande", chica: "Chica", pares: "Pares", juego: "Juego", punto: "Punto" };
const PHASES = { mus_decision: "¿Mus?", discard: "Descartes", lance: "Lances", game_over: "Fin de la partida" };
const MODES = { con_bot: "Tú + bot contra 2 bots", dos_humanos: "2 personas contra 2 bots", cuatro: "4 personas" };
const SIGNALS = {
  dos_reyes: "Dos reyes", dos_ases: "Dos ases", pares: "Pares", medias_reyes: "Tres reyes",
  medias_ases: "Tres ases", medias: "Medias", duples: "Duples", juego: "Juego",
  treinta_y_una: "La 31", treinta: "Treinta", veintinueve: "29", ciego: "Ciego (nada)",
};
const ACTIONS = { mus: "Mus", cut: "Corto", pass: "Paso", accept: "Quiero", reject: "No quiero", ordago: "¡Órdago!", discard: "Descartar" };

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
}

async function api(method, path, body) {
  const res = await fetch(path, {
    method, credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Error " + res.status);
  return data;
}

function mount(...nodes) { const app = document.getElementById("app"); app.replaceChildren(...nodes); }
function avatarById(id) { return state.avatars.find((a) => a.id === id) || state.avatars[0]; }

// --- Caras ------------------------------------------------------------------------------
// Cara provisional en SVG; si existe la caricatura (static/avatars/<id>/<pose>.png) se usa.
// (dx, dy): hacia dónde mira, en la pantalla. mood: "", "contento", "fastidiado".
function face(avatar, dx = 0, dy = 0, mood = "") {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 64 64");
  svg.setAttribute("class", "face");
  const add = (name, attrs) => { const e = document.createElementNS(ns, name); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); svg.append(e); return e; };
  add("circle", { cx: 32, cy: 32, r: 30, fill: avatar.color, stroke: "#222", "stroke-width": 2 });
  for (const ex of [22, 42]) {
    add("circle", { cx: ex, cy: 27, r: 7, fill: "#fff", stroke: "#222" });
    add("circle", { cx: ex + dx * 3.5, cy: 27 + dy * 3.5, r: 3, fill: "#222" });
  }
  const mouth = mood === "contento" ? "M20 42 Q32 54 44 42" : mood === "fastidiado" ? "M20 48 Q32 38 44 48" : "M22 45 Q32 50 42 45";
  add("path", { d: mouth, stroke: "#222", "stroke-width": 3, fill: "none", "stroke-linecap": "round" });
  const wrap = h("span", { class: "face", title: avatar.nickname });
  wrap.append(svg);
  const pose = mood || (Math.abs(dx) > Math.abs(dy) ? (dx < 0 ? "izquierda" : "derecha") : dy < 0 ? "enfrente" : "frente");
  const known = avatarById(avatar.id);
  const images = (known && known.images) || [];
  const file = images.includes(pose) ? pose : images.includes("frente") ? "frente" : null;
  if (file) wrap.replaceChildren(h("img", { src: `/static/avatars/${avatar.id}/${file}.png`, alt: avatar.nickname }));
  return wrap;
}

// --- Pantallas: acceso -------------------------------------------------------------------

function avatarPicker(selectedId, onPick) {
  const grid = h("div", { class: "avatars" });
  for (const a of state.avatars) {
    const btn = h("button", { type: "button", class: "avatar-choice" + (a.id === selectedId ? " selected" : ""), "data-avatar": a.id },
      face(a), a.nickname, h("small", {}, a.style));
    btn.addEventListener("click", () => {
      for (const b of grid.children) b.classList.toggle("selected", b === btn);
      onPick(a.id);
    });
    grid.append(btn);
  }
  return grid;
}

function authScreen(mode = "login", chosen = state.avatars[0]?.id) {
  const err = h("p", { class: "error" });
  const user = h("input", { type: "text", autocomplete: "username", maxlength: 24 });
  const pass = h("input", { type: "password", autocomplete: mode === "login" ? "current-password" : "new-password", maxlength: 128 });
  const consent = h("input", { type: "checkbox" });
  const submit = async (ev) => {
    ev.preventDefault();
    try {
      state.me = mode === "login"
        ? await api("POST", "/api/login", { username: user.value, password: pass.value })
        : await api("POST", "/api/register", { username: user.value, password: pass.value, avatar: chosen, consent: consent.checked });
      lobby();
    } catch (e) { err.textContent = e.message; }
  };
  const form = h("form", { class: "panel", onsubmit: submit },
    h("h2", {}, mode === "login" ? "Entrar" : "Crear cuenta"),
    h("label", {}, "Usuario"), user, h("label", {}, "Contraseña"), pass,
    mode === "register" && [
      h("label", {}, "Elige tu avatar"),
      avatarPicker(chosen, (id) => { chosen = id; }),
      h("label", { class: "check" }, consent, "Acepto que MUS.ST guarde mi cuenta, mis partidas y mis estadísticas para jugar y para la práctica de IA. Puedo descargarlas o borrarlas cuando quiera."),
    ],
    err,
    h("button", { type: "submit" }, mode === "login" ? "Entrar" : "Registrarme"),
    h("button", { type: "button", class: "secondary", onclick: () => authScreen(mode === "login" ? "register" : "login") },
      mode === "login" ? "No tengo cuenta" : "Ya tengo cuenta"));
  mount(form);
  renderWho();
}

function renderWho() {
  const who = document.getElementById("whoami");
  if (!state.me) { who.replaceChildren(); return; }
  who.replaceChildren(state.me.username, " ",
    h("button", { class: "secondary", onclick: async () => { await api("POST", "/api/logout"); state.me = null; closeSocket(); authScreen(); } }, "Salir"));
}

// --- Pantallas: lobby ----------------------------------------------------------------------

async function lobby() {
  closeSocket();
  try { state.me = await api("GET", "/api/me"); } catch (e) { return authScreen(); }
  renderWho();
  const err = h("p", { class: "error" });
  const mode = h("select", {}, Object.entries(MODES).map(([k, v]) => h("option", { value: k }, v)));
  const signals = h("input", { type: "checkbox" });
  const phrases = h("input", { type: "checkbox", checked: true });
  const level = h("select", {}, h("option", { value: "medio" }, "Medio: cuenta cartas y mira el marcador"), h("option", { value: "sencillo" }, "Sencillo: para empezar"));
  const code = h("input", { type: "text", maxlength: 6, placeholder: "ABC234" });
  const games = h("tbody");
  const profileBox = h("div", { class: "profile" }, h("p", { class: "muted" }, "Calculando tu estilo…"));
  const createButton = h("button", { onclick: () => create() }, "Jugar");
  mode.addEventListener("change", () => { createButton.textContent = mode.value === "con_bot" ? "Jugar" : "Crear sala"; });
  const create = async () => {
    try {
      const room = await api("POST", "/api/rooms", { mode: mode.value, signals: signals.checked, phrases: phrases.checked, level: level.value });
      // Tú + bot: no hay nadie a quien esperar, la partida empieza ya.
      if (room.mode === "con_bot") await api("POST", `/api/rooms/${room.code}/start`);
      enterRoom(room);
    } catch (e) { err.textContent = e.message; }
  };
  const join = async () => {
    try { enterRoom(await api("POST", `/api/rooms/${encodeURIComponent(code.value.trim().toUpperCase())}/join`)); }
    catch (e) { err.textContent = e.message; }
  };
  const me = state.me;
  mount(
    h("div", { class: "grid2" },
      h("section", { class: "panel" },
        h("h2", {}, "Nueva partida"),
        h("label", {}, "Modo"), mode,
        h("label", { class: "check" }, signals, "Con señas (los compañeros se pueden pasar señas… si nadie más mira)"),
        h("label", {}, "Nivel de los bots"), level,
        h("label", { class: "check" }, phrases, "Los bots dicen frases"),
        createButton,
        h("h3", {}, "Unirse con un código"), code, h("button", { onclick: join }, "Unirme"), err),
      h("section", { class: "panel" },
        h("h2", {}, "Mi perfil"),
        face(avatarById(me.avatar)),
        h("p", {}, `${me.games_played} partidas · ${me.games_won} ganadas`),
        profileBox,
        h("label", {}, "Cambiar de avatar"),
        avatarPicker(me.avatar, async (id) => { state.me = await api("PUT", "/api/me/avatar", { avatar: id }); lobby(); }),
        h("button", { class: "secondary", onclick: exportData }, "Descargar mis datos"),
        h("button", { class: "danger", onclick: deleteAccount }, "Borrar mi cuenta"))),
    h("section", { class: "panel" }, h("h2", {}, "Mis últimas partidas"),
      h("table", { class: "list" }, h("thead", {}, h("tr", {}, h("th", {}, "Fecha"), h("th", {}, "Modo"), h("th", {}, "Señas"), h("th", {}, "Resultado"), h("th", {}, "Tantos"))), games)));
  try {
    const p = await api("GET", "/api/me/profile");
    const pct = (x) => `${Math.round(x * 100)} %`;
    profileBox.replaceChildren(...[
      h("p", {}, "Tu estilo según la IA: ", h("b", {}, p.style), p.decisions ? ` (confianza ${pct(p.confidence)})` : ""),
      p.decisions >= 8 && h("ul", { class: "muted" },
        h("li", {}, `Envidas en ${pct(p.bet_rate)} de las ocasiones; órdago en ${pct(p.ordago_rate)}`),
        h("li", {}, `Quieres ${pct(p.accept_rate)} de los envites y ${pct(p.accept_ordago_rate)} de los órdagos`),
        h("li", {}, `Farol (envidar con mano mala): ${pct(p.bluff_rate)} · Ir de tapado: ${pct(p.slowplay_rate)}`),
        h("li", {}, `Cuando vas perdiendo envidas ${pct(p.bet_rate_losing)}; si no, ${pct(p.bet_rate_even)}`)),
      p.decisions < 8 && h("p", { class: "muted" }, "Juega unas partidas y la IA aprenderá cómo juegas."),
    ].filter(Boolean));
  } catch (e) { profileBox.replaceChildren(); }
  try {
    for (const g of await api("GET", "/api/me/games")) {
      games.append(h("tr", {}, h("td", {}, new Date(g.finished_at + "Z").toLocaleString()), h("td", {}, MODES[g.mode] || g.mode),
        h("td", {}, g.signals ? "sí" : "no"), h("td", {}, g.won ? "Ganada" : "Perdida"), h("td", {}, g.tantos.join(" – "))));
    }
  } catch (e) { err.textContent = e.message; }
}

async function exportData() {
  const data = await api("GET", "/api/me/export");
  const link = h("a", { href: URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })), download: "musst-mis-datos.json" });
  link.click();
}

async function deleteAccount() {
  const password = prompt("Escribe tu contraseña para borrar la cuenta y todos tus datos:");
  if (!password) return;
  try { await api("DELETE", "/api/me", { password }); state.me = null; authScreen(); }
  catch (e) { alert(e.message); }
}

// --- Sala y mesa ---------------------------------------------------------------------------

function closeSocket() { const ws = state.ws; state.ws = null; state.link = ""; if (ws) { ws.onclose = null; ws.close(); } }

function enterRoom(room) {
  closeSocket();
  state.room = room; state.view = null; state.selected.clear(); state.bubbles = {}; state.lastPhrase = 0;
  state.link = "Conectando con la mesa…"; state.retries = 0;
  connect(room.code);
  waitingRoom();
}

// Conexión con la mesa: si se corta, se reintenta y se avisa en pantalla.
function connect(code) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/rooms/${code}`);
  state.ws = ws;
  ws.onopen = () => { state.link = ""; state.retries = 0; render(); };
  ws.onmessage = (msg) => {
    const data = JSON.parse(msg.data);
    if (data.error) { const e = document.getElementById("table-error"); if (e) e.textContent = data.error; return; }
    state.view = data; state.room = data.room;
    for (const p of data.phrases) if (p.id > state.lastPhrase) {
      state.lastPhrase = p.id;
      if (!state.quiet) { state.bubbles[p.seat] = p.text; setTimeout(() => { if (state.bubbles[p.seat] === p.text) { delete state.bubbles[p.seat]; render(); } }, 4000); }
    }
    render();
  };
  ws.onclose = (ev) => {
    if (state.ws !== ws) return; // ya hemos salido de la sala
    state.ws = null;
    if (ev.code === 4401 || ev.code === 4403) {
      state.link = "No se puede entrar en la mesa (sesión caducada o sala cerrada). Vuelve al lobby.";
    } else if (state.retries < 10) {
      state.retries += 1;
      state.link = "Se ha cortado la conexión con la mesa. Reintentando…";
      setTimeout(() => { if (!state.ws && state.room && state.room.code === code) connect(code); }, 1500 * state.retries);
    } else {
      state.link = "No hay conexión con la mesa. Comprueba tu conexión y recarga la página.";
    }
    render();
  };
}

function linkStatus() {
  return state.link ? h("p", { class: "error" }, state.link) : null;
}

function render() {
  if (!state.view) return waitingRoom();
  if (state.view.game) return tableScreen();
  return waitingRoom();
}

function waitingRoom() {
  const room = state.room;
  const err = h("p", { class: "error" });
  const isHost = room.host_id === state.me.id;
  const missing = room.human_seats.filter((s) => !room.seats[s]).length;
  mount(h("section", { class: "panel" },
    h("h2", {}, "Sala ", h("span", { class: "code" }, room.code)),
    linkStatus(),
    h("p", {}, MODES[room.mode], " · ", room.signals ? "con señas" : "sin señas", room.mode !== "cuatro" ? ` · bots de nivel ${room.level}` : ""),
    room.mode !== "con_bot" && h("p", { class: "muted" }, "Pasa este código a tus amigos para que se unan."),
    h("ul", {}, [0, 1, 2, 3].map((s) => h("li", {}, `Asiento ${s + 1} (pareja ${s % 2 ? "B" : "A"}): `,
      room.seats[s] ? `${room.seats[s].name} — ${room.seats[s].avatar.nickname}` : room.human_seats.includes(s) ? "esperando jugador…" : "bot"))),
    isHost
      ? h("button", { disabled: missing > 0, onclick: async () => { try { await api("POST", `/api/rooms/${room.code}/start`); } catch (e) { err.textContent = e.message; } } }, missing ? `Faltan ${missing}` : "Empezar")
      : h("p", { class: "muted" }, "Esperando a que empiece la partida…"),
    h("button", { class: "secondary", onclick: async () => { try { await api("POST", `/api/rooms/${room.code}/leave`); } catch (e) { /* ya empezada */ } lobby(); } }, "Volver"),
    err));
}

function cardEl(code, opts = {}) {
  if (!code) return h("span", { class: "card back" });
  const suit = code.slice(-1), num = Number(code.slice(0, -1));
  return h(opts.onclick ? "button" : "span", { class: `card ${suit}${opts.selected ? " sel" : ""}${opts.small ? " mini" : ""}`, onclick: opts.onclick, title: `${FIGURES[num] || num} de ${SUITS[suit]}` },
    FIGURES[num] ? FIGURES[num][0] + (num === 1 ? "s" : "") : String(num), h("small", {}, SUITS[suit]));
}

const POS_VECTORS = [[0, 1], [1, 0], [0, -1], [-1, 0]]; // abajo, derecha, arriba, izquierda

function gazeVector(fromPos, toPos) {
  if (toPos == null) return [0, 0.4]; // mira la mesa
  const [ax, ay] = POS_VECTORS[fromPos], [bx, by] = POS_VECTORS[toPos];
  const dx = bx - ax, dy = by - ay, n = Math.hypot(dx, dy) || 1;
  return [dx / n, dy / n];
}

function moodFor(g, seat) {
  const last = [...g.events].reverse().find((e) => e.type === "LanceResolved" || e.type === "GameFinished");
  if (!last) return "";
  const team = seat % 2 ? "B" : "A";
  const winTeam = last.type === "GameFinished" ? last.data.winner : (last.data.winner % 2 ? "B" : "A");
  return winTeam === team ? "contento" : "fastidiado";
}

function describe(e, names) {
  const d = e.data, n = (s) => names[s];
  switch (e.type) {
    case "HandStarted": return `— Mano ${d.hand_number}: reparte ${n(d.dealer)}, es mano ${n(d.mano)}`;
    case "MusRequested": return `${n(d.seat)}: mus`;
    case "MusCut": return `${n(d.seat)}: corto`;
    case "DiscardDeclared": return `${n(d.seat)} pide ${d.count}`;
    case "LanceStarted": return `Lance de ${LANCES[d.lance]}`;
    case "Passed": return `${n(d.seat)}: paso`;
    case "BetPlaced": return `${n(d.seat)}: envido ${d.amount}`;
    case "BetRaised": return `${n(d.seat)}: ${d.increment} más (${d.total})`;
    case "OrdagoDeclared": return `${n(d.seat)}: ¡ÓRDAGO!`;
    case "BetAccepted": case "OrdagoAccepted": return `${n(d.seat)}: quiero`;
    case "BetRejected": return `${n(d.seat)}: no quiero`;
    case "ParesDeclared": return "Pares: " + d.holders.map((x, i) => `${n(i)} ${x ? "sí" : "no"}`).join(", ");
    case "JuegoDeclared": return "Juego: " + d.holders.map((x, i) => `${n(i)} ${x ? "sí" : "no"}`).join(", ");
    case "LanceResolved": return `${LANCES[d.lance]} para ${n(d.winner)}`;
    case "PointsAwarded": return `+${d.points} pareja ${d.team} (${LANCES[d.lance] || d.lance}) → ${d.tantos_after.join("–")}`;
    case "HandsRevealed": return "Cartas: " + d.hands.map((cs, i) => `${n(i)} ${cs.join(" ")}`).join(" · ");
    case "GameWon": return `Juego para la pareja ${d.team}`;
    case "GameFinished": return `¡Partida para la pareja ${d.winner}!`;
    case "SignalSeen": return `Has visto una seña de ${n(d.sender)}: ${SIGNALS[d.signal]}`;
    default: return null;
  }
}

function send(action) {
  const err = document.getElementById("table-error"); if (err) err.textContent = "";
  if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.send(JSON.stringify({ action }));
}

function actionPanel(g) {
  const legal = g.legal;
  const mine = g.to_act.includes(g.seat);
  const panel = h("div", { class: "actions" });
  const main = legal.actions.filter((a) => a.type !== "signal" && a.type !== "discard");
  const row = h("div", { class: "row" });
  if (mine) {
    for (const a of main) row.append(h("button", { onclick: () => send(a) }, ACTIONS[a.type] || a.type));
    if (legal.bet) {
      const amt = h("input", { type: "number", min: legal.bet.min, max: legal.bet.max ?? 40, value: legal.bet.min });
      row.append(amt, h("button", { onclick: () => send({ type: "bet", amount: Number(amt.value) }) }, "Envido"));
    }
    if (legal.raise) {
      const amt = h("input", { type: "number", min: legal.raise.min, max: legal.raise.max ?? 40, value: legal.raise.min });
      row.append(amt, h("button", { onclick: () => send({ type: "raise", amount: Number(amt.value) }) }, "Más"));
    }
    if (g.phase === "discard") {
      row.append(h("span", {}, "Toca las cartas que quieres cambiar "),
        h("button", { disabled: state.selected.size === 0, onclick: () => { send({ type: "discard", cards: [...state.selected] }); state.selected.clear(); } }, `Descartar ${state.selected.size}`));
    }
  } else if (g.phase !== "game_over") {
    row.append(h("span", { class: "muted" }, `Esperando a ${g.to_act.map((s) => g.names[s]).join(", ")}…`));
  }
  panel.append(row);
  const signals = legal.actions.filter((a) => a.type === "signal");
  if (state.room.signals) {
    const srow = h("div", { class: "row" }, h("span", {}, "Señas: "));
    if (!signals.length) srow.append(h("span", { class: "muted" }, "ahora no puedes hacer ninguna"));
    for (const a of signals) srow.append(h("button", { class: "secondary", onclick: () => send(a) }, SIGNALS[a.signal] || a.signal));
    panel.append(srow);
    if (g.gaze) {
      const watching = [0, 1, 2, 3].filter((s) => s !== g.seat && g.gaze[s] === g.seat).map((s) => g.names[s]);
      panel.append(h("p", { class: "muted" }, watching.length ? `Te miran: ${watching.join(", ")}` : "Nadie te mira ahora"));
    }
  }
  return panel;
}

function tableScreen() {
  const v = state.view, g = v.game, room = v.room, me = g.seat;
  const lastReveal = [...g.events].reverse().find((e) => e.type === "HandsRevealed");
  const revealed = g.revealed_hands;
  const previous = !revealed && lastReveal && lastReveal.hand === g.hand_number - 1 ? lastReveal.data.hands : null;
  const seats = [0, 1, 2, 3].map((s) => {
    const pos = (s - me + 4) % 4;
    const occ = room.seats[s];
    const target = g.gaze ? g.gaze[s] : null;
    const [dx, dy] = gazeVector(pos, target == null ? null : (target - me + 4) % 4);
    const tags = [];
    if (g.mano === s) tags.push("mano");
    if (g.dealer === s) tags.push("reparte");
    if (g.discard_counts[s] != null) tags.push(`pide ${g.discard_counts[s]}`);
    if (g.mus_requested.includes(s)) tags.push("mus");
    let cards;
    if (s === me) {
      cards = g.my_hand.map((c) => cardEl(c, {
        selected: state.selected.has(c),
        onclick: g.phase === "discard" && g.to_act.includes(me) ? () => { state.selected.has(c) ? state.selected.delete(c) : state.selected.add(c); render(); } : null,
      }));
    } else if (revealed && revealed[s] && revealed[s].length) {
      cards = revealed[s].map((c) => cardEl(c));
    } else {
      cards = [0, 1, 2, 3].map(() => cardEl(null));
    }
    return h("div", { class: `seat pos${pos}${g.to_act.includes(s) ? " turn" : ""}` },
      state.bubbles[s] && h("div", { class: "bubble" }, state.bubbles[s]),
      face(occ.avatar, dx, dy, moodFor(g, s)),
      h("div", { class: "name" }, occ.name, occ.bot ? " 🤖" : ""),
      h("div", { class: "tags" }, `Pareja ${s % 2 ? "B" : "A"}`, tags.length ? " · " + tags.join(" · ") : ""),
      h("div", { class: "cards" }, cards));
  });
  const mineTeam = me % 2;
  const center = h("div", { class: "center" },
    h("div", { class: "score" },
      h("span", {}, "Nosotros ", h("b", {}, g.score.tantos[mineTeam])),
      h("span", {}, "Ellos ", h("b", {}, g.score.tantos[1 - mineTeam]))),
    h("div", { class: "dim" }, `a ${g.target_score} · mano ${g.hand_number}`),
    h("div", {}, PHASES[g.phase] || g.phase, g.lance ? ` · ${LANCES[g.lance]}` : ""),
    g.bet && g.bet.accepted + g.bet.pending > 0 && h("div", {}, g.bet.is_ordago ? "¡Órdago!" : `En juego: ${g.bet.accepted}${g.bet.pending ? ` (+${g.bet.pending})` : ""}`),
    g.signals_seen.length > 0 && h("div", { class: "signals-seen" }, "Señas vistas: " + g.signals_seen.map((x) => `${g.names[x.sender]}: ${SIGNALS[x.signal]}`).join(", ")),
    previous && h("div", { class: "previous" }, h("div", {}, "Mano anterior"),
      previous.map((cs, s) => h("div", {}, g.names[s] + ": ", cs.map((c) => cardEl(c, { small: true }))))),
    g.winner && h("h2", {}, g.winner === (mineTeam ? "B" : "A") ? "¡Habéis ganado!" : "Habéis perdido"),
    g.winner && h("button", { onclick: lobby }, "Volver al lobby"));
  const log = h("div", { class: "log" }, g.events.map((e) => describe(e, g.names)).filter(Boolean).slice(-40).map((t) => h("div", {}, t)));
  mount(
    h("div", { class: "table" }, seats, center),
    h("section", { class: "panel" }, linkStatus(), actionPanel(g), h("p", { class: "error", id: "table-error" }),
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: state.quiet, onchange: (ev) => { state.quiet = ev.target.checked; } }), "Silenciar frases")),
    h("section", { class: "panel" }, h("h3", {}, "Lo que ha pasado"), log));
  log.scrollTop = log.scrollHeight;
}

// --- Arranque ------------------------------------------------------------------------------

(async function boot() {
  try {
    const pack = await api("GET", "/api/avatars");
    state.avatars = pack.avatars; state.notice = pack.aviso;
    document.getElementById("notice").textContent = pack.aviso;
  } catch (e) { /* sin avatares no se puede seguir */ }
  try { state.me = await api("GET", "/api/me"); lobby(); }
  catch (e) { authScreen(); }
})();
