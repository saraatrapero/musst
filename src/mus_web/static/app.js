"use strict";
// MUS.ST: cliente sin compilación. Todo el DOM se construye con textContent (sin
// innerHTML) para que ningún nombre de usuario pueda inyectar código.

const state = { me: null, avatars: [], notice: "", room: null, view: null, ws: null, selected: new Set(), bubbles: {}, lastPhrase: 0, quiet: false, summarySeen: 0, phraseLog: [] };

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
const ACTIONS = { mus: "Mus (cambiar cartas)", cut: "Corto (jugar)", pass: "Paso", accept: "Quiero", reject: "No quiero", ordago: "¡Órdago!", discard: "Descartar" };

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

function mount(...nodes) { const app = document.getElementById("app"); app.replaceChildren(...nodes.filter((n) => n != null && n !== false)); }
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
  document.body.classList.remove("playing");
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
    if (!code.value.trim()) { err.textContent = "Escribe el código de la sala de tu amigo (para jugar tú solo, pulsa «Jugar»)."; return; }
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
  state.summarySeen = 0; state.phraseLog = [];
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
      const who = data.room.seats[p.seat] ? data.room.seats[p.seat].name : "";
      state.phraseLog.push(`${who}: «${p.text}»`);
      if (!state.quiet) { state.bubbles[p.seat] = p.text; setTimeout(() => { if (state.bubbles[p.seat] === p.text) { delete state.bubbles[p.seat]; render(); } }, 6500); }
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

// --- Naipes ---------------------------------------------------------------------------------
// Baraja española dibujada en SVG: número y palo (oros, copas, espadas, bastos).

const SUIT_COLORS = { O: "#c99a06", C: "#c0392b", E: "#2c4a7a", B: "#2e7d32" };

function suitIcon(suit, size = 26) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("aria-hidden", "true");
  const add = (name, attrs) => { const e = document.createElementNS(ns, name); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); svg.append(e); };
  const c = SUIT_COLORS[suit];
  if (suit === "O") {
    add("circle", { cx: 12, cy: 12, r: 10, fill: c, stroke: "#7a5c00", "stroke-width": 1.5 });
    add("circle", { cx: 12, cy: 12, r: 5, fill: "none", stroke: "#7a5c00", "stroke-width": 1.5 });
  } else if (suit === "C") {
    add("path", { d: "M5 4h14c0 6-3 9-6 9.5V18h3v2H8v-2h3v-4.5C8 13 5 10 5 4z", fill: c });
  } else if (suit === "E") {
    add("path", { d: "M12 1l2.6 3.5V15h-5.2V4.5z", fill: c });
    add("path", { d: "M5 15h14v2.6H5z", fill: c });
    add("path", { d: "M10.6 17.6h2.8V23h-2.8z", fill: "#6b4f2a" });
  } else {
    add("path", { d: "M8 2.5c3-1.6 8-.6 8 2.6l-1.6 15.4c-.2 2-4.6 2-4.8 0L7 5.6c0-1.3.2-2.4 1-3.1z", fill: c, stroke: "#1b4d1e", "stroke-width": 1 });
    add("circle", { cx: 10.5, cy: 8, r: 1.3, fill: "#1b4d1e" });
    add("circle", { cx: 13, cy: 12.5, r: 1.3, fill: "#1b4d1e" });
    add("circle", { cx: 11, cy: 16.5, r: 1.1, fill: "#1b4d1e" });
  }
  return svg;
}

const PIPS = {
  1: [[50, 50]], 2: [[50, 26], [50, 74]], 3: [[50, 20], [50, 50], [50, 80]],
  4: [[32, 26], [68, 26], [32, 74], [68, 74]], 5: [[32, 24], [68, 24], [50, 50], [32, 76], [68, 76]],
  6: [[32, 20], [68, 20], [32, 50], [68, 50], [32, 80], [68, 80]],
  7: [[32, 18], [68, 18], [50, 34], [32, 52], [68, 52], [32, 82], [68, 82]],
};
const FIGURE_ART = { 10: ["💂", "SOTA"], 11: ["🐎", "CABALLO"], 12: ["👑", "REY"] };

// Naipe. opts: small (resúmenes), selected, glow (cuenta en el lance), onclick, back.
function cardEl(code, opts = {}) {
  const size = opts.small ? " mini" : "";
  if (!code) return h("span", { class: `card back${size}` }, h("span", { class: "backlogo" }, "MUS.ST"));
  const suit = code.slice(-1), num = Number(code.slice(0, -1));
  const eff = effectiveRank(code);
  const title = `${FIGURES[num] || num} de ${SUITS[suit]}`;
  const badge = eff === 12 ? "REY" : eff === 1 ? "AS" : null;
  const cls = `card face ${suit}${size}${opts.selected ? " sel" : ""}${opts.glow ? " glow" : ""}`;
  const body = [];
  body.push(h("span", { class: "corner" }, String(num), suitIcon(suit, opts.small ? 10 : 14)));
  if (badge) body.push(h("span", { class: "badge" }, badge));
  if (!opts.small) {
    if (FIGURE_ART[num]) {
      const [art, name] = FIGURE_ART[num];
      body.push(h("span", { class: "figure" }, h("span", { class: "art" }, art), suitIcon(suit, 18), h("span", { class: "fname" }, name)));
    } else {
      const pips = h("span", { class: "pips" });
      for (const [x, y] of PIPS[num]) {
        const pip = h("span", { class: "pip" });
        pip.append(suitIcon(suit, num === 1 ? 40 : 22));
        pip.dataset.x = x; pip.dataset.y = y;
        pips.append(pip);
      }
      body.push(pips);
    }
    body.push(h("span", { class: "suitname" }, SUITS[suit].toUpperCase()));
  } else {
    body.push(h("span", { class: "minisuit" }, suitIcon(suit, 16)));
  }
  const el = h(opts.onclick ? "button" : "span", { class: cls, onclick: opts.onclick, title, "aria-label": title }, body);
  // Posición de los símbolos (sin estilos en línea en el HTML: se fija desde JS).
  for (const pip of el.querySelectorAll(".pip")) { pip.style.left = `${pip.dataset.x}%`; pip.style.top = `${pip.dataset.y}%`; }
  return el;
}

// Naipes que cuentan en cada lance (para resaltarlos en el resumen).
function countsIn(lance, cards) {
  const eff = cards.map(effectiveRank);
  if (lance === "grande") return eff.map((r) => r === 12);
  if (lance === "chica") return eff.map((r) => r === 1);
  if (lance === "pares") return eff.map((r) => eff.filter((x) => x === r).length >= 2);
  return eff.map(() => true);
}

// --- Qué tengo -------------------------------------------------------------------------------
const RANK_NAMES = { 1: "ases", 4: "cuatros", 5: "cincos", 6: "seises", 7: "sietes", 10: "sotas", 11: "caballos", 12: "reyes" };

function effectiveRank(code) {
  const n = Number(code.slice(0, -1));
  return n === 3 ? 12 : n === 2 ? 1 : n;
}

function handInfo(cards) {
  if (cards.length !== 4) return "";
  const ranks = cards.map(effectiveRank);
  const counts = {};
  for (const r of ranks) counts[r] = (counts[r] || 0) + 1;
  const groups = Object.entries(counts).map(([r, n]) => [Number(r), n]).sort((a, b) => b[1] - a[1] || b[0] - a[0]);
  let pares = "sin pares";
  if (groups[0][1] === 4) pares = `duples de ${RANK_NAMES[groups[0][0]]}`;
  else if (groups[0][1] === 3) pares = `medias de ${RANK_NAMES[groups[0][0]]}`;
  else if (groups[0][1] === 2 && groups[1][1] === 2) pares = `duples de ${RANK_NAMES[groups[0][0]]} y ${RANK_NAMES[groups[1][0]]}`;
  else if (groups[0][1] === 2) pares = `pareja de ${RANK_NAMES[groups[0][0]]}`;
  const total = ranks.reduce((acc, r) => acc + (r >= 10 ? 10 : r), 0);
  const juego = total >= 31 ? `juego de ${total}${total === 31 ? " (¡la mejor!)" : ""}` : `sin juego (al punto: ${total})`;
  const reyes = ranks.filter((r) => r === 12).length, ases = ranks.filter((r) => r === 1).length;
  return `Tu jugada: ${pares} · ${juego} · grande: ${reyes} ${reyes === 1 ? "rey" : "reyes"} · chica: ${ases} ${ases === 1 ? "as" : "ases"}`;
}

// --- Lo que ha dicho cada uno en esta mano ----------------------------------------------------
function seatChips(g) {
  const said = {}, declared = { pares: {}, juego: {} };
  for (const e of g.events) {
    if (e.hand !== g.hand_number) continue;
    const d = e.data;
    switch (e.type) {
      case "LanceStarted": for (const k of Object.keys(said)) delete said[k]; break;
      case "DiscardDeclared": said[d.seat] = `Pide ${d.count}`; break;
      case "MusRequested": said[d.seat] = "Mus"; break;
      case "MusCut": said[d.seat] = "¡Corto!"; break;
      case "Passed": said[d.seat] = "Paso"; break;
      case "BetPlaced": said[d.seat] = `Envido ${d.amount}`; break;
      case "BetRaised": said[d.seat] = `${d.increment} más`; break;
      case "OrdagoDeclared": said[d.seat] = "¡ÓRDAGO!"; break;
      case "BetAccepted": case "OrdagoAccepted": said[d.seat] = "Quiero"; break;
      case "BetRejected": said[d.seat] = "No quiero"; break;
      case "ParesDeclared": d.holders.forEach((x, i) => { declared.pares[i] = x; }); break;
      case "JuegoDeclared": d.holders.forEach((x, i) => { declared.juego[i] = x; }); break;
      default: break;
    }
  }
  return { said, declared };
}

// --- Lances ---------------------------------------------------------------------------------
const RESOLUTIONS = {
  passed: () => "En paso",
  accepted: (o) => `Querido: ${o.amount} (se ve al final)`,
  rejected: (o, t) => `No querido: +${o.immediate_points} ${t(o.team)}`,
  uncontested: (o, t) => `Solo lo juega${o.team ? ` ${t(o.team)}` : ""}`,
  not_played: () => "Nadie tiene",
  ordago_accepted: () => "¡Órdago querido!",
};

function lanceBoard(g) {
  const mineTeam = g.seat % 2 ? "B" : "A";
  const teamName = (t) => (t === mineTeam ? "nosotros" : "ellos");
  const punto = g.juego_holders && g.juego_holders.every((x) => !x);
  const order = ["grande", "chica", "pares", punto ? "punto" : "juego"];
  return h("div", { class: "lances" }, order.map((lance) => {
    const outcome = g.outcomes.find((o) => o.lance === lance);
    let status = "—", cls = "";
    if (outcome) {
      status = (RESOLUTIONS[outcome.resolution] || (() => outcome.resolution))(outcome, teamName);
      cls = "done";
    } else if (g.phase === "lance" && g.lance === lance) {
      cls = "now";
      const b = g.bet;
      if (b && b.is_ordago) status = "¡Órdago en juego!";
      else if (b && b.pending > b.accepted) status = `Envite de ${b.pending}`;
      else status = "Hablando…";
    }
    return h("div", { class: `lance ${cls}` }, h("span", { class: "lname" }, LANCES[lance]), h("span", {}, status));
  }));
}

// --- Aviso de turno ---------------------------------------------------------------------------
function turnBanner(g) {
  if (g.phase === "game_over") return null;
  const mine = g.to_act.includes(g.seat);
  const n = (s) => g.names[s];
  if (!mine) return h("div", { class: "banner wait" }, `Le toca a ${g.to_act.map(n).join(", ")}…`);
  let text = "Te toca";
  if (g.phase === "mus_decision") text = "Te toca: ¿pides mus (cambiar cartas) o cortas (jugar con estas)?";
  else if (g.phase === "discard") text = "Toca las cartas que quieres cambiar y pulsa «Descartar».";
  else if (g.phase === "lance" && g.bet) {
    const lance = LANCES[g.lance] ? `la ${LANCES[g.lance]}` : "este lance";
    if (g.bet.is_ordago) text = `¡${n(g.bet.proposer)} echa un ÓRDAGO a ${lance}! Si quieres, este lance decide la partida.`;
    else if (g.bet.pending > g.bet.accepted && g.bet.proposer != null) text = `${n(g.bet.proposer)} envida ${g.bet.pending} a ${lance}. ¿Quieres?`;
    else text = `Te toca hablar a ${lance}: paso, envido u órdago.`;
  }
  return h("div", { class: "banner mine" }, text);
}

// --- Resumen de la mano -------------------------------------------------------------------------
const REASONS = { negada: "no quisieron", envite_no_querido: "no quisieron el revoque", envite: "envite querido", paso: "en paso", pares: "pares", juego: "juego", punto: "punto", ordago: "órdago" };

const LANCE_WHY = {
  grande: "por tener las cartas más altas", chica: "por tener las cartas más bajas",
  pares: "por mejores pares", juego: "por mejor juego", punto: "por más puntos al punto",
};

function handSummary(g) {
  const hand = g.phase === "game_over" ? g.hand_number : g.hand_number - 1;
  if (hand < 1 || state.summarySeen >= hand) return null;
  const evs = g.events.filter((e) => e.hand === hand);
  const points = evs.filter((e) => e.type === "PointsAwarded");
  if (!points.length) return null;
  const reveal = evs.find((e) => e.type === "HandsRevealed");
  const hands = reveal ? reveal.data.hands : null;
  const mineTeam = g.seat % 2 ? "B" : "A";
  const who = (t) => (t === mineTeam ? "Nosotros" : "Ellos");
  const last = points[points.length - 1].data.tantos_after;
  const lances = [...new Set(points.map((e) => e.data.lance))];
  const tabs = [...lances, "resumen"];
  if (!state.summaryTab || !tabs.includes(state.summaryTab)) state.summaryTab = tabs[0];
  const tab = state.summaryTab;
  const close = () => { state.summarySeen = hand; state.summaryTab = null; render(); };
  const next = () => { const i = tabs.indexOf(tab); if (i + 1 < tabs.length) { state.summaryTab = tabs[i + 1]; render(); } else close(); };
  let body;
  if (tab === "resumen") {
    body = h("div", {},
      h("ul", { class: "pointlist" }, points.map((e) => h("li", { class: e.data.team === mineTeam ? "good" : "bad" },
        `${LANCES[e.data.lance] || e.data.lance}: +${e.data.points} ${who(e.data.team)} (${REASONS[e.data.reason] || e.data.reason})`))),
      h("p", { class: "final" }, `Marcador: nosotros ${last[mineTeam === "A" ? 0 : 1]} · ellos ${last[mineTeam === "A" ? 1 : 0]}`));
  } else {
    const won = points.filter((e) => e.data.lance === tab);
    const resolved = evs.find((e) => e.type === "LanceResolved" && e.data.lance === tab);
    const team = won.length ? won[0].data.team : null;
    const total = won.reduce((a, e) => a + e.data.points, 0);
    const winnerName = resolved ? g.names[resolved.data.winner] : who(team);
    const why = resolved ? LANCE_WHY[tab] : (won[0] && won[0].data.reason === "negada" ? "porque no se quiso el envite" : "");
    body = h("div", {},
      h("div", { class: `winner ${team === mineTeam ? "good" : "bad"}` },
        h("b", {}, `👑 Gana: ${winnerName}`), winnerName !== who(team) && h("span", { class: "pill" }, who(team)),
        h("div", {}, `${why} · +${total} piedra${total === 1 ? "" : "s"}`)),
      hands && h("div", { class: "fourhands" }, [0, 1, 2, 3].map((s) => {
        const glow = countsIn(tab, hands[s]);
        const winnerSeat = resolved && resolved.data.winner === s;
        return h("div", { class: `handbox ${s % 2 === g.seat % 2 ? "ours" : "theirs"}${winnerSeat ? " win" : ""}` },
          h("div", { class: "hb-head" }, h("b", {}, g.names[s]), h("small", {}, s === g.seat ? "tú" : s % 2 === g.seat % 2 ? "tu pareja" : "rival")),
          h("div", { class: "hb-info" }, handInfo(hands[s]).replace("Tu jugada: ", "")),
          h("div", { class: "cards" }, hands[s].map((c, i) => cardEl(c, { small: true, glow: glow[i] }))));
      })));
  }
  return h("div", { class: "overlay", onclick: (ev) => { if (ev.target === ev.currentTarget) close(); } },
    h("div", { class: "summary" },
      h("div", { class: "sum-head" }, h("h2", {}, `Mano ${hand}: ${tab === "resumen" ? "resumen" : `a la ${LANCES[tab]}`}`),
        h("button", { class: "small", onclick: close }, g.phase === "game_over" ? "Ver la mesa" : "Saltar")),
      h("div", { class: "tabs" }, tabs.map((t) => h("button", { class: `tab${t === tab ? " on" : ""}`, onclick: () => { state.summaryTab = t; render(); } }, t === "resumen" ? "📊 Resumen" : LANCES[t]))),
      body,
      h("button", { class: "big go", onclick: next }, tab === "resumen" ? (g.phase === "game_over" ? "Ver la mesa" : "Seguir jugando ▶") : "Siguiente ▶")));
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

function describe(e, names, seat) {
  const d = e.data, n = (s) => names[s];
  const team = (t) => (t === (seat % 2 ? "B" : "A") ? "nosotros" : "ellos");
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
    case "PointsAwarded": return `+${d.points} ${team(d.team)} (${LANCES[d.lance] || d.lance}, ${REASONS[d.reason] || d.reason})`;
    case "HandsRevealed": return "Cartas: " + d.hands.map((cs, i) => `${n(i)} ${cs.join(" ")}`).join(" · ");
    case "GameWon": return `Juego para ${team(d.team)}`;
    case "GameFinished": return `¡Partida para ${team(d.winner)}!`;
    case "SignalSeen": return `Has visto una seña de ${n(d.sender)}: ${SIGNALS[d.signal]}`;
    default: return null;
  }
}

function send(action) {
  const err = document.getElementById("table-error"); if (err) err.textContent = "";
  if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.send(JSON.stringify({ action }));
}

// Botones grandes abajo, con colores por significado.
const ACTION_STYLE = { mus: ["🔄 PEDIR MUS", "go"], cut: ["⛔ NO HAY MUS (corto)", "stop"], pass: ["Paso", "neutral"], accept: ["✅ QUIERO", "go"], reject: ["✋ NO QUIERO", "stop"], ordago: ["🔥 ¡ÓRDAGO!", "hot"] };

function actionBar(g) {
  const legal = g.legal;
  const mine = g.to_act.includes(g.seat);
  const bar = h("div", { class: "actionbar" });
  bar.append(h("div", { class: "phase" }, h("span", { class: "dot" }), `Fase: ${phaseLabel(g)}`));
  const row = h("div", { class: "buttons" });
  if (mine) {
    const main = legal.actions.filter((a) => a.type !== "signal" && a.type !== "discard");
    for (const a of main) {
      const [label, kind] = ACTION_STYLE[a.type] || [ACTIONS[a.type] || a.type, "neutral"];
      row.append(h("button", { class: `big ${kind}`, onclick: () => send(a) }, label));
    }
    for (const [key, range, verb] of [["bet", legal.bet, "Envido"], ["raise", legal.raise, "Subo"]]) {
      if (!range) continue;
      for (const amount of [range.min, range.min + 2, range.min + 3]) {
        row.append(h("button", { class: "big bet", onclick: () => send({ type: key, amount }) }, `${verb} ${amount}`));
      }
    }
    if (g.phase === "discard") {
      row.append(h("button", { class: "big go", disabled: state.selected.size === 0, onclick: () => { send({ type: "discard", cards: [...state.selected] }); state.selected.clear(); } },
        state.selected.size ? `🔄 Cambiar ${state.selected.size} carta${state.selected.size > 1 ? "s" : ""}` : "Toca las cartas que quieres cambiar"));
    }
  } else if (g.phase !== "game_over") {
    row.append(h("div", { class: "waiting" }, `Esperando a ${g.to_act.map((s) => g.names[s]).join(", ")}…`));
  }
  bar.append(row);
  if (state.room.signals) {
    const signals = legal.actions.filter((a) => a.type === "signal");
    const srow = h("div", { class: "signals" }, h("span", {}, "🤫 Señas: "));
    if (!signals.length) srow.append(h("span", { class: "muted" }, "ahora no puedes hacer ninguna"));
    for (const a of signals) srow.append(h("button", { class: "small", onclick: () => send(a) }, SIGNALS[a.signal] || a.signal));
    if (g.gaze) {
      const watching = [0, 1, 2, 3].filter((s) => s !== g.seat && g.gaze[s] === g.seat).map((s) => g.names[s]);
      srow.append(h("span", { class: "muted" }, watching.length ? ` · Te miran: ${watching.join(", ")}` : " · Nadie te mira"));
    }
    bar.append(srow);
  }
  return bar;
}

function phaseLabel(g) {
  if (g.phase === "mus_decision") return "Mus (¿hay o no?)";
  if (g.phase === "discard") return "Descartes";
  if (g.phase === "lance" && g.lance) return `A la ${LANCES[g.lance]}`;
  return PHASES[g.phase] || g.phase;
}

function myHandChips(cards) {
  if (cards.length !== 4) return null;
  const info = handInfo(cards);
  const pares = info.match(/Tu jugada: ([^·]+)/)[1].trim();
  const juego = info.split(" · ")[1];
  const has = (t) => !t.startsWith("sin");
  return h("div", { class: "mychips" },
    h("span", { class: `chip ${has(pares) ? "yes" : "no"}` }, `${has(pares) ? "✔" : "✖"} Pares: ${has(pares) ? pares : "no"}`),
    h("span", { class: `chip ${has(juego) ? "yes" : "no"}` }, `${has(juego) ? "✔" : "✖"} Juego: ${has(juego) ? juego.replace("juego de ", "") : juego.replace("sin juego (al punto: ", "punto (")}`));
}

function scoreBox(g, ours) {
  const team = ours ? g.seat % 2 : 1 - (g.seat % 2);
  const tantos = g.score.tantos[team];
  return h("div", { class: `teambox ${ours ? "ours" : "theirs"}` },
    h("span", { class: "dot" }), h("span", { class: "tname" }, ours ? "Tu pareja" : "Rivales"),
    h("span", { class: "big" }, String(tantos), h("small", {}, `/${g.target_score}`)),
    h("span", { class: "pill" }, `${Math.floor(tantos / 5)} amarr.`),
    h("span", { class: "pill" }, `${tantos % 5} piedras`));
}

function tableScreen() {
  const v = state.view, g = v.game, room = v.room, me = g.seat;
  document.body.classList.add("playing");
  const revealed = g.revealed_hands;
  const { said, declared } = seatChips(g);
  const seats = [0, 1, 2, 3].map((s) => {
    const pos = (s - me + 4) % 4;
    const occ = room.seats[s];
    const target = g.gaze ? g.gaze[s] : null;
    const [dx, dy] = gazeVector(pos, target == null ? null : (target - me + 4) % 4);
    const role = s === me ? "tú" : (s % 2 === me % 2 ? "tu pareja" : "rival");
    const tags = [role];
    if (g.mano === s) tags.push("mano");
    if (g.dealer === s) tags.push("reparte");
    const chips = [];
    if (said[s]) chips.push(h("span", { class: `chip say${said[s].includes("ÓRDAGO") ? " hot" : ""}` }, said[s]));
    if (s in declared.pares) chips.push(h("span", { class: `chip ${declared.pares[s] ? "yes" : "no"}` }, declared.pares[s] ? "Pares sí" : "Pares no"));
    if (s in declared.juego) chips.push(h("span", { class: `chip ${declared.juego[s] ? "yes" : "no"}` }, declared.juego[s] ? "Juego sí" : "Juego no"));
    let cards;
    if (s === me) {
      cards = g.my_hand.map((c) => cardEl(c, {
        selected: state.selected.has(c),
        onclick: g.phase === "discard" && g.to_act.includes(me) ? () => { state.selected.has(c) ? state.selected.delete(c) : state.selected.add(c); render(); } : null,
      }));
    } else if (revealed && revealed[s] && revealed[s].length) {
      cards = revealed[s].map((c) => cardEl(c, { small: true }));
    } else {
      cards = [0, 1, 2, 3].map(() => cardEl(null, { small: true }));
    }
    return h("div", { class: `seat pos${pos}${g.to_act.includes(s) ? " turn" : ""}${s % 2 === me % 2 ? " ours" : " theirs"}` },
      state.bubbles[s] && h("div", { class: "bubble" }, state.bubbles[s]),
      h("div", { class: "plate" },
        face(occ.avatar, dx, dy, moodFor(g, s)),
        h("div", {}, h("div", { class: "name" }, occ.name, occ.bot ? " 🤖" : ""), h("div", { class: "tags" }, tags.join(" · ")))),
      chips.length > 0 && h("div", { class: "chips" }, chips),
      h("div", { class: `cards${s === me ? " mine" : ""}` }, cards),
      s === me && myHandChips(g.my_hand));
  });
  const mineTeam = me % 2;
  const header = h("div", { class: "gamehead" },
    scoreBox(g, true),
    h("div", { class: "lancepill" }, h("small", {}, "LANCE"), " ", phaseLabel(g).toUpperCase()),
    scoreBox(g, false));
  const center = h("div", { class: "center" },
    lanceBoard(g),
    g.signals_seen.length > 0 && h("div", { class: "signals-seen" }, "Señas vistas: " + g.signals_seen.map((x) => `${g.names[x.sender]}: ${SIGNALS[x.signal]}`).join(", ")),
    g.winner && h("h2", {}, g.winner === (mineTeam ? "B" : "A") ? "🏆 ¡Habéis ganado!" : "Habéis perdido"),
    g.winner && h("button", { class: "big go", onclick: () => { document.body.classList.remove("playing"); lobby(); } }, "Volver al menú"));
  const lines = g.events.map((e) => describe(e, g.names, me)).filter(Boolean).slice(-40);
  const log = h("div", { class: "log" }, lines.map((t) => h("div", {}, t)),
    state.phraseLog.slice(-5).map((p) => h("div", { class: "said" }, `💬 ${p}`)));
  mount(
    header,
    turnBanner(g),
    linkStatus(),
    h("div", { class: "felt" }, h("div", { class: "table" }, seats, center)),
    actionBar(g),
    h("p", { class: "error", id: "table-error" }),
    h("details", { class: "panel history" }, h("summary", {}, "📜 Lo que ha pasado"), log,
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: state.quiet, onchange: (ev) => { state.quiet = ev.target.checked; } }), "Silenciar frases")),
    handSummary(g));
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
