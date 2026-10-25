"use strict";
// MUS.ST: cliente sin compilación. Todo el DOM se construye con textContent (sin
// innerHTML) para que ningún nombre de usuario pueda inyectar código.

const state = {
  me: null, avatars: [], notice: "", room: null, view: null, ws: null, selected: new Set(), bubbles: {},
  lastPhrase: 0, quiet: false, summarySeen: 0, phraseLog: [], deckImages: [],
  dealing: null, dealtShown: 0, voice: readPref("voz", true), signalsOpen: false, lastCall: null,
};

function readPref(key, fallback) {
  try { const v = localStorage.getItem(key); return v === null ? fallback : v === "1"; } catch (e) { return fallback; }
}
function writePref(key, value) { try { localStorage.setItem(key, value ? "1" : "0"); } catch (e) { /* sin almacenamiento */ } }

// --- Voces de los avatares (síntesis de voz del navegador) ---------------------------------
function speak(text, avatarId) {
  if (!state.voice || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "es-ES";
  const voices = speechSynthesis.getVoices().filter((v) => v.lang && v.lang.startsWith("es"));
  const i = Math.max(0, state.avatars.findIndex((a) => a.id === avatarId));
  if (voices.length) u.voice = voices[i % voices.length];
  u.pitch = 0.8 + ((i * 37) % 60) / 100; // cada personaje con su tono
  u.rate = 0.95 + ((i * 13) % 20) / 100;
  speechSynthesis.speak(u);
}
// Cada jugador «canta» en voz alta lo que hace (mus, paso, envido, quiero…), como en la
// mesa de verdad. Sólo lo nuevo: al entrar en la sala no se repite lo ya hablado.
const DISCARD_WORDS = { 1: "Dame una", 2: "Dame dos", 3: "Dame tres", 4: "Dame cuatro" };
function callFor(e) {
  const d = e.data;
  switch (e.type) {
    case "MusRequested": return [[d.seat, "Mus"]];
    case "MusCut": return [[d.seat, "No hay mus"]];
    case "DiscardDeclared": return [[d.seat, DISCARD_WORDS[d.count] || `Dame ${d.count}`]];
    case "Passed": return [[d.seat, "Paso"]];
    case "BetPlaced": return [[d.seat, d.amount === 2 ? "Envido" : `Envido ${d.amount}`]];
    case "BetRaised": return [[d.seat, `${d.increment} más`]];
    case "OrdagoDeclared": return [[d.seat, "¡Órdago!"]];
    case "BetAccepted": case "OrdagoAccepted": return [[d.seat, "Quiero"]];
    case "BetRejected": return [[d.seat, "No quiero"]];
    case "ParesDeclared": return d.holders.map((x, i) => [i, x ? "Pares sí" : "Pares no"]);
    case "JuegoDeclared": return d.holders.map((x, i) => [i, x ? "Juego sí" : "Juego no"]);
    default: return [];
  }
}
function singCalls(data) {
  const events = (data.game && data.game.events) || [];
  const last = events.length ? events[events.length - 1].seq : 0;
  if (state.lastCall == null || last < state.lastCall) { state.lastCall = last; return; }
  const fresh = events.filter((e) => e.seq > state.lastCall);
  state.lastCall = last;
  if (state.quiet || state.dealtShown < data.game.hand_number - 1) return;
  const mano = data.game.mano ?? 0;
  for (const e of fresh) {
    let calls = callFor(e);
    // Pares y juego se cantan en orden, empezando por la mano.
    if (e.type === "ParesDeclared" || e.type === "JuegoDeclared") calls = [0, 1, 2, 3].map((k) => calls[(mano + k) % 4]);
    for (const [seat, text] of calls) speak(text, data.room.seats[seat] && data.room.seats[seat].avatar.id);
    partnerAnswered(e, data);
  }
}

// En el Mus basta con que conteste uno de la pareja: si tu compañero quiere (o sube)
// antes que tú, a ti ya no te pregunta. Se avisa para que se entienda.
const PARTNER_SAYS = {
  BetAccepted: "ha dicho «Quiero» por la pareja: en el Mus basta con que conteste uno, así que a ti ya no te toca.",
  OrdagoAccepted: "ha querido el órdago por la pareja.",
  BetRaised: "ha subido el envite por la pareja.",
  BetRejected: "no quiere; ahora decides tú.",
};
function partnerAnswered(e, data) {
  const g = data.game, mate = (g.seat + 2) % 4;
  if (e.data.seat !== mate || !PARTNER_SAYS[e.type]) return;
  if (e.type === "BetRejected" && !g.to_act.includes(g.seat)) return;
  state.notice = { text: `${g.names[mate]} ${PARTNER_SAYS[e.type]}`, until: Date.now() + 6000 };
  setTimeout(() => render(), 6100);
}

// iPhone/iPad sólo dejan hablar después de un toque: se «despierta» la voz con el primero.
function unlockVoice() {
  if ("speechSynthesis" in window) { const u = new SpeechSynthesisUtterance(" "); u.volume = 0; speechSynthesis.speak(u); }
}

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

// Botones de opción (uno elegido de varios).
function segmented(options, value, onPick) {
  const box = h("div", { class: "seg" });
  for (const [v, label] of options) {
    const b = h("button", { type: "button", class: v === value ? "on" : "" }, label);
    b.addEventListener("click", () => { for (const x of box.children) x.classList.toggle("on", x === b); onPick(v); });
    box.append(b);
  }
  return box;
}

// Elegir compañero, con su ficha y su voz.
function partnerPicker(list, selectedId, onPick) {
  const card = h("div", { class: "pcard" });
  const show = (a) => card.replaceChildren(face(a),
    h("div", {}, h("b", {}, a.nickname), h("div", { class: "muted" }, `Estilo: ${a.style}`), h("i", {}, `«${a.sample}»`),
      h("div", {}, h("button", { type: "button", class: "secondary small", onclick: () => { unlockVoice(); speak(a.sample, a.id); } }, `🔊 Escuchar a ${a.nickname}`))));
  const grid = h("div", { class: "avatars" });
  for (const a of list) {
    const btn = h("button", { type: "button", class: "avatar-choice" + (a.id === selectedId ? " selected" : "") }, face(a), a.nickname, h("small", {}, a.style));
    btn.addEventListener("click", () => { for (const b of grid.children) b.classList.toggle("selected", b === btn); onPick(a.id); show(a); });
    grid.append(btn);
  }
  const first = list.find((a) => a.id === selectedId);
  if (first) show(first);
  return h("div", {}, grid, card);
}

// --- Torneo: tres rondas contra parejas de bots (el progreso se guarda en este navegador) ---
const ROUNDS = [
  { name: "Cuartos de final", level: "sencillo" },
  { name: "Semifinal", level: "medio" },
  { name: "Gran final", level: "medio" },
];

function newTorneo(partner, target, signals, phrases) {
  const pool = state.avatars.filter((a) => a.id !== state.me.avatar && a.id !== partner).map((a) => a.id);
  for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]]; }
  const rivals = [0, 1, 2].map((r) => [pool[(2 * r) % pool.length], pool[(2 * r + 1) % pool.length]]);
  return { partner, target, signals, phrases, rivals, round: 1, results: [] };
}

function loadTorneo() {
  try { return JSON.parse(localStorage.getItem("torneo") || "null"); } catch (e) { return null; }
}
function saveTorneo(t) {
  try { if (t) localStorage.setItem("torneo", JSON.stringify(t)); else localStorage.removeItem("torneo"); } catch (e) { /* sin almacenamiento */ }

}

function torneoBanner() {
  const t = loadTorneo();
  if (!t || t.results.length >= 3 || t.results.includes(false)) return null;
  return h("div", { class: "tbanner" }, `🏆 Tienes un torneo en curso: ${ROUNDS[t.round - 1].name}. `,
    h("button", { class: "small", onclick: tournamentScreen }, "Continuar"));
}

function tournamentScreen() {
  closeSocket();
  document.body.classList.remove("playing");
  const t = loadTorneo();
  if (!t) return lobby();
  const nick = (id) => (state.avatars.find((a) => a.id === id) || { nickname: id }).nickname;
  const lost = t.results.includes(false), champion = t.results.length >= 3 && !lost;
  const err = h("p", { class: "error" });
  const cards = ROUNDS.map((r, i) => {
    const res = t.results[i];
    const status = res === true ? ["✓ Superada", "won"] : res === false ? ["✗ Eliminados", "lost"] : i + 1 === t.round && !lost ? ["En juego", "now"] : ["Bloqueada", "locked"];
    return h("div", { class: `round ${status[1]}` },
      h("div", { class: "rhead" }, h("b", {}, `Ronda ${i + 1}`), h("span", { class: "rtag" }, status[0])),
      h("h3", {}, r.name),
      h("div", { class: "rivals" }, h("small", {}, "Rivales a batir:"), h("b", {}, `🔴 ${nick(t.rivals[i][0])} y ${nick(t.rivals[i][1])}`)),
      h("small", { class: "muted" }, res === true ? "¡Derrotados!" : res === false ? "Os han ganado esta vez." : i + 1 === t.round ? "Tu próxima partida." : "Esperando rival."));
  });
  const play = async () => {
    unlockVoice();
    try {
      const room = await api("POST", "/api/rooms", { mode: "con_bot", signals: t.signals, phrases: t.phrases, level: ROUNDS[t.round - 1].level,
        target: t.target, partner: t.partner, rivals: t.rivals[t.round - 1], tournament_round: t.round });
      await api("POST", `/api/rooms/${room.code}/start`);
      enterRoom(room);
    } catch (e) { err.textContent = e.message; }
  };
  mount(h("section", { class: "panel torneo" },
    h("small", { class: "kicker" }, "GRAN TORNEO DE MUS.ST"),
    h("h2", {}, champion ? "🏆 ¡¡Campeones del torneo!! 🏆" : lost ? "Fin del torneo" : "Cuadro de eliminatorias (3 rondas)"),
    h("p", { class: "muted" }, `Tú y ${nick(t.partner)} contra las parejas del torneo · a ${t.target} tantos`),
    h("div", { class: "rounds" }, cards),
    champion || lost
      ? h("button", { class: "big go", onclick: () => { saveTorneo(null); lobby(); } }, "🏆 Jugar otro torneo")
      : h("button", { class: "big go", onclick: play }, `⚔️ Comenzar ${ROUNDS[t.round - 1].name}`),
    h("button", { class: "secondary", onclick: lobby }, "Volver al menú"), err));
}

// Al acabar una partida del torneo, se apunta el resultado.
function finishTorneoGame(g, room) {
  const t = loadTorneo();
  if (!t || room.tournament_round !== t.round || t.results.length >= t.round) return;
  const won = g.winner === (g.seat % 2 ? "B" : "A");
  t.results.push(won);
  if (won && t.round < 3) t.round += 1;
  saveTorneo(t);
}

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
  const createButton = h("button", { class: "big go", onclick: () => create() }, "Jugar");
  // Partida rápida o torneo, a 40 o a 30 tantos, y compañero elegido (sólo contra bots).
  const opts = { kind: "rapida", target: 40, partner: null };
  const kind = segmented([["torneo", "🏆 Torneo (3 rondas)"], ["rapida", "🃏 Partida rápida"]], opts.kind, (v) => { opts.kind = v; refresh(); });
  const target = segmented([[40, "40 piedras (8 amarracos)"], [30, "30 piedras (6 amarracos)"]], opts.target, (v) => { opts.target = v; });
  const others = state.avatars.filter((a) => a.id !== state.me.avatar);
  opts.partner = others[0] && others[0].id;
  const partnerBox = h("div", {}, partnerPicker(others, opts.partner, (id) => { opts.partner = id; }));
  const botOnly = h("div", { class: "botonly" },
    h("label", {}, "Modo de juego"), kind,
    h("label", {}, "Meta del juego"), target,
    h("label", {}, "Elige a tu compañero"), partnerBox);
  const refresh = () => {
    const bots = mode.value === "con_bot";
    botOnly.hidden = !bots;
    levelBox.hidden = bots && opts.kind === "torneo";
    createButton.textContent = !bots ? "Crear sala" : opts.kind === "torneo" ? "🏆 Entrar al torneo" : "Jugar";
  };
  mode.addEventListener("change", refresh);
  const create = async () => {
    unlockVoice();
    if (mode.value === "con_bot" && opts.kind === "torneo") {
      saveTorneo(newTorneo(opts.partner, opts.target, signals.checked, phrases.checked));
      return tournamentScreen();
    }
    try {
      const bots = mode.value === "con_bot";
      const room = await api("POST", "/api/rooms", { mode: mode.value, signals: signals.checked, phrases: phrases.checked, level: level.value,
        target: bots ? opts.target : 40, partner: bots ? opts.partner : null });
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
  const levelBox = h("div", {}, h("label", {}, "Nivel de los bots"), level);
  const me = state.me;
  refresh();
  mount(
    h("div", { class: "grid2" },
      h("section", { class: "panel" },
        h("h2", {}, "Nueva partida"),
        h("label", {}, "Modo"), mode,
        torneoBanner(),
        botOnly,
        h("label", { class: "check" }, signals, "Con señas (los compañeros se pueden pasar señas… si nadie más mira)"),
        levelBox,
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
    me.admin && adminPanel(),
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

// Panel de administración: estadísticas y contraseña nueva para quien la olvide.
function adminPanel() {
  const box = h("section", { class: "panel admin" }, h("h2", {}, "🛠️ Administración"), h("p", { class: "muted" }, "Cargando…"));
  const pct = (x) => `${(x * 100).toFixed(1).replace(".", ",")} %`;
  const user = h("input", { type: "text", maxlength: 24, placeholder: "usuario" });
  const pass = h("input", { type: "password", minlength: 8, placeholder: "contraseña nueva (8 o más)" });
  const msg = h("p", { class: "muted" });
  const reset = async () => {
    try { await api("POST", "/api/admin/password", { username: user.value.trim(), password: pass.value }); msg.textContent = `Contraseña cambiada para ${user.value.trim()}.`; pass.value = ""; }
    catch (e) { msg.textContent = e.message; }
  };
  api("GET", "/api/admin/stats").then((s) => {
    const rows = s.bots_vs_people.map((r) => h("tr", {}, h("td", {}, r.bot), h("td", {}, String(r.games)), h("td", {}, String(r.wins)),
      h("td", {}, `${pct(r.rate)} (${pct(r.low)} a ${pct(r.high)})`)));
    box.replaceChildren(h("h2", {}, "🛠️ Administración"),
      h("p", {}, `${s.users} usuarios · ${s.games} partidas guardadas`),
      h("h3", {}, "Bots contra personas"),
      rows.length ? h("table", { class: "list" }, h("thead", {}, h("tr", {}, h("th", {}, "Bot"), h("th", {}, "Partidas"), h("th", {}, "Gana el bot"), h("th", {}, "% (intervalo 95 %)"))), h("tbody", {}, rows))
        : h("p", { class: "muted" }, "Todavía no hay partidas terminadas de personas contra bots."),
      h("h3", {}, "Poner una contraseña nueva"), user, pass, h("button", { onclick: reset }, "Cambiar contraseña"), msg);
  }).catch((e) => box.replaceChildren(h("h2", {}, "🛠️ Administración"), h("p", { class: "error" }, e.message)));
  return box;
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
  state.room = room; state.view = null; state.selected.clear(); state.bubbles = {}; state.lastPhrase = 0; state.lastCall = null;
  state.summarySeen = 0; state.phraseLog = []; state.dealing = null; state.dealtShown = 0;
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
    singCalls(data);
    for (const p of data.phrases) if (p.id > state.lastPhrase) {
      state.lastPhrase = p.id;
      const who = data.room.seats[p.seat] ? data.room.seats[p.seat].name : "";
      state.phraseLog.push(`${who}: «${p.text}»`);
      if (!state.quiet && state.dealtShown >= data.game?.hand_number - 1) speak(p.text, data.room.seats[p.seat]?.avatar.id);
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

// Naipe: baraja dibujada (cards.js) o imagen real de static/cards/<código>.png si existe.
// opts: small (resúmenes y manos ajenas), selected, glow (cuenta en el lance), onclick,
// fly ([dx, dy]: llega volando desde la baraja).
function cardEl(code, opts = {}) {
  const mini = Boolean(opts.small);
  let art;
  if (!code) art = MusCards.back({ mini });
  else if (state.deckImages.includes(code)) art = h("img", { src: `/static/cards/${code}.png`, alt: "" });
  else art = MusCards.svg(code, { mini });
  const num = code ? Number(code.slice(0, -1)) : 0;
  const title = code ? `${FIGURES[num] || num} de ${SUITS[code.slice(-1)]}` : "carta boca abajo";
  const cls = `card${mini ? " mini" : ""}${opts.selected ? " sel" : ""}${opts.glow ? " glow" : ""}${opts.fly ? " fly" : ""}`;
  const node = h(opts.onclick ? "button" : "span", { class: cls, onclick: opts.onclick, title, "aria-label": title }, art);
  if (opts.fly) { node.style.setProperty("--fx", `${opts.fly[0]}px`); node.style.setProperty("--fy", `${opts.fly[1]}px`); }
  return node;
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
    // Piedras en juego (o ya ganadas con un «no quiero») junto a cada lance.
    let stake = 0, owner = "";
    if (outcome && outcome.resolution === "rejected") { stake = outcome.immediate_points; owner = outcome.team === mineTeam ? " ours" : " theirs"; }
    else if (outcome && outcome.resolution === "accepted") stake = outcome.amount;
    else if (cls === "now" && g.bet && !g.bet.is_ordago) stake = Math.max(g.bet.pending, g.bet.accepted);
    return h("div", { class: `lance ${cls}` }, h("span", { class: "lname" }, LANCES[lance]),
      stake > 0 && h("span", { class: `stake${owner}`, title: `${stake} piedra${stake === 1 ? "" : "s"}` }, stonePile(stake)),
      h("span", {}, status));
  }));
}

// Amarracos (5 tantos) y piedras (1 tanto) dibujados.
function stonePile(tantos) {
  const row = h("span", { class: "stonepile" });
  for (let i = 0; i < Math.floor(tantos / 5); i++) row.append(h("span", { class: "amarraco" }));
  for (let i = 0; i < tantos % 5; i++) row.append(h("span", { class: "piedra" }));
  return row;
}

// --- Aviso de turno ---------------------------------------------------------------------------
function turnBanner(g) {
  if (g.phase === "game_over") return null;
  const mine = g.to_act.includes(g.seat);
  const n = (s) => g.names[s];
  const holders = g.lance === "pares" ? g.pares_holders : g.lance === "juego" ? g.juego_holders : null;
  if (g.phase === "lance" && holders && !holders[g.seat]) {
    const playing = [0, 1, 2, 3].filter((s) => holders[s]).map(n).join(", ");
    return h("div", { class: "banner wait" },
      `No llevas ${g.lance}, pero la jugada sigue: la juegan ${playing}. Le toca a ${g.to_act.map(n).join(", ")}…`);
  }
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
  grande: "tiene las cartas más altas (los reyes mandan)", chica: "tiene las cartas más bajas (los ases mandan)",
  pares: "tiene los mejores pares", juego: "tiene el mejor juego (la 31 es la mejor)", punto: "tiene más puntos (sin juego)",
};
const WHAT_COUNTS = { grande: (i) => i.grande, chica: (i) => i.chica, pares: (i) => i.pares, juego: (i) => i.juego, punto: (i) => i.juego };

function explainPoints(e, who) {
  const d = e.data, n = d.points, team = who(d.team).toLowerCase(), p = `+${n} piedra${n === 1 ? "" : "s"} para ${team}`;
  switch (d.reason) {
    case "envite": return `Se quiso un envite de ${n}: ${p}.`;
    case "paso": return `Nadie envidó (en paso): el lance vale 1. ${p}.`;
    case "negada": return `Envidaron y no se quiso: la «negada» vale 1. ${p}.`;
    case "envite_no_querido": return `Subieron y no se quiso: se cobra lo que ya se había querido. ${p}.`;
    case "pares": return `Valor de los pares de la pareja (pareja 1, medias 2, duples 3): ${p}.`;
    case "juego": return `Valor del juego de la pareja (la 31 vale 3, otro juego 2): ${p}.`;
    case "punto": return `El punto vale 1: ${p}.`;
    case "ordago": return `¡Órdago querido! Quien gana el lance gana la partida.`;
    default: return `${p}.`;
  }
}

function infoParts(cards) {
  const t = handInfo(cards).replace("Tu jugada: ", "").split(" · ");
  return { pares: t[0], juego: t[1], grande: t[2], chica: t[3] };
}

// Explicación de la jugada que acaba de terminar, lance a lance. Lo último: repartir.
const HAND_END_PAUSE = 2500; // ms

// Durante la pausa, el centro de la mesa dice «Jugada terminada» en vez del resumen.
function summaryWaiting(g, room) {
  const node = handSummary(g, room);
  return node && node.classList.contains("ending") ? node : null;
}

function handSummary(g, room) {
  const over = g.phase === "game_over";
  const hand = over ? g.hand_number : g.hand_number - 1;
  if (hand < 1 || state.summarySeen >= hand) return null;
  if (!over && !room.awaiting_deal) return null;
  const evs = g.events.filter((e) => e.hand === hand);
  const points = evs.filter((e) => e.type === "PointsAwarded");
  if (!points.length) return null;
  // Al acabar la jugada, una pausa antes del resumen: que terminen de hablar y se vea
  // que ha acabado (si no llevas pares ni juego, el resto se resuelve en un momento).
  if (!state.handEnd || state.handEnd.hand !== hand) state.handEnd = { hand, at: Date.now() };
  const waited = Date.now() - state.handEnd.at;
  const talking = "speechSynthesis" in window && speechSynthesis.speaking;
  if (waited < HAND_END_PAUSE || (talking && waited < 15000)) {
    if (!state.summaryTimer) state.summaryTimer = setTimeout(() => { state.summaryTimer = null; render(); }, 500);
    return h("div", { class: "dealpanel ending" }, h("b", {}, "Jugada terminada"), h("p", { class: "muted" }, "Contando los tantos…"));
  }
  const reveal = evs.find((e) => e.type === "HandsRevealed");
  const hands = reveal ? reveal.data.hands : null;
  const mineTeam = g.seat % 2 ? "B" : "A";
  const who = (t) => (t === mineTeam ? "Nosotros" : "Ellos");
  const last = points[points.length - 1].data.tantos_after;
  // Siempre en el orden del recuento: grande, chica, pares, juego (o punto).
  const lances = ["grande", "chica", "pares", "juego", "punto"].filter((l) => points.some((e) => e.data.lance === l));
  const steps = [...lances, "resumen"];
  if (!state.summaryTab || !steps.includes(state.summaryTab)) state.summaryTab = steps[0];
  const tab = state.summaryTab, idx = steps.indexOf(tab);
  const finish = () => { state.summarySeen = hand; state.summaryTab = null; if (over) render(); else startDeal(g); };
  const next = () => { if (idx + 1 < steps.length) { state.summaryTab = steps[idx + 1]; render(); } else finish(); };
  let body;
  if (tab === "resumen") {
    const ours = points.filter((e) => e.data.team === mineTeam).reduce((a, e) => a + e.data.points, 0);
    const theirs = points.filter((e) => e.data.team !== mineTeam).reduce((a, e) => a + e.data.points, 0);
    const mine = last[mineTeam === "A" ? 0 : 1], other = last[mineTeam === "A" ? 1 : 0];
    body = h("div", {},
      h("div", { class: "totals" },
        h("div", { class: "good" }, h("small", {}, "Nosotros en esta jugada"), h("b", {}, `+${ours}`)),
        h("div", { class: "bad" }, h("small", {}, "Ellos en esta jugada"), h("b", {}, `+${theirs}`))),
      h("div", { class: "stonesrow" }, scoreStones(mine, "Nosotros"), scoreStones(other, "Ellos")),
      h("p", { class: "muted" }, `Una piedra es un tanto; cinco piedras hacen un amarraco. Se juega a ${g.target_score} tantos (${g.target_score / 5} amarracos).`));
  } else {
    const won = points.filter((e) => e.data.lance === tab);
    const resolved = evs.find((e) => e.type === "LanceResolved" && e.data.lance === tab);
    const team = won.length ? won[0].data.team : null;
    const total = won.reduce((a, e) => a + e.data.points, 0);
    let headline;
    if (resolved && hands) {
      const w = resolved.data.winner;
      headline = `Gana ${g.names[w]} (${who(team).toLowerCase()}) porque ${LANCE_WHY[tab]}: ${WHAT_COUNTS[tab](infoParts(hands[w]))}.`;
    } else {
      const closed = evs.find((e) => e.type === "LanceClosed" && e.data.lance === tab);
      const lance = LANCES[tab].toLowerCase();
      if (closed && closed.data.resolution === "rejected") {
        headline = `Se lo lleva ${who(team).toLowerCase()} porque envidaron y la otra pareja dijo «no quiero»: cuando no se quiere, no hace falta comparar las cartas.`;
      } else {
        headline = `Se lo lleva ${who(team).toLowerCase()} sin envites: solo esa pareja llevaba ${lance}, así que no había con quién comparar.`;
      }
    }
    body = h("div", {},
      h("div", { class: `winner ${team === mineTeam ? "good" : "bad"}` },
        h("b", {}, headline),
        h("ul", {}, won.map((e) => h("li", {}, explainPoints(e, who)))),
        h("div", { class: "lancetotal" }, `Total de la ${LANCES[tab]}: +${total} para ${who(team).toLowerCase()}`)),
      hands && h("div", { class: "fourhands" }, [0, 1, 2, 3].map((s) => {
        const glow = countsIn(tab, hands[s]);
        const winnerSeat = resolved && resolved.data.winner === s;
        return h("div", { class: `handbox ${s % 2 === g.seat % 2 ? "ours" : "theirs"}${winnerSeat ? " win" : ""}` },
          h("div", { class: "hb-head" }, h("b", {}, `${winnerSeat ? "👑 " : ""}${g.names[s]}`), h("small", {}, s === g.seat ? "tú" : s % 2 === g.seat % 2 ? "tu pareja" : "rival")),
          h("div", { class: "hb-info" }, WHAT_COUNTS[tab](infoParts(hands[s]))),
          h("div", { class: "cards" }, hands[s].map((c, i) => cardEl(c, { small: true, glow: glow[i] }))));
      })));
  }
  const lastStep = idx + 1 === steps.length;
  return h("div", { class: "overlay" },
    h("div", { class: "summary" },
      h("div", { class: "sum-head" }, h("h2", {}, `Jugada ${hand} · ${tab === "resumen" ? "Resultado" : `a la ${LANCES[tab]}`}`),
        h("span", { class: "muted" }, `Paso ${idx + 1} de ${steps.length}`)),
      h("div", { class: "tabs" }, steps.map((t, i) => h("span", { class: `tab${t === tab ? " on" : i < idx ? " done" : ""}` }, t === "resumen" ? "Resultado" : LANCES[t]))),
      body,
      h("button", { class: "big go", onclick: next },
        lastStep ? (over ? "Ver la mesa" : "🃏 Repartir nueva jugada") : `Siguiente: ${steps[idx + 1] === "resumen" ? "resultado" : LANCES[steps[idx + 1]]} ▶`)));
}

// --- Reparto ----------------------------------------------------------------------------------
const DEAL_STEP_MS = 160;

function startDeal(g) {
  unlockVoice();
  const hand = g.hand_number;
  if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.send(JSON.stringify({ deal: hand }));
  animateDeal(hand);
}

function animateDeal(hand) {
  if (state.dealing && state.dealing.hand === hand) return;
  state.dealing = { hand, n: 0 };
  const tick = () => {
    if (!state.dealing || state.dealing.hand !== hand) return;
    state.dealing.n += 1;
    if (state.dealing.n >= 16) { state.dealing = null; state.dealtShown = hand; }
    else setTimeout(tick, DEAL_STEP_MS);
    render();
  };
  setTimeout(tick, DEAL_STEP_MS);
  render();
}

// Cuántas cartas ve ya cada asiento durante el reparto (de una en una, empezando por la mano).
function dealtCount(g, seat) {
  if (state.dealtShown >= g.hand_number) return 4;
  if (!state.dealing || state.dealing.hand !== g.hand_number) return 0;
  const offset = (seat - g.mano + 4) % 4, n = state.dealing.n;
  return n > offset ? Math.floor((n - offset - 1) / 4) + 1 : 0;
}

function dealPanel(g) {
  const n = g.names;
  return h("div", { class: "dealpanel" },
    h("p", {}, `Jugada ${g.hand_number}: reparte ${n[g.dealer]} y es mano ${n[g.mano]}.`),
    h("button", { class: "big go", onclick: () => startDeal(g) }, g.hand_number === 1 ? "🃏 Repartir" : "🃏 Repartir nueva jugada"));
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
  bar.append(signalsPanel(g));
  bar.append(h("div", { class: "barfoot" },
    h("button", { class: "small", onclick: () => { state.voice = !state.voice; writePref("voz", state.voice); if (state.voice) unlockVoice(); render(); } },
      state.voice ? "🔊 Voces activadas" : "🔇 Voces apagadas")));
  return bar;
}

// Señas: sólo las ve quien está mirando al que las hace (las miradas de la mesa son públicas).
const SIGNAL_HELP = {
  dos_reyes: "pareja de reyes", dos_ases: "pareja de ases", pares: "una pareja", medias_reyes: "tres reyes",
  medias_ases: "tres ases", medias: "un trío", duples: "duples (dos parejas)", juego: "tengo juego",
  treinta_y_una: "tengo la 31", treinta: "30 de punto", veintinueve: "29 de punto", ciego: "no tengo nada",
};

function signalsPanel(g) {
  if (!state.room.signals) {
    return h("div", { class: "signals off" }, "🤫 Partida sin señas. Para jugar con señas, marca «Con señas» al crear la partida.");
  }
  const me = g.seat, mate = (me + 2) % 4;
  const gaze = g.gaze || [];
  const mateLooks = gaze[mate] === me;
  const rivalsLook = [0, 1, 2, 3].filter((s) => s % 2 !== me % 2 && gaze[s] === me).map((s) => g.names[s]);
  const legal = g.legal.actions.filter((a) => a.type === "signal");
  const open = state.signalsOpen || mateLooks;
  const toggle = h("button", { class: "small sig-toggle", onclick: () => { state.signalsOpen = !state.signalsOpen; render(); } },
    open ? "🤫 Ocultar señas" : "🤫 Echar seña");
  if (!open) {
    return h("div", { class: "signals closed" }, toggle,
      rivalsLook.length > 0 && h("span", { class: "warn" }, `👀 Te mira ${rivalsLook.join(" y ")}`));
  }
  const box = h("div", { class: `signals${mateLooks ? " ready" : ""}` },
    h("div", { class: "sig-head" },
      toggle,
      h("span", {}, mateLooks ? `¡${g.names[mate]} te está mirando! Es el momento.` : `${g.names[mate]} no te mira ahora: espera a que te mire.`),
      rivalsLook.length > 0 && h("span", { class: "warn" }, `👀 Cuidado: te mira ${rivalsLook.join(" y ")}`)));
  if (!legal.length) box.append(h("div", { class: "muted" }, "Ahora no puedes hacer señas (se hacen después de cortar el mus)."));
  else box.append(h("div", { class: "muted" }, "Sólo puedes señar lo que llevas: las señas falsas no están permitidas."));
  const row = h("div", { class: "sig-buttons" });
  for (const a of legal) row.append(h("button", { class: "small sig", onclick: () => send(a) }, h("b", {}, SIGNALS[a.signal] || a.signal), h("small", {}, SIGNAL_HELP[a.signal] || "")));
  box.append(row);
  return box;
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

// Tanteo con amarracos (5 tantos) y piedrecitas (1 tanto), como en la mesa de verdad.
function scoreStones(tantos, label) {
  const box = h("div", { class: "stones", title: `${tantos} tantos = ${Math.floor(tantos / 5)} amarracos y ${tantos % 5} piedras` });
  if (label) box.append(h("small", {}, label));
  const row = stonePile(tantos);
  if (!tantos) row.append(h("span", { class: "muted" }, "sin piedras"));
  box.append(row, h("div", { class: "stonecount" }, `${tantos} tanto${tantos === 1 ? "" : "s"} · ${Math.floor(tantos / 5)} amarr. + ${tantos % 5} p.`));
  return box;
}

function scoreBox(g, ours) {
  const team = ours ? g.seat % 2 : 1 - (g.seat % 2);
  const tantos = g.score.tantos[team];
  return h("div", { class: `teambox ${ours ? "ours" : "theirs"}` },
    h("div", { class: "tb-head" }, h("span", { class: "dot" }), h("span", { class: "tname" }, ours ? "Tu pareja" : "Rivales"),
      h("span", { class: "big" }, String(tantos), h("small", {}, `/${g.target_score}`))),
    scoreStones(tantos),
    h("div", { class: "faltan" }, tantos >= g.target_score ? "¡Juego!" : `Faltan ${g.target_score - tantos}`));
}

function tableScreen() {
  const v = state.view, g = v.game, room = v.room, me = g.seat;
  document.body.classList.add("playing");
  // Si otra persona ha repartido, también se ve el reparto aquí.
  if (!room.awaiting_deal && state.dealtShown < g.hand_number && !state.dealing && g.phase !== "game_over") animateDeal(g.hand_number);
  const dealing = room.awaiting_deal || (state.dealing && state.dealing.hand === g.hand_number);
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
    if (!dealing) {
      if (said[s]) chips.push(h("span", { class: `chip say${said[s].includes("ÓRDAGO") ? " hot" : ""}` }, said[s]));
      if (s in declared.pares) chips.push(h("span", { class: `chip ${declared.pares[s] ? "yes" : "no"}` }, declared.pares[s] ? "Pares sí" : "Pares no"));
      if (s in declared.juego) chips.push(h("span", { class: `chip ${declared.juego[s] ? "yes" : "no"}` }, declared.juego[s] ? "Juego sí" : "Juego no"));
      if (g.gaze && g.gaze[s] != null && s !== me) chips.push(h("span", { class: "chip look" }, `👀 mira a ${g.gaze[s] === me ? "ti" : g.names[g.gaze[s]]}`));
    }
    const count = dealtCount(g, s);
    const fromDealer = (k) => {
      if (!(state.dealing && k === count - 1)) return null;
      const [ax, ay] = POS_VECTORS[(g.dealer - me + 4) % 4], [bx, by] = POS_VECTORS[pos];
      return [(ax - bx) * 220, (ay - by) * 180];
    };
    let cards;
    if (s === me) {
      cards = g.my_hand.slice(0, count).map((c, k) => cardEl(c, {
        selected: state.selected.has(c), fly: fromDealer(k),
        onclick: !dealing && g.phase === "discard" && g.to_act.includes(me) ? () => { state.selected.has(c) ? state.selected.delete(c) : state.selected.add(c); render(); } : null,
      }));
    } else if (revealed && revealed[s] && revealed[s].length) {
      cards = revealed[s].map((c) => cardEl(c, { small: true }));
    } else {
      cards = Array.from({ length: count }, (_, k) => cardEl(null, { small: true, fly: fromDealer(k) }));
    }
    const deck = s === g.dealer && g.phase !== "game_over" && h("div", { class: "deck", title: "Baraja" },
      h("span", { class: "card mini" }, MusCards.back({ mini: true })), h("small", {}, "Baraja"));
    return h("div", { class: `seat pos${pos}${!dealing && g.to_act.includes(s) ? " turn" : ""}${s % 2 === me % 2 ? " ours" : " theirs"}` },
      state.bubbles[s] && h("div", { class: "bubble" }, state.bubbles[s]),
      h("div", { class: "plate" },
        face(occ.avatar, dx, dy, moodFor(g, s)),
        h("div", {}, h("div", { class: "name" }, occ.name, occ.bot ? " 🤖" : ""), h("div", { class: "tags" }, tags.join(" · ")))),
      chips.length > 0 && h("div", { class: "chips" }, chips),
      h("div", { class: `hand-row${deck ? " with-deck" : ""}` }, deck, h("div", { class: `cards${s === me ? " mine" : ""}${s !== me && revealed && revealed[s] && revealed[s].length ? " shown" : ""}` }, cards)),
      s === me && !dealing && myHandChips(g.my_hand));
  });
  const mineTeam = me % 2;
  const center = h("div", { class: "center" },
    room.awaiting_deal && !state.dealing ? (summaryWaiting(g, room) || (!handSummary(g, room) && dealPanel(g)) || lanceBoard(g)) : lanceBoard(g),
    g.signals_seen.length > 0 && h("div", { class: "signals-seen" }, "🤫 Seña vista: " + g.signals_seen.map((x) => `${g.names[x.sender]} → ${SIGNALS[x.signal]} (${SIGNAL_HELP[x.signal] || ""})`).join(", ")),
    g.winner && h("h2", {}, g.winner === (mineTeam ? "B" : "A") ? "🏆 ¡Habéis ganado!" : "Habéis perdido"),
    g.winner && (room.tournament_round
      ? h("button", { class: "big go", onclick: () => { finishTorneoGame(g, room); tournamentScreen(); } }, "🏆 Ver el torneo")
      : h("button", { class: "big go", onclick: () => { document.body.classList.remove("playing"); lobby(); } }, "Volver al menú")));
  const lines = g.events.map((e) => describe(e, g.names, me)).filter(Boolean).slice(-40);
  const log = h("div", { class: "log" }, lines.map((t) => h("div", {}, t)),
    state.phraseLog.slice(-5).map((p) => h("div", { class: "said" }, `💬 ${p}`)));
  const header = h("div", { class: "gamehead" },
    scoreBox(g, true),
    h("div", { class: "lancepill" }, h("small", {}, "LANCE"), " ", dealing ? "REPARTO" : phaseLabel(g).toUpperCase()),
    scoreBox(g, false));
  mount(
    header,
    !dealing && turnBanner(g),
    state.notice && Date.now() < state.notice.until && h("div", { class: "banner notice" }, `🤝 ${state.notice.text}`),
    linkStatus(),
    h("div", { class: "felt" }, h("div", { class: "table" }, seats, center)),
    !dealing && actionBar(g),
    h("p", { class: "error", id: "table-error" }),
    h("details", { class: "panel history" }, h("summary", {}, "📜 Lo que ha pasado"), log,
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: state.quiet, onchange: (ev) => { state.quiet = ev.target.checked; } }), "Silenciar frases")),
    !summaryWaiting(g, room) && handSummary(g, room));
  log.scrollTop = log.scrollHeight;
}

// --- Arranque ------------------------------------------------------------------------------

(async function boot() {
  try {
    const pack = await api("GET", "/api/avatars");
    state.avatars = pack.avatars; state.notice = pack.aviso;
    state.deckImages = (await api("GET", "/api/deck")).images;
    document.getElementById("notice").textContent = pack.aviso;
  } catch (e) { /* sin avatares no se puede seguir */ }
  try { state.me = await api("GET", "/api/me"); lobby(); }
  catch (e) { authScreen(); }
})();
