/* NFL game sheet. window.NFLSheet = { open(id, opts), close(), refresh() }.
   Data: GET /api/nfl/game?id=. Every ESPN string goes through esc(); the pure builders sit between the
   pure markers so scripts/nfl/checks/sheet_ui.py can run them under node without a DOM. */
(function () {
  "use strict";
  const ENDPOINT = "/api/nfl/game?id=";
  const POLL_MS = 20000;
  const BIG_YARDS = 20;
  const TABS = [["drives", "Drives"], ["plays", "Plays"], ["wp", "Win prob"], ["scoring", "Scoring"], ["box", "Box"], ["leaders", "Leaders"]];
  const FILTERS = [["all", "All"], ["scoring", "Scoring"], ["big", "Big plays"], ["turnover", "Turnovers"], ["penalty", "Penalties"]];

  // pure:start
  const LIVE_RE = /^(in|in_progress|halftime|end_period)$/i;
  const FINAL_RE = /^(post|final)$/i;
  const NON_SCRIMMAGE = /kickoff|punt|field goal|extra point|two-point|timeout|end (period|of)|coin toss/i;

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>\x22\x27]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\x22": "&quot;", "\x27": "&#39;" })[c]);
  }
  function int(v) { const n = Math.round(Number(v)); return Number.isFinite(n) ? n : 0; }
  function numOrNull(v) { if (v == null || v === "") return null; const n = Number(v); return Number.isFinite(n) ? n : null; }
  function f1(v) { return (Math.round(Number(v) * 10) / 10).toFixed(1); }
  function flag(v) { return Boolean(v) && v !== "false" && v !== "0"; }

  function periodLabel(n) {
    n = int(n);
    if (n <= 0) return "";
    if (n <= 4) return "Q" + n;
    return n === 5 ? "OT" : (n - 4) + "OT";
  }
  function lineLabels(n) {
    return Array.from({ length: n }, (_, i) => i < 4 ? "Q" + (i + 1) : (n > 5 ? (i - 3) + "OT" : "OT"));
  }
  function ordinal(n) { return ({ 1: "1st", 2: "2nd", 3: "3rd", 4: "4th" })[n] || ""; }
  function downText(p) {
    const down = ordinal(int(p && p.down));
    if (!down) return "";
    const dist = numOrNull(p.distance);
    return dist == null ? down : down + " & " + int(dist);
  }

  function offGame(d) { return /^STATUS_(POSTPONED|CANCELED|CANCELLED)$/.test(String((d && d.status) || "")); }
  function phase(d) {
    const s = String((d && d.state) || "");
    if (offGame(d)) return "hold";
    if (LIVE_RE.test(s)) return "live";
    if (FINAL_RE.test(s)) return "final";
    return ((d && d.drives) || []).length || ((d && d.scoring) || []).length ? "hold" : "pre";
  }
  function defaultTab(d) { return phase(d) === "final" ? "scoring" : "drives"; }

  function totals(d) {
    const ls = (d && d.linescores) || {};
    const sum = a => (a || []).reduce((t, v) => t + int(v), 0);
    if ((ls.away || []).length || (ls.home || []).length) return { away: sum(ls.away), home: sum(ls.home) };
    const sc = (d && d.scoring) || [];
    const last = sc[sc.length - 1];
    return last ? { away: int(last.away), home: int(last.home) } : { away: 0, home: 0 };
  }
  function statusText(d) {
    const ph = phase(d), st = String((d && d.state) || "");
    const label = d.periodLabel || periodLabel(d.period);
    if (ph === "final") {
      const ot = int(d.ot_periods);
      const t = totals(d);
      return "Final" + (ot > 1 ? "/" + ot + "OT" : ot === 1 ? "/OT" : "") + (d.result === "tie" || (t.away === t.home) ? " · Tie" : "");
    }
    if (ph === "pre") return "Game detail opens at kickoff";
    if (offGame(d)) return /POSTPONED/.test(d.status) ? "Postponed" : "Canceled";
    if (d.status === "STATUS_HALFTIME" || /^halftime$/i.test(st)) return "Halftime";
    if (d.status === "STATUS_END_PERIOD" || /^end_period$/i.test(st)) return "End of " + label;
    if (ph === "live") return (label + " " + (d.clock || "")).trim();
    return st.replace(/_/g, " ").toLowerCase().replace(/^./, c => c.toUpperCase());
  }

  function hexLum(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ""));
    if (!m) return null;
    const n = parseInt(m[1], 16), ch = [n >> 16, (n >> 8) & 255, n & 255].map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return { hex: "#" + m[1].toLowerCase(), lum: 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2] };
  }
  function chipStyle(hex) {
    const c = hexLum(hex);
    if (!c) return "background:#22314d;color:#f4f7fb";
    return "background:" + c.hex + ";color:" + (c.lum > 0.4 ? "#0b1220" : "#ffffff");
  }
  // Helmet glyph: one plain shape for every team, tinted with the team's two colours. It carries no team mark.
  // The facemask falls back to light grey when the second colour would vanish on the dark sheet or match the shell.
  function helmetColors(t) {
    const a = hexLum(t && t.color), b = hexLum(t && t.alt);
    const shell = a ? a.hex : "#22314d";
    return { shell, mask: b && b.lum >= 0.12 && b.hex !== shell ? b.hex : "#d5dbe6" };
  }
  function helmetHtml(t, flip, box) {
    const c = helmetColors(t);
    const tfHtml = flip ? ` transform="translate(24 0) scale(-1 1)"` : "";
    const boxHtml = box ? ` x="${f1(box.x)}" y="${f1(box.y)}" width="${f1(box.w)}" height="${f1(box.w * 20 / 24)}"` : ` class="ns-hel" aria-hidden="true"`;
    return `<svg${boxHtml} viewBox="0 0 24 20"><path class="ns-hsh" fill="${esc(c.shell)}"${tfHtml} d="M2.6 11.6C2.6 5.9 7.1 1.8 12.8 1.8c5 0 8.6 3.3 9.2 7.9l-6.3.5c-1.5.1-2.4 1.3-2.1 2.8l.8 3.9c-2.3 1.4-5.3 1.7-7.9.7-2.4-.9-3.9-3-3.9-6z"/>
      <path class="ns-hst" stroke="${esc(c.mask)}"${tfHtml} d="M4.6 7.6C6.4 4.6 9.4 3.1 12.8 3.1c2.9 0 5.3 1.1 6.9 3"/>
      <circle class="ns-hear" cx="9.4" cy="11.8" r="1.3"${tfHtml}/>
      <path class="ns-hmk" stroke="${esc(c.mask)}"${tfHtml} d="M22 9.7l1 4.3c.3 1.4-.4 2.5-1.8 2.6l-6.8.3M13.7 13.4l9.1-.2"/></svg>`;
  }
  function teamOf(d, abbr) {
    const t = (d && d.teams) || {};
    for (const s of ["away", "home"]) if (t[s] && String(t[s].abbr) === String(abbr)) return t[s];
    return null;
  }
  function chipHtml(d, abbr) {
    const t = teamOf(d, abbr);
    return `<span class="ns-tm">${helmetHtml(t, false, null)}<span class="ns-chip" style="${esc(chipStyle(t && t.color))}">${esc(abbr)}</span></span>`;
  }

  // Win probability. Points carry the home side's chance, 0-1 (percent tolerated).
  function wpValues(points) {
    const raw = (points || []).map(p => numOrNull(p && p.p)).filter(v => v != null);
    const pct = raw.some(v => v > 1) ? 1 : 100;
    return raw.map(v => Math.max(0, Math.min(100, v * pct)));
  }
  function wpPath(vals, W, H) {
    if (vals.length < 2) return "";
    return vals.map((v, i) => (i ? "L" : "M") + f1(i * W / (vals.length - 1)) + "," + f1(H - v * H / 100)).join("");
  }
  function wpTicks(wp, n) {
    const out = [];
    for (const q of (wp && wp.quarters) || []) {
      const idx = int(q[1]);
      const lab = typeof q[0] === "number" ? periodLabel(q[0]) : String(q[0] || "");
      if (idx >= 0 && idx < n && lab) out.push({ label: lab.slice(0, 4), pct: n > 1 ? 100 * idx / (n - 1) : 0 });
    }
    const at = numOrNull(wp && wp.ot_at);
    if (at != null && at >= 0 && at < n && !out.some(t => /OT/.test(t.label))) out.push({ label: "OT", pct: n > 1 ? 100 * at / (n - 1) : 0 });
    return out;
  }
  function wpLatest(d, vals) {
    if (phase(d) !== "live" || !vals.length) return "";
    const h = Math.round(vals[vals.length - 1]), a = d.teams.away.abbr, hm = d.teams.home.abbr;
    return h === 50 ? "even" : h > 50 ? hm + " " + h + "%" : a + " " + (100 - h) + "%";
  }
  function wpHtml(d) {
    const vals = wpValues(d.winprob && d.winprob.points);
    if (vals.length < 2) return `<div class="ns-empty">No win probability for this game yet.</div>`;
    const W = 300, H = 90, ticks = wpTicks(d.winprob, vals.length);
    const latest = wpLatest(d, vals);
    const ticksHtml = ticks.map(t => `<line x1="${f1(t.pct * W / 100)}" x2="${f1(t.pct * W / 100)}" y1="0" y2="${int(H)}" class="ns-wq"/>`).join("");
    const labelsHtml = ticks.map(t => `<span class="ns-wt" style="left:${f1(t.pct)}%">${esc(t.label)}</span>`).join("");
    const lab = "ESPN win probability" + (latest ? " · latest " + latest : "");
    return `<div class="ns-wp"><div class="ns-wplab">${esc(lab)}</div>
      <div class="ns-wbox"><svg viewBox="0 0 ${int(W)} ${int(H)}" preserveAspectRatio="none" role="img" aria-label="${esc(lab)}">
        <line x1="0" x2="${int(W)}" y1="${int(H / 2)}" y2="${int(H / 2)}" class="ns-wmid"/>${ticksHtml}
        <path d="${esc(wpPath(vals, W, H))}" class="ns-wline"/></svg>${labelsHtml}</div>
      <div class="ns-wpaxis"><span>${esc(d.teams.home.abbr)} ↑</span><span>${esc(d.teams.away.abbr)} ↓</span></div>
      <p class="ns-note">ESPN's model estimate at each play. It is not a result.</p></div>`;
  }

  // Field tracker. The field is drawn away end zone left, home end zone right; start_yl and cur_yl are distances from the home goal line; yl below is yards to the goal being attacked.
  function sideOf(d, t) {
    const tm = (d && d.teams) || {};
    const dr = ((d && d.drives) || []).find(r => String(r.id) === String(t.drive_id));
    for (const key of [t.team, dr && dr.team]) {
      if (key == null || key === "") continue;
      for (const s of ["away", "home"]) {
        const x = tm[s] || {};
        if (String(key) === String(x.abbr) || String(key) === String(x.id)) return s;
      }
    }
    return null;
  }
  function trackerGeom(t, side) {
    if (!t || !side) return null;
    const s0 = numOrNull(t.start_yl), c0 = numOrNull(t.cur_yl);
    if (s0 == null || c0 == null) return null;
    const s = side === "away" ? s0 : 100 - s0, c = side === "away" ? c0 : 100 - c0;
    const cl = v => Math.max(0, Math.min(100, v));
    const xOf = yl => side === "away" ? 10 + (100 - cl(yl)) : 10 + cl(yl);
    return { side, dir: side === "away" ? 1 : -1, x0: xOf(s), x1: xOf(c), rzX: side === "away" ? 90 : 10, red: cl(c) <= 20 };
  }
  function trackerHtml(d) {
    const t = d.tracker;
    if (!t || phase(d) !== "live") return "";
    const side = sideOf(d, t), g = trackerGeom(t, side);
    if (!g) return "";
    const tm = d.teams;
    const dr = (d.drives || []).find(r => String(r.id) === String(t.drive_id)) || {};
    const lastPlay = (dr.plays_list || []).filter(p => p.kind !== "admin").slice(-1)[0] || {};
    const from = (dr.start && dr.start.yard_text) || "", at = lastPlay.yard_text || (dr.end && dr.end.yard_text) || "";
    const tip = g.x1 + g.dir * 7;
    const away = chipStyle(tm.away.color).split(";")[0].replace("background:", ""), home = chipStyle(tm.home.color).split(";")[0].replace("background:", "");
    const off = side === "away" ? tm.away : tm.home;
    const offHtml = helmetHtml(off, g.dir < 0, { x: g.x1 - g.dir * 6.4 - 5.5, y: 13.4, w: 11 });
    const ezHtml = helmetHtml(tm.away, false, { x: 1.2, y: 14.8, w: 7.6 }) + helmetHtml(tm.home, true, { x: 111.2, y: 14.8, w: 7.6 });
    const capHtml = [helmetHtml(off, false, null) + esc(off.abbr) + " ball", from ? "from " + esc(from) : "", at ? "now " + esc(at) : ""].filter(Boolean).join(" · ");
    const metaHtml = [t.plays != null ? int(t.plays) + " plays" : "", t.yards != null ? int(t.yards) + " yds" : "", t.elapsed ? esc(t.elapsed) : ""].filter(Boolean).join(" · ");
    const linesHtml = [20, 30, 40, 50, 60, 70, 80, 90, 100].map(x => `<line x1="${int(x)}" x2="${int(x)}" y1="0" y2="36" class="ns-yl"/>`).join("");
    const rzHtml = `<rect x="${int(g.rzX)}" y="0" width="20" height="36" class="ns-rz${g.red ? " on" : ""}"/>`;
    return `<div class="ns-field"><svg viewBox="0 0 120 36" role="img" aria-label="${esc((side === "away" ? tm.away.abbr : tm.home.abbr) + " drive, moving " + (g.dir > 0 ? "right" : "left") + (g.red ? ", in the red zone" : ""))}">
      <rect width="120" height="36" class="ns-turf"/>
      <rect width="10" height="36" fill="${esc(away)}" opacity=".7"/><rect x="110" width="10" height="36" fill="${esc(home)}" opacity=".7"/>
      ${linesHtml}${rzHtml}
      <line x1="${f1(g.x1)}" x2="${f1(g.x1)}" y1="0" y2="36" class="ns-los"/>
      <line x1="${f1(g.x0)}" x2="${f1(g.x1)}" y1="18" y2="18" class="ns-path"/>
      <rect x="${f1(g.x0 - 1.5)}" y="12" width="3" height="12" class="ns-start"/>
      <polygon points="${f1(tip)},18 ${f1(g.x1 + g.dir * 1)},12.5 ${f1(g.x1 + g.dir * 1)},23.5" class="ns-arrow"/>
      ${ezHtml}${offHtml}</svg>
      <div class="ns-fcap"><span class="ns-fwho">${capHtml}</span>${g.red ? `<b class="ns-rzchip">Red zone</b>` : ""}</div>${metaHtml ? `<div class="ns-fmeta">${metaHtml}</div>` : ""}</div>`;
  }

  // Plays
  function allPlays(d) {
    const out = [];
    for (const dr of d.drives || []) for (const p of dr.plays_list || []) out.push({ p, team: dr.team, did: dr.id });
    return out.map((x, i) => [x, i]).sort((a, b) => (int(a[0].p.seq) - int(b[0].p.seq)) || (a[1] - b[1])).map(x => x[0]);
  }
  function isBigPlay(p) {
    if (!p || p.kind === "admin" || flag(p.penalty) || NON_SCRIMMAGE.test(p.type || "")) return false;
    return int(p.yards) >= BIG_YARDS;
  }
  function playMatches(f, p) {
    if (p.kind === "admin") return false;
    if (f === "scoring") return flag(p.scoring);
    if (f === "big") return isBigPlay(p);
    if (f === "turnover") return flag(p.turnover);
    if (f === "penalty") return flag(p.penalty);
    return true;
  }
  function playHtml(p, d, team) {
    const when = (p.periodLabel || periodLabel(p.period)) + (p.clock ? " " + p.clock : "");
    const dn = downText(p), where = p.yard_text ? (dn ? " at " : "") + p.yard_text : "";
    const tagsHtml = [flag(p.scoring) ? `<b class="ns-tag sc">${esc(p.score_value ? "+" + int(p.score_value) : "Score")}</b>` : "",
      flag(p.turnover) ? `<b class="ns-tag to">Turnover</b>` : "", flag(p.penalty) ? `<b class="ns-tag pn">Penalty</b>` : "",
      isBigPlay(p) ? `<b class="ns-tag bp">${int(p.yards)} yds</b>` : ""].join("");
    const scoreHtml = flag(p.scoring) ? `<div class="ns-psc">${esc(d.teams.away.abbr)} ${int(p.away)} – ${esc(d.teams.home.abbr)} ${int(p.home)}</div>` : "";
    const leadHtml = team ? chipHtml(d, team) : "";
    const pdnHtml = dn || where ? `<span class="ns-pdn">${esc(dn + where)}</span>` : "";
    return `<div class="ns-play${p.kind === "admin" ? " admin" : ""}"><div class="ns-pq">${esc(when)}${leadHtml}</div>
      <div class="ns-ptxt">${pdnHtml}${esc(p.text)}${tagsHtml}${scoreHtml}</div></div>`;
  }
  function playsTabHtml(d, ui) {
    const f = ui.filter || "all";
    const barHtml = FILTERS.map(([id, label]) => `<button class="ns-fbtn${f === id ? " active" : ""}" data-filter="${esc(id)}" aria-pressed="${f === id ? "true" : "false"}">${esc(label)}</button>`).join("");
    let list = allPlays(d).filter(x => playMatches(f, x.p));
    if (phase(d) === "live") list = list.reverse();
    const rowsHtml = list.map(x => playHtml(x.p, d, x.team)).join("");
    return `<div class="ns-filters" role="group" aria-label="Play filters">${barHtml}</div>${rowsHtml || `<div class="ns-empty">No plays match.</div>`}`;
  }

  // Drives
  function driveOpen(d, dr, ui) {
    const ov = ui.drv && ui.drv[dr.id];
    return ov == null ? Boolean(dr.live) && phase(d) === "live" : ov;
  }
  function resultClass(dr) {
    if (flag(dr.scoring)) return "score";
    return /interception|fumble|downs|turnover|safety/i.test(dr.result || "") ? "turn" : "";
  }
  function driveHtml(d, dr, ui) {
    const live = Boolean(dr.live) && phase(d) === "live";
    const plays = dr.plays_list || [];
    let main = plays.filter(p => p.kind !== "admin"), admin = plays.filter(p => p.kind === "admin");
    if (live) { main = main.slice().reverse(); admin = admin.slice().reverse(); }
    const mainHtml = main.map(p => playHtml(p, d, "")).join("");
    const adminRowsHtml = admin.map(p => playHtml(p, d, "")).join("");
    const adminHtml = admin.length ? `<details class="ns-admin"><summary>${int(admin.length)} admin ${admin.length === 1 ? "play" : "plays"}</summary>${adminRowsHtml}</details>` : "";
    const meta = [dr.plays != null ? int(dr.plays) + " plays" : "", dr.yards != null ? int(dr.yards) + " yds" : "", dr.time || ""].filter(Boolean).join(" · ");
    const from = dr.start && dr.start.yard_text ? "from " + dr.start.yard_text : "";
    const startQ = dr.start && (dr.start.periodLabel || periodLabel(dr.start.period));
    return `<details class="ns-drive ${esc(resultClass(dr))}${live ? " now" : ""}" data-did="${esc(dr.id)}"${driveOpen(d, dr, ui) ? " open" : ""}>
      <summary>${chipHtml(d, dr.team)}<span class="ns-res ${esc(resultClass(dr))}">${esc(live ? "On the field" : dr.result || "Drive")}</span>
        <span class="ns-dmeta">${esc([startQ, from, meta].filter(Boolean).join(" · "))}</span></summary>
      <div class="ns-dbody">${dr.desc ? `<p class="ns-ddesc">${esc(dr.desc)}</p>` : ""}${mainHtml || `<div class="ns-empty">No plays yet.</div>`}${adminHtml}</div></details>`;
  }
  function drivesTabHtml(d, ui) {
    let list = d.drives || [];
    if (phase(d) === "live") list = list.slice().reverse();
    const rowsHtml = list.map(dr => driveHtml(d, dr, ui)).join("");
    return trackerHtml(d) + (rowsHtml || `<div class="ns-empty">No drives yet.</div>`);
  }

  // Scoring, box, leaders
  function scoringTabHtml(d) {
    let list = d.scoring || [];
    if (phase(d) === "live") list = list.slice().reverse();
    const rowsHtml = list.map(s => `<div class="ns-play"><div class="ns-pq">${esc((s.periodLabel || periodLabel(s.period)) + " " + (s.clock || ""))}${chipHtml(d, s.team)}</div>
      <div class="ns-ptxt"><b class="ns-tag sc">${esc(s.kind)}</b> ${esc(s.text)}
      <div class="ns-psc">${esc(d.teams.away.abbr)} ${int(s.away)} – ${esc(d.teams.home.abbr)} ${int(s.home)}</div></div></div>`).join("");
    return rowsHtml || `<div class="ns-empty">No scoring yet.</div>`;
  }
  function boxTabHtml(d) {
    const box = d.box || [];
    if (!box.length) return `<div class="ns-empty">Box score not available yet.</div>`;
    const rowsHtml = box.map(r => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td>${esc(r[2])}</td></tr>`).join("");
    return `<table class="ns-box"><thead><tr><th></th><th>${esc(d.teams.away.abbr)}</th><th>${esc(d.teams.home.abbr)}</th></tr></thead><tbody>${rowsHtml}</tbody></table>`;
  }
  function leadersTabHtml(d) {
    const L = d.leaders || {};
    const colHtml = (t, list) => {
      const itemsHtml = (list || []).map(l => `<div class="ns-lead"><span>${esc(l.cat || l.label || l.category)}</span><b>${esc(l.name || l.athlete)}</b><div class="ns-lline">${esc(l.line || l.display || l.value)}</div></div>`).join("");
      return `<div class="ns-lcol"><h3>${esc(t.name || t.abbr)}</h3>${itemsHtml || `<div class="ns-empty">None yet.</div>`}</div>`;
    };
    return `<div class="ns-leads">${colHtml(d.teams.away, L.away)}${colHtml(d.teams.home, L.home)}</div>`;
  }

  // Header
  function headHtml(d) {
    const tm = d.teams, tot = totals(d), ph = phase(d);
    const ls = d.linescores || {};
    const n = Math.max((ls.away || []).length, (ls.home || []).length, ph === "pre" ? 0 : 4);
    const labs = lineLabels(n);
    const poss = d.tracker && ph === "live" ? sideOf(d, d.tracker) : null;
    const rowHtml = (side, t) => `<div class="ns-trow"><span class="ns-tn">${chipHtml(d, t.abbr)}<span>${esc(t.name || t.abbr)}</span>${poss === side ? `<i class="ns-ball" role="img" aria-label="has the ball"></i>` : ""}</span><b class="ns-score">${ph === "pre" ? "" : int(tot[side])}</b></div>`;
    const cell = (a, i) => `<td>${esc((a || [])[i] == null ? "" : int(a[i]))}</td>`;
    const labsHtml = labs.map(l => `<th>${esc(l)}</th>`).join("");
    const lrowsHtml = [["away", tm.away], ["home", tm.home]].map(([s, t]) => {
      const cellsHtml = labs.map((_, i) => cell(ls[s], i)).join("");
      return `<tr><td>${esc(t.abbr)}</td>${cellsHtml}<td><b>${int(tot[s])}</b></td></tr>`;
    }).join("");
    const lineHtml = n ? `<div class="ns-lwrap"><table class="ns-lines"><thead><tr><th></th>${labsHtml}<th>T</th></tr></thead><tbody>${lrowsHtml}</tbody></table></div>` : "";
    const cls = ph === "final" ? "final" : ph === "live" ? "on" : "";
    const pill = ph === "final" ? "FINAL" : ph === "live" ? "LIVE" : ph === "hold" ? "PAUSED" : "PRE";
    return `<div class="ns-head"><div class="ns-teams">${rowHtml("away", tm.away)}${rowHtml("home", tm.home)}</div>
      <div class="ns-stat"><span class="ns-pill ${esc(cls)}">${esc(pill)}</span><span>${esc(statusText(d))}</span></div>${lineHtml}</div>`;
  }

  function tabBodyHtml(d, ui, tab) {
    if (tab === "plays") return playsTabHtml(d, ui);
    if (tab === "wp") return wpHtml(d);
    if (tab === "scoring") return scoringTabHtml(d);
    if (tab === "box") return boxTabHtml(d);
    if (tab === "leaders") return leadersTabHtml(d);
    return drivesTabHtml(d, ui);
  }
  function validTab(tab) { return TABS.some(t => t[0] === tab); }

  // ui: { id, d, error, loading, tab, filter, drv }
  function panelHtml(ui) {
    const d = ui.d;
    const closeHtml = `<button class="ns-x" data-close aria-label="Close game detail">×</button>`;
    if (!d) {
      const msgHtml = ui.error ? `Couldn't load game detail. <button class="ns-btn" data-retry>Retry</button>` : "Loading…";
      return `${closeHtml}<h2 id="ns-title" class="ns-sr">Game detail</h2><div class="ns-body"><div class="ns-empty" aria-live="polite">${msgHtml}</div></div>`;
    }
    const title = d.teams.away.abbr + " at " + d.teams.home.abbr + " game detail";
    const ph = phase(d), tab = validTab(ui.tab) ? ui.tab : defaultTab(d);
    let navHtml = "", bodyHtml;
    if (ph === "pre") {
      bodyHtml = `<div class="ns-empty">Play-by-play opens at kickoff.</div>`;
    } else {
      const tabsHtml = TABS.map(([id, label]) => `<button class="ns-tab${tab === id ? " active" : ""}" role="tab" id="ns-tab-${esc(id)}" data-tab="${esc(id)}" aria-selected="${tab === id ? "true" : "false"}" aria-controls="ns-panel" tabindex="${tab === id ? "0" : "-1"}">${esc(label)}</button>`).join("");
      navHtml = `<div class="ns-tabs" role="tablist" aria-label="Game detail">${tabsHtml}</div>`;
      bodyHtml = tabBodyHtml(d, ui, tab);
    }
    const noteHtml = [d.stale ? "Showing saved data." : "", ui.error ? "Update failed, retrying." : ""].filter(Boolean).map(s => `<div class="ns-warn" role="status">${esc(s)}</div>`).join("");
    return `${closeHtml}<h2 id="ns-title" class="ns-sr">${esc(title)}</h2>${headHtml(d)}${navHtml}${noteHtml}
      <div class="ns-body" id="ns-panel" role="${ph === "pre" ? "region" : "tabpanel"}"${ph === "pre" ? "" : ` aria-labelledby="ns-tab-${esc(tab)}"`}>${bodyHtml}</div>
      <div class="ns-foot">Scores and play data via ESPN. <span id="ns-upd"></span></div>`;
  }
  // pure:end

  let S = null;          // { id, d, error, tab, filter, drv, seq, sig, opener, fromBoard }
  let timer = null, inflight = false, overlay = null, inerted = [];

  function chicago(iso) {
    const t = Date.parse(iso);
    if (!Number.isFinite(t)) return "";
    return new Date(t).toLocaleTimeString("en-US", { timeZone: "America/Chicago", hour: "numeric", minute: "2-digit", second: "2-digit" }) + " CT";
  }
  function ensureOverlay() {
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.className = "ns-sheet";
    overlay.hidden = true;
    overlay.innerHTML = `<div class="ns-panel" role="dialog" aria-modal="true" aria-labelledby="ns-title" tabindex="-1"></div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("click", onClick);
    overlay.addEventListener("keydown", onPanelKey);
    overlay.addEventListener("toggle", onToggle, true);
    return overlay;
  }
  function panel() { return overlay.firstElementChild; }
  function onClick(e) {
    if (e.target === overlay || e.target.closest("[data-close]")) { dismiss(); return; }
    if (!S) return;
    const tab = e.target.closest("[data-tab]");
    if (tab) { S.tab = tab.dataset.tab; render(); const b = overlay.querySelector(".ns-body"); if (b) b.scrollTop = 0; return; }
    const f = e.target.closest("[data-filter]");
    if (f) { S.filter = f.dataset.filter; render(); return; }
    if (e.target.closest("[data-retry]")) load(true);
  }
  function onToggle(e) {
    const el = e.target;
    if (!S || !S.d || !el.dataset || el.dataset.did == null) return;
    const dr = (S.d.drives || []).find(r => String(r.id) === el.dataset.did);
    if (!dr) return;
    const dflt = Boolean(dr.live) && phase(S.d) === "live";
    if (el.open !== dflt || (S.drv && S.drv[dr.id] != null)) { S.drv = S.drv || {}; S.drv[dr.id] = el.open; }
  }
  function focusables() {
    return Array.from(panel().querySelectorAll("button, summary, [href], [tabindex]:not([tabindex='-1'])")).filter(el => !el.disabled && el.offsetParent !== null);
  }
  function onPanelKey(e) {
    if (e.key === "Tab") {
      const list = focusables();
      if (!list.length) { e.preventDefault(); panel().focus(); return; }
      const first = list[0], last = list[list.length - 1], a = document.activeElement;
      if (e.shiftKey && (a === first || a === panel())) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && a === last) { e.preventDefault(); first.focus(); }
      return;
    }
    const t = e.target.closest && e.target.closest("[data-tab]");
    if (t && (e.key === "ArrowRight" || e.key === "ArrowLeft" || e.key === "Home" || e.key === "End")) {
      const tabs = Array.from(overlay.querySelectorAll("[data-tab]"));
      let i = tabs.indexOf(t);
      i = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      e.preventDefault();
      S.tab = tabs[i].dataset.tab;
      render();
      const nt = overlay.querySelector(`[data-tab="${CSS.escape(S.tab)}"]`); if (nt) nt.focus();
    }
  }
  function onDocKey(e) { if (e.key === "Escape" && S) { e.preventDefault(); dismiss(); } }
  function onHash() { if (S && !/^#game\//.test(location.hash)) close(); }
  function onVisibility() {
    if (!S) return;
    if (document.hidden) { clearTimeout(timer); timer = null; }
    else if (S.d && phase(S.d) === "live") load(true);
    else schedule();
  }

  function render() {
    if (!S || !overlay) return;
    const p = panel(), a = document.activeElement;
    const keep = a && p.contains(a) ? (a.dataset.tab ? `[data-tab="${CSS.escape(a.dataset.tab)}"]` : a.dataset.filter ? `[data-filter="${CSS.escape(a.dataset.filter)}"]` : a.hasAttribute("data-close") ? "[data-close]" : "") : "";
    const body = p.querySelector(".ns-body"), top = body ? body.scrollTop : 0;
    const fullHtml = panelHtml(S);
    p.innerHTML = fullHtml;
    const fresh = p.querySelector(".ns-body"); if (fresh) fresh.scrollTop = top;
    if (keep) { const el = p.querySelector(keep); if (el) el.focus(); }
    stamp();
  }
  function stamp() {
    const el = overlay && overlay.querySelector("#ns-upd");
    if (el && S && S.fetchedAt) el.textContent = "Updated " + chicago(S.fetchedAt) + ".";
  }
  function schedule() {
    clearTimeout(timer);
    timer = null;
    if (!S || document.hidden || !S.d || phase(S.d) !== "live") return;
    timer = setTimeout(() => load(false), POLL_MS);
  }
  async function load(force) {
    if (!S || inflight && !force) return;
    const mine = S, token = ++mine.seq;
    inflight = true;
    try {
      const res = await fetch(ENDPOINT + encodeURIComponent(mine.id), { cache: "no-store" });
      const data = await res.json();
      if (!data || !data.ok) throw new Error((data && data.error) || "game failed");
      if (S !== mine || token !== mine.seq) return;
      const { fetched_at, ...rest } = data;
      const sig = JSON.stringify(rest);
      const changed = sig !== mine.sig || mine.error;
      mine.d = data; mine.error = null; mine.sig = sig; mine.fetchedAt = fetched_at;
      if (changed) render(); else stamp();
    } catch (err) {
      if (S !== mine || token !== mine.seq) return;
      mine.error = String((err && err.message) || err);
      render();
    } finally {
      if (S === mine && token === mine.seq) inflight = false;
      if (S === mine) schedule();
    }
  }

  function open(id, opts) {
    id = String(id == null ? "" : id);
    if (!/^\d{6,12}$/.test(id)) return;
    if (S && S.id === id) { refresh(); return; }
    if (S) teardown();
    ensureOverlay();
    S = { id, d: null, error: null, tab: null, filter: "all", drv: {}, seq: 0, sig: "", fetchedAt: "", opener: document.activeElement, fromBoard: Boolean(opts && opts.fromBoard) };
    document.body.classList.add("ns-open");
    inerted = Array.from(document.body.children).filter(el => el !== overlay && !el.inert);
    inerted.forEach(el => { el.inert = true; });
    overlay.hidden = false;
    document.addEventListener("keydown", onDocKey);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("hashchange", onHash);
    render();
    panel().focus();
    inflight = false;
    load(true);
  }
  function teardown() {
    clearTimeout(timer);
    timer = null;
    document.removeEventListener("keydown", onDocKey);
    document.removeEventListener("visibilitychange", onVisibility);
    window.removeEventListener("hashchange", onHash);
    inerted.forEach(el => { el.inert = false; });
    inerted = [];
    document.body.classList.remove("ns-open");
    if (overlay) overlay.hidden = true;
    const back = S && S.opener;
    S = null;
    inflight = false;
    if (back && back.focus && document.contains(back)) back.focus();
  }
  function close() { if (S) teardown(); }
  function dismiss() {
    const fromBoard = S && S.fromBoard;
    if (/^#game\//.test(location.hash)) {
      if (fromBoard) { close(); history.back(); return; }
      history.replaceState(null, "", location.pathname + location.search);
    }
    close();
    window.dispatchEvent(new CustomEvent("nflsheet:dismiss"));
  }
  function refresh() { if (S) load(true); }

  window.NFLSheet = { open, close, refresh };
})();
