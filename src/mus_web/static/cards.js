"use strict";
// Baraja española dibujada en SVG (sin imágenes externas). Si existen imágenes en
// static/cards/<código>.png (p. ej. 12O.png), la web las usa en su lugar.
//   MusCards.svg(code, {mini})  → elemento <svg> del naipe
//   MusCards.back({mini})       → reverso
(function () {
  const NS = "http://www.w3.org/2000/svg";
  let uid = 0;

  function el(name, attrs = {}, parent) {
    const e = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (parent) parent.append(e);
    return e;
  }

  const INK = { O: "#9a6b00", C: "#b3261e", E: "#1f4e8c", B: "#2d6a2f" };
  const ROBE = { O: "#b3261e", C: "#1f4e8c", E: "#7a1f6e", B: "#2d6a2f" };

  // --- Símbolos de los palos (dibujados en una caja de 40×40, centrados en 0,0) ---------
  function oro(g, defs) {
    const id = `oro${uid++}`;
    const grad = el("radialGradient", { id, cx: "40%", cy: "35%", r: "70%" }, defs);
    el("stop", { offset: "0%", "stop-color": "#fff3b0" }, grad);
    el("stop", { offset: "55%", "stop-color": "#e8b923" }, grad);
    el("stop", { offset: "100%", "stop-color": "#a87400" }, grad);
    el("circle", { r: 18, fill: `url(#${id})`, stroke: "#6e4c00", "stroke-width": 2 }, g);
    el("circle", { r: 12, fill: "none", stroke: "#8a5f00", "stroke-width": 1.6 }, g);
    for (let i = 0; i < 8; i++) {
      const a = (i * Math.PI) / 4;
      el("circle", { cx: 15 * Math.cos(a), cy: 15 * Math.sin(a), r: 1.4, fill: "#6e4c00" }, g);
    }
    el("circle", { r: 5, fill: "#b3261e", stroke: "#6e4c00", "stroke-width": 1 }, g);
  }

  function copa(g) {
    el("path", { d: "M-14,-17 h28 c0,13 -6,19 -12,20 v8 c0,2 6,3 8,6 h-20 c2,-3 8,-4 8,-6 v-8 c-6,-1 -12,-7 -12,-20z", fill: "#c62f24", stroke: "#6b1410", "stroke-width": 1.6 }, g);
    el("path", { d: "M-14,-17 h28 v4 h-28z", fill: "#e8b923", stroke: "#6e4c00", "stroke-width": 1.2 }, g);
    el("ellipse", { cx: 0, cy: 17.5, rx: 11, ry: 2.6, fill: "#e8b923", stroke: "#6e4c00", "stroke-width": 1.2 }, g);
    el("path", { d: "M-8,-10 c0,7 3,11 5,12", stroke: "#ffb3a8", "stroke-width": 2, fill: "none", "stroke-linecap": "round" }, g);
  }

  function espada(g) {
    el("path", { d: "M0,-20 L3.2,-15 L3.2,9 L-3.2,9 L-3.2,-15 Z", fill: "#7fa7d9", stroke: "#1f4e8c", "stroke-width": 1.4 }, g);
    el("path", { d: "M0,-17 V8", stroke: "#e6f0ff", "stroke-width": 1 }, g);
    el("path", { d: "M-10,9 h20 l-2,3.5 h-16z", fill: "#e8b923", stroke: "#6e4c00", "stroke-width": 1.2 }, g);
    el("rect", { x: -2.4, y: 12.5, width: 4.8, height: 6, fill: "#7a4b1f" }, g);
    el("circle", { cx: 0, cy: 20, r: 2.8, fill: "#e8b923", stroke: "#6e4c00", "stroke-width": 1 }, g);
  }

  function basto(g) {
    el("path", { d: "M-4,-19 c5,-3 11,0 10,5 l-4,32 c-0.5,3 -6,3 -6.5,0 l-3,-31 c-0.5,-2.5 1,-5 3.5,-6z", fill: "#3f8f3a", stroke: "#1e4d1c", "stroke-width": 1.6 }, g);
    for (const [x, y] of [[0, -12], [2, -4], [-1, 4], [1, 11]]) {
      el("ellipse", { cx: x, cy: y, rx: 2.6, ry: 1.6, fill: "#7a4b1f" }, g);
    }
    el("path", { d: "M-2,-16 l-6,-3 M4,-9 l6,-2", stroke: "#1e4d1c", "stroke-width": 1.6, "stroke-linecap": "round" }, g);
  }

  const DRAW = { O: oro, C: copa, E: espada, B: basto };

  function symbol(parent, defs, suit, x, y, scale = 1, rotate = 0) {
    const g = el("g", { transform: `translate(${x},${y}) rotate(${rotate}) scale(${scale})` }, parent);
    DRAW[suit](g, defs);
    return g;
  }

  // Posición (x, y, giro) de los símbolos en un naipe de 200×300.
  const LAYOUT = {
    1: [[100, 150, 0, 2.6]],
    2: [[100, 95, 0], [100, 205, 180]],
    3: [[100, 80, 0], [100, 150, 0], [100, 220, 180]],
    4: [[65, 90, 0], [135, 90, 0], [65, 210, 180], [135, 210, 180]],
    5: [[65, 85, 0], [135, 85, 0], [100, 150, 0], [65, 215, 180], [135, 215, 180]],
    6: [[65, 80, 0], [135, 80, 0], [65, 150, 0], [135, 150, 0], [65, 220, 180], [135, 220, 180]],
    7: [[65, 75, 0], [135, 75, 0], [100, 118, 0], [65, 160, 0], [135, 160, 0], [65, 225, 180], [135, 225, 180]],
  };
  // Espadas y bastos se cruzan, como en la baraja tradicional.
  const CROSS = { 2: [[100, 150, 35], [100, 150, -35]], 3: [[100, 150, 35], [100, 150, -35], [100, 150, 0]] };

  function pips(svg, defs, suit, num) {
    if ((suit === "E" || suit === "B") && CROSS[num]) {
      for (const [x, y, r] of CROSS[num]) symbol(svg, defs, suit, x, y, 2.2, r);
      return;
    }
    const scale = num >= 6 ? 1.15 : 1.35;
    for (const [x, y, r, s] of LAYOUT[num]) symbol(svg, defs, suit, x, y, s || scale, suit === "O" ? 0 : r);
  }

  // --- Figuras ----------------------------------------------------------------------
  function face(svg, x, y, opts = {}) {
    el("circle", { cx: x, cy: y, r: 13, fill: "#f2c7a0", stroke: "#5a3a22", "stroke-width": 1.5 }, svg);
    el("circle", { cx: x - 4.5, cy: y - 2, r: 1.6, fill: "#2b1a0c" }, svg);
    el("circle", { cx: x + 4.5, cy: y - 2, r: 1.6, fill: "#2b1a0c" }, svg);
    el("path", { d: `M${x - 4},${y + 5} q4,3 8,0`, stroke: "#5a3a22", "stroke-width": 1.4, fill: "none" }, svg);
    if (opts.beard) el("path", { d: `M${x - 12},${y + 2} q12,22 24,0 q-4,6 -12,6 q-8,0 -12,-6z`, fill: "#e6e1d6", stroke: "#8a8478", "stroke-width": 1 }, svg);
  }

  function rey(svg, defs, suit) {
    const robe = ROBE[suit];
    el("path", { d: "M60,250 L72,140 Q100,118 128,140 L140,250 Z", fill: robe, stroke: "#2b1a0c", "stroke-width": 2 }, svg);
    el("path", { d: "M92,140 L100,250 L108,140", fill: "#f4e6c6", stroke: "#2b1a0c", "stroke-width": 1.2 }, svg);
    el("path", { d: "M60,250 Q100,262 140,250", fill: "none", stroke: "#e8b923", "stroke-width": 4 }, svg);
    face(svg, 100, 108, { beard: true });
    el("path", { d: "M84,96 L84,80 L92,88 L100,76 L108,88 L116,80 L116,96 Z", fill: "#e8b923", stroke: "#6e4c00", "stroke-width": 1.6 }, svg);
    for (const cx of [88, 100, 112]) el("circle", { cx, cy: 92, r: 1.8, fill: "#b3261e" }, svg);
    symbol(svg, defs, suit, 140, 175, 1.1, suit === "O" || suit === "C" ? 0 : 20);
  }

  function caballo(svg, defs, suit) {
    // Caballo
    el("path", { d: "M45,215 Q50,180 90,178 L140,176 Q160,150 152,128 L170,118 Q178,140 168,166 Q162,190 150,200 L152,250 L142,250 L138,210 L80,212 L72,250 L62,250 L60,212 Q48,214 45,215 Z", fill: "#8a5a2b", stroke: "#3b2410", "stroke-width": 2 }, svg);
    el("path", { d: "M152,128 Q150,116 160,110 L170,118", fill: "#5a3a1a", stroke: "#3b2410", "stroke-width": 1.4 }, svg);
    el("circle", { cx: 163, cy: 124, r: 1.8, fill: "#111" }, svg);
    el("path", { d: "M45,215 Q30,222 34,240", fill: "none", stroke: "#3b2410", "stroke-width": 4, "stroke-linecap": "round" }, svg);
    // Jinete
    el("path", { d: "M88,180 L92,128 Q108,118 122,128 L118,182 Z", fill: ROBE[suit], stroke: "#2b1a0c", "stroke-width": 1.8 }, svg);
    face(svg, 107, 108);
    el("path", { d: "M93,100 Q107,84 121,100 Z", fill: "#2b1a0c" }, svg);
    symbol(svg, defs, suit, 70, 140, 1, suit === "O" || suit === "C" ? 0 : -25);
  }

  function sota(svg, defs, suit) {
    el("rect", { x: 86, y: 205, width: 10, height: 45, fill: "#f4e6c6", stroke: "#2b1a0c", "stroke-width": 1.4 }, svg);
    el("rect", { x: 104, y: 205, width: 10, height: 45, fill: "#f4e6c6", stroke: "#2b1a0c", "stroke-width": 1.4 }, svg);
    el("path", { d: "M74,210 L80,140 Q100,124 120,140 L126,210 Z", fill: ROBE[suit], stroke: "#2b1a0c", "stroke-width": 2 }, svg);
    el("path", { d: "M80,170 H120", stroke: "#e8b923", "stroke-width": 4 }, svg);
    face(svg, 100, 112);
    el("path", { d: "M84,104 Q100,86 116,104 Z", fill: "#2d6a2f", stroke: "#123b13", "stroke-width": 1.2 }, svg);
    el("path", { d: "M114,96 Q130,80 126,70", stroke: "#b3261e", "stroke-width": 3, fill: "none", "stroke-linecap": "round" }, svg);
    symbol(svg, defs, suit, 138, 165, 1.05, suit === "O" || suit === "C" ? 0 : 15);
  }

  const FIGURE = { 10: [sota, "SOTA"], 11: [caballo, "CABALLO"], 12: [rey, "REY"] };

  function index(svg, defs, suit, num, x, y, rotate) {
    const g = el("g", { transform: `translate(${x},${y}) rotate(${rotate})` }, svg);
    const t = el("text", { x: 0, y: 0, "text-anchor": "middle", "font-family": "Georgia, serif", "font-weight": "800", "font-size": num >= 10 ? 34 : 40, fill: INK[suit] }, g);
    t.textContent = String(num);
    symbol(g, defs, suit, 0, 22, 0.55, 0);
  }

  function badge(svg, text) {
    const g = el("g", { transform: "translate(150,14)" }, svg);
    el("rect", { x: 0, y: 0, width: 40, height: 20, rx: 6, fill: "#f6c453", stroke: "#8a5f00", "stroke-width": 1 }, g);
    const t = el("text", { x: 20, y: 15, "text-anchor": "middle", "font-family": "system-ui, sans-serif", "font-weight": "800", "font-size": 12, fill: "#3b2a1a" }, g);
    t.textContent = text;
  }

  function frame(mini) {
    const svg = el("svg", { viewBox: "0 0 200 300", class: "naipe" + (mini ? " mini" : ""), role: "img" });
    const defs = el("defs", {}, svg);
    el("rect", { x: 2, y: 2, width: 196, height: 296, rx: 16, fill: "#fffaf0", stroke: "#cbb994", "stroke-width": 3 }, svg);
    el("rect", { x: 10, y: 10, width: 180, height: 280, rx: 10, fill: "none", stroke: "#e9dcc0", "stroke-width": 2 }, svg);
    return [svg, defs];
  }

  function svg(code, opts = {}) {
    const suit = code.slice(-1), num = Number(code.slice(0, -1));
    const [card, defs] = frame(opts.mini);
    if (opts.mini) {
      const t = el("text", { x: 100, y: 125, "text-anchor": "middle", "font-family": "Georgia, serif", "font-weight": "800", "font-size": 110, fill: INK[suit] }, card);
      t.textContent = String(num);
      symbol(card, defs, suit, 100, 215, 2.3, 0);
    } else {
      index(card, defs, suit, num, 28, 48, 0);
      index(card, defs, suit, num, 172, 252, 180);
      if (FIGURE[num]) {
        const [draw, name] = FIGURE[num];
        draw(card, defs, suit);
        const t = el("text", { x: 100, y: 282, "text-anchor": "middle", "font-family": "system-ui, sans-serif", "font-weight": "800", "font-size": 15, fill: INK[suit], "letter-spacing": 1 }, card);
        t.textContent = name;
      } else {
        pips(card, defs, suit, num);
      }
    }
    const eff = num === 3 ? 12 : num === 2 ? 1 : num;
    if (num === 3) badge(card, "REY");
    else if (num === 2) badge(card, "AS");
    else if (eff === 12 && opts.mini) badge(card, "REY");
    return card;
  }

  function back(opts = {}) {
    const card = el("svg", { viewBox: "0 0 200 300", class: "naipe back" + (opts.mini ? " mini" : ""), role: "img" });
    el("rect", { x: 2, y: 2, width: 196, height: 296, rx: 16, fill: "#9d1f26", stroke: "#fff4dd", "stroke-width": 6 }, card);
    el("rect", { x: 16, y: 16, width: 168, height: 268, rx: 10, fill: "none", stroke: "#e8b923", "stroke-width": 3 }, card);
    for (let i = 0; i < 6; i++) el("path", { d: `M16,${40 + i * 44} L184,${18 + i * 44}`, stroke: "#b8323a", "stroke-width": 10 }, card);
    el("ellipse", { cx: 100, cy: 150, rx: 62, ry: 34, fill: "#9d1f26", stroke: "#e8b923", "stroke-width": 4 }, card);
    const t = el("text", { x: 100, y: 160, "text-anchor": "middle", "font-family": "Georgia, serif", "font-weight": "800", "font-size": 28, fill: "#e8b923" }, card);
    t.textContent = "MUS.ST";
    return card;
  }

  window.MusCards = { svg, back };
})();
