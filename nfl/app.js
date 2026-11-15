/* Pro Football Board client. Optional /nfl/games.js (window.NFL_DATA) enriches /api/nfl/live. */
(() => {
  const SNAP = window.NFL_DATA || null;
  const $ = (id) => document.getElementById(id);
  const CT = "America/Chicago";
  const STAR_KEY = "nflb_stars_v1";
  const CARD_BG = "162036";
  const CT_PARTS = new Intl.DateTimeFormat("en-US", { timeZone: CT, weekday: "short", year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const KICK_FMT = new Intl.DateTimeFormat("en-US", { timeZone: CT, weekday: "short", hour: "numeric", minute: "2-digit" });
  const CLOCK_FMT = new Intl.DateTimeFormat("en-US", { timeZone: CT, hour: "numeric", minute: "2-digit", second: "2-digit" });
  const ESC_RE = new RegExp("[&<>\"']", "g");
  const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" };
  const WIN_LABEL = { flex: "Flex TBD", xmas: "Christmas", thanks: "Thanksgiving", wed: "Wed night", blackfri: "Black Friday", tnf: "TNF", fri: "Friday", sat: "Saturday", intl: "Int'l AM", sunE: "Sun early", sunL: "Sun late", snf: "SNF", mnf: "MNF", probowl: "Pro Bowl", other: "Other" };
  const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const STALE_MS = 18 * 3600000;
  const SWING_WINDOW_MS = 180000;
  const HYSTERESIS = 5;
  const VIEWS = ["live", "all", "starred"];

  let metrics = null;       // /nfl/metrics.json, optional
  let live = null;          // last good /api/nfl/live payload
  let liveErr = "";
  let lastOk = null;
  let games = [];
  let win = null;           // selected window pill
  let winPicked = false;    // the viewer chose; never move it for them
  let view = "";            // "" | live | all | starred (from the hash)
  let topId = null;         // desk hero, held by hysteresis
  let openId = null;        // game in the sheet
  let timer = null;
  let hiddenWait = false;
  let lastPollAt = 0;
  let polling = false;
  const ring = {};          // game id -> [{ t, wp }] of recent home win probability
  const stars = new Set(readJson(STAR_KEY, []));

  function readJson(key, dflt) {
    try { return JSON.parse(localStorage.getItem(key) || "null") || dflt; } catch (e) { return dflt; }
  }
  function esc(v) { return String(v ?? "").replace(ESC_RE, (c) => ESC_MAP[c]); }

  // ---------- pure helpers (extracted by scripts/nfl/checks/client.py) ----------
  function ctParts(date) {
    const o = {};
    for (const p of CT_PARTS.formatToParts(date)) o[p.type] = p.value;
    return { y: +o.year, mo: +o.month, d: +o.day, wd: o.weekday, min: (+o.hour % 24) * 60 + +o.minute };
  }
  function abroad(g) {
    const c = g.venue && g.venue.country;
    return c ? c !== "US" : !!g.neutral;
  }
  function nflWindowOf(g) {
    if (g.kind === "all_star") return "probowl";
    if (g.kind === "playoff") return "post:" + (g.round || "Playoffs");
    const d = new Date(g.date);
    if (g.time_tbd || isNaN(d)) return "flex";
    const c = ctParts(d);
    if (c.mo === 12 && (c.d === 24 || c.d === 25)) return "xmas";
    if (c.wd === "Thu" && c.mo === 11 && c.d >= 22 && c.d <= 28) return "thanks";
    if (c.wd === "Wed") return "wed";
    if (c.wd === "Fri" && c.mo === 11 && c.d >= 23 && c.d <= 29) return "blackfri";
    if (c.wd === "Thu") return "tnf";
    if (c.wd === "Fri") return "fri";
    if (c.wd === "Sat") return "sat";
    if (c.wd === "Sun") {
      if (c.min < 11 * 60 && abroad(g)) return "intl";
      if (c.min < 12 * 60 + 30) return "sunE";
      if (c.min < 18 * 60) return "sunL";
      return "snf";
    }
    if (c.wd === "Mon") return "mnf";
    return "other";
  }
  function defaultWindow(list, order) {
    const liveWin = order.find((w) => list.some((g) => g.win === w && g.state === "in"));
    if (liveWin) return liveWin;
    const next = order.find((w) => list.some((g) => g.win === w && g.state !== "post"));
    return next || order[order.length - 1] || "all";
  }
  function pollDelay(list, now) {
    if (list.some((g) => g.state === "in")) return 20000;
    const soon = list.some((g) => {
      const t = Date.parse(g.date || "");
      return g.state === "pre" && !g.time_tbd && !isNaN(t) && t - now <= 3600000 && t - now >= -10800000;
    });
    return soon ? 60000 : 120000;
  }
  function swingOf(samples, now) {
    const s = (samples || []).filter((x) => now - x.t <= SWING_WINDOW_MS);
    if (s.length < 2) return { pts: 0, toward: null };
    const d = s[s.length - 1].wp - s[0].wp;
    return { pts: Math.abs(d) * 100, toward: d > 0 ? "home" : d < 0 ? "away" : null };
  }
  function effScore(score, swingPts) {
    return score + Math.min(15, Math.round(swingPts));
  }
  function deskOrder(items, prevId) {
    const out = items.slice().sort((a, b) => b.eff - a.eff || b.prog - a.prog || a.kick - b.kick);
    const prev = out.find((x) => x.id === prevId);
    if (prev && out[0].id !== prevId && out[0].eff < prev.eff + HYSTERESIS) {
      out.splice(out.indexOf(prev), 1);
      out.unshift(prev);
    }
    return out.map((x) => x.id);
  }

  // ---------- colors ----------
  function hex6(v) {
    const s = String(v || "").replace("#", "").toLowerCase();
    return /^[0-9a-f]{6}$/.test(s) ? s : "";
  }
  function lum(hex) {
    const c = [0, 2, 4].map((i) => {
      const v = parseInt(hex.slice(i, i + 2), 16) / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function contrast(a, b) {
    const x = lum(a), y = lum(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  }
  // Team color first; alt when the color is unreadable or vanishes into the card; neutral otherwise.
  function chipColors(t) {
    for (const bg of [hex6(t && t.color), hex6(t && t.alt)]) {
      if (!bg || contrast(bg, CARD_BG) < 1.4) continue;
      const w = contrast(bg, "ffffff"), k = contrast(bg, "111111");
      if (Math.max(w, k) >= 3.5) return { bg, fg: w >= k ? "ffffff" : "111111" };
    }
    return { bg: "2a3a5a", fg: "f4f7fb" };
  }

  // ---------- model ----------
  function recText(r) {
    if (!r) return "";
    return typeof r === "string" ? r : (r.text || "");
  }
  function sideOf(s, l) {
    if (!s && !l) return null;
    s = s || {}; l = l || {};
    const lr = recText(l.record), sr = recText(s.record);
    const score = l.score != null ? l.score : (s.score === "" ? null : s.score);
    return {
      id: String(l.id || s.id || ""), abbr: l.abbr || s.abbr || "", name: s.full || l.name || s.name || "",
      color: s.color || "", alt: s.alt || "", rec: (lr && lr !== "0-0") || !sr ? lr : sr,
      score: score == null ? null : Number(score), timeouts: l.timeouts,
    };
  }
  function tvText(list) {
    return (list || []).map((b) => (typeof b === "string" ? b : (b && (b.name || b.shortName)) || "")).filter(Boolean).join(" / ");
  }
  function mergeGame(s, l, ctx) {
    s = s || {}; l = l || {};
    const away = sideOf(s.away, l.away), home = sideOf(s.home, l.home);
    const allStar = !!away && !!home && /^(AFC|NFC)$/.test(away.abbr) && /^(AFC|NFC)$/.test(home.abbr);
    const post = ctx.type === 3;
    const kind = s.kind || (allStar ? "all_star" : post ? "playoff" : "regular");
    const g = {
      id: String(l.id || s.id), state: l.state || s.state || "pre", status: l.status || "", statusShort: l.statusShort || "", period: l.period || 0,
      periodLabel: l.periodLabel || "", clock: l.clock || "", clock_s: l.clock_s, completed: !!(l.completed || s.state === "post"),
      ot: !!l.ot, result: l.result || null, date: l.date || s.date || "",
      time_tbd: l.time_tbd != null ? !!l.time_tbd : !!s.time_tbd, flex: l.flex_note || s.flex_note || "",
      neutral: l.neutral != null ? !!l.neutral : !!s.neutral, kind,
      round: s.round || (kind === "playoff" ? (s.week_label || ctx.label || "Playoffs") : null),
      tv: tvText(l.broadcasts && l.broadcasts.length ? l.broadcasts : s.broadcasts),
      venue: s.venue || (l.venue_name ? { name: l.venue_name } : null), wx: s.wx || null, wx_status: s.wx_status || "",
      situation: l.situation || null, wp: l.wp || null, desk: l.desk || null,
      away, home, ph: !!(l.placeholder || s.placeholder) || !away || !home,
    };
    if (g.state === "post" && !g.result && away && home && away.score != null && home.score != null) {
      g.result = away.score === home.score ? "tie" : (away.score > home.score ? "away" : "home");
    }
    g.win = nflWindowOf(g);
    return g;
  }
  function snapUsable() {
    if (!SNAP || !Array.isArray(SNAP.games)) return false;
    if (!live) return true;
    return !!(SNAP.week && live.week && SNAP.week.number === live.week.number && SNAP.season && live.season && SNAP.season.type === live.season.type);
  }
  function buildGames() {
    const ok = snapUsable();
    const by = {};
    if (ok) SNAP.games.forEach((s) => { by[String(s.id)] = s; });
    const src = live || SNAP || {};
    const ctx = { type: src.season && src.season.type, label: src.week && src.week.label };
    const list = live && live.games.length ? live.games.map((l) => mergeGame(by[String(l.id)], l, ctx)) : (ok ? SNAP.games.map((s) => mergeGame(s, null, ctx)) : []);
    return list;
  }
  function winOrder(list) {
    const first = {};
    list.forEach((g) => {
      const t = g.time_tbd ? Infinity : Date.parse(g.date || "");
      const v = isNaN(t) ? Infinity : t;
      if (!(g.win in first) || v < first[g.win]) first[g.win] = v;
    });
    return Object.keys(first).sort((a, b) => first[a] - first[b] || (a < b ? -1 : 1));
  }
  function winLabel(id) { return id.startsWith("post:") ? id.slice(5) : (WIN_LABEL[id] || id); }
  function isLive(g) { return g.state === "in"; }
  function kickMs(g) { const t = Date.parse(g.date || ""); return isNaN(t) || g.time_tbd ? Infinity : t; }
  function rank(g) { return g.state === "in" ? 0 : g.state === "pre" ? 1 : 2; }
  function sortGames(list) {
    return list.slice().sort((a, b) => rank(a) - rank(b)
      || (isLive(a) ? ((b.desk ? b.desk.score : 0) - (a.desk ? a.desk.score : 0)) : 0)
      || kickMs(a) - kickMs(b) || (a.id < b.id ? -1 : 1));
  }
  function visibleGames() {
    let list = games;
    if (view === "live") list = games.filter(isLive);
    else if (view === "starred") list = games.filter((g) => stars.has(g.id));
    else if (view !== "all" && win && win !== "all") list = games.filter((g) => g.win === win);
    return sortGames(list);
  }

  // ---------- formatting ----------
  function ctText(d) {
    const o = {};
    for (const p of KICK_FMT.formatToParts(d)) o[p.type] = p.value;
    return [o.weekday, o.hour + ":" + o.minute, o.dayPeriod, "CT"].filter(Boolean).join(" ");
  }
  function kickText(g) {
    if (g.time_tbd) return "TBD";
    const d = new Date(g.date);
    return isNaN(d) ? "TBD" : ctText(d);
  }
  function compass(deg) {
    if (deg == null || deg === "" || !isFinite(Number(deg))) return "";
    return COMPASS[Math.round(((Number(deg) % 360) + 360) % 360 / 22.5) % 16];
  }
  function wxStale(w, now) {
    if (!w) return false;
    const t = Date.parse(w.fetched_at || "");
    return !!w.stale || (!isNaN(t) && now - t > STALE_MS);
  }
  function signed(v, d) {
    const x = Number(v);
    if (v == null || !isFinite(x)) return "";
    return (x > 0 ? "+" : "") + x.toFixed(d);
  }
  function clockText(d) { return CLOCK_FMT.format(d) + " CT"; }
  function periodName(g) {
    if (g.periodLabel) return g.periodLabel;
    return g.period > 4 ? (g.period === 5 ? "OT" : (g.period - 4) + "OT") : g.period ? "Q" + g.period : "";
  }
  function stateInfo(g) {
    const st = g.status;
    if (st === "STATUS_POSTPONED") return { pill: "POSTPONED", text: "", final: true };
    if (st === "STATUS_CANCELED") return { pill: "CANCELED", text: "", final: true };
    if (g.state === "post") return { pill: g.ot ? "FINAL/OT" : "FINAL", text: g.result === "tie" ? "Tie game" : "", final: true };
    if (g.state !== "in") return { pill: "", text: "" };
    if (st === "STATUS_HALFTIME") return { pill: "HALF", text: "Halftime" };
    if (st === "STATUS_END_PERIOD") return { pill: "LIVE", text: "End of " + periodName(g) };
    if (st === "STATUS_DELAYED") return { pill: "DELAYED", text: periodName(g) + " " + g.clock };
    if (st === "STATUS_SUSPENDED") return { pill: "SUSPENDED", text: periodName(g) + " " + g.clock };
    if (/^End of /.test(g.statusShort || "")) return { pill: "LIVE", text: g.statusShort };
    return { pill: "LIVE", text: (periodName(g) + " " + g.clock).trim() };
  }
  function clampNum(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }

  // ---------- html builders (h* return markup; every ESPN string goes through esc) ----------
  function hChip(t, cls) {
    if (!t) return `<span class="tchip tbd">TBD</span>`;
    const c = chipColors(t);
    return `<span class="tchip${esc(cls || "")}" style="background:#${esc(c.bg)};color:#${esc(c.fg)}">${esc(t.abbr)}</span>`;
  }
  function hTeam(g, side) {
    const t = g[side];
    const show = g.state !== "pre" && t.score != null;
    const done = g.state === "post" && g.result && g.result !== "tie";
    const rowCls = done ? (g.result === side ? " win" : " lose") : "";
    const s = g.situation;
    const ballHtml = s && g.state === "in" && s.possession === side ? `<span class="poss" title="Has the ball"></span>` : "";
    const scoreText = show ? String(t.score) : "";
    return `<div class="trow${rowCls}">${hChip(t)}<span class="name">${esc(t.name || t.abbr)}</span><span class="rec">${esc(t.rec)}</span><span class="score">${ballHtml}${esc(scoreText)}</span></div>`;
  }
  function hField(g) {
    const s = g.situation;
    if (!s || s.yl100 == null || !s.possession) return "";
    const y = Number(s.yl100);
    if (!isFinite(y)) return "";
    const awayBall = s.possession === "away";
    const x = clampNum(awayBall ? 100 - y : y, 0, 100);
    const posPct = (8 + x * 0.84).toFixed(1);
    const l = chipColors(g.away), r = chipColors(g.home);
    const rzHtml = s.is_red_zone ? `<i class="rzone ${awayBall ? "r" : "l"}"></i>` : "";
    const ticksHtml = [20, 30, 40, 50, 60, 70, 80].map((n) => {
      const tickPct = (8 + n * 0.84).toFixed(1);
      return `<i class="yd" style="left:${tickPct}%"></i>`;
    }).join("");
    const label = (s.possession_abbr || "") + " ball" + (s.yard_text ? ", " + s.yard_text : "");
    return `<div class="field" role="img" aria-label="${esc(label)}"><i class="ez l" style="background:#${esc(l.bg)}"></i><i class="ez r" style="background:#${esc(r.bg)}"></i>${rzHtml}${ticksHtml}<b class="ball" style="left:${posPct}%"></b></div>`;
  }
  function hLive(g) {
    const info = stateInfo(g);
    if (!info.pill) return "";
    const s = g.state === "in" ? g.situation : null;
    const down = s ? (s.stoppage ? "Stoppage" : (s.text || "")) : "";
    const who = s && s.possession_abbr ? s.possession_abbr + " ball" : "";
    const rzHtml = s && s.is_red_zone ? `<span class="rz">${s.goal_to_go ? "GOAL TO GO" : "RED ZONE"}</span>` : "";
    const lpHtml = s && s.last_play && s.last_play.text ? `<div class="lastp">${esc(s.last_play.text)}</div>` : "";
    const pillCls = info.final ? " final" : "";
    const bitsText = [who, down].filter(Boolean).join(" · ");
    const bitsHtml = bitsText ? ` <span>${esc(bitsText)}</span>` : "";
    return `<div class="liverow"><div class="lr1"><span class="livepill${pillCls}">${esc(info.pill)}</span><span class="clk">${esc(info.text)}</span>${bitsHtml}${rzHtml}</div>${hField(g)}${lpHtml}</div>`;
  }
  function hMetaTv(g) {
    return g.tv ? `<span class="tv">${esc(g.tv)}</span>` : "";
  }
  function hWx(g) {
    const w = g.wx, st = g.wx_status;
    if (st === "dome") return `<div class="wx"><div class="cond"><b>Indoors</b><span class="mini">Dome</span></div></div>`;
    if (!w || (st && st !== "ok" && st !== "retractable" && st !== "canopy" && !w.stale)) return "";
    const n = (v, u) => (v == null || v === "" || !isFinite(Number(v)) ? "" : Math.round(Number(v)) + u);
    const cell = (lab, val) => (val ? `<div><div class="mini">${esc(lab)}</div><div class="val">${esc(val)}</div></div>` : "");
    const chipsHtml = (w.flags || []).map((f) => `<span class="flag">${esc(f)}</span>`).join("");
    const fetched = new Date(w.fetched_at || "");
    const staleNote = wxStale(w, Date.now()) && !isNaN(fetched) ? `Forecast from ${esc(ctText(fetched))}, may be out of date.` : "";
    const noteText = [w.roof_note, staleNote].filter(Boolean).join(" ");
    const noteHtml = noteText ? `<div class="note">${esc(noteText)}</div>` : "";
    const windText = n(w.wind, " mph") ? n(w.wind, " mph") + (compass(w.winddir) ? " " + compass(w.winddir) : "") : "";
    const condHtml = `<div class="cond"><b>${esc(n(w.temp, "°"))}</b><span class="mini">${esc(w.label || "")}</span></div>`;
    const cellsHtml = cell("Wind", windText) + cell("Gusts", n(w.gusts, " mph")) + cell("Rain", n(w.pop, "%")) + cell("Feels", n(w.apparent, "°"));
    const flagsHtml = chipsHtml ? `<div class="flags">${chipsHtml}</div>` : "";
    return `<div class="wx">${condHtml}${cellsHtml}${noteHtml}</div>${flagsHtml}`;
  }
  function ord(v) { return v == null ? "" : " #" + Number(v); }
  function metricsFor(abbr) {
    const t = metrics && metrics.teams && metrics.teams[abbr];
    return t && t.off && t.def && !t.small_sample ? t : null;
  }
  function hMetricRows(o, d, oa, da) {
    const rows = [
      ["EPA/play", signed(o.off.epa, 3) + ord(o.off.epa_rank), signed(d.def.epa, 3) + ord(d.def.epa_rank)],
      ["Success rate", (o.off.sr * 100).toFixed(1) + "%" + ord(o.off.sr_rank), (d.def.sr * 100).toFixed(1) + "%" + ord(d.def.sr_rank)],
    ];
    if (o.off.proe != null) rows.push(["PROE", signed(o.off.proe, 1) + " pts" + ord(o.off.proe_rank), ""]);
    const bodyHtml = rows.map((r) => `<div class="mrow"><span>${esc(r[1])}</span><span class="mlab">${esc(r[0])}</span><span>${esc(r[2])}</span></div>`).join("");
    return `<div class="mt">${esc(oa)} offense vs ${esc(da)} defense</div>${bodyHtml}`;
  }
  function hMetrics(g) {
    if (!metrics || g.ph || !g.away || !g.home) return "";
    const y = (live || SNAP || {}).season;
    if (y && metrics.season && y.year && Number(y.year) !== Number(metrics.season)) return "";
    const a = metricsFor(g.away.abbr), h = metricsFor(g.home.abbr);
    if (!a || !h) return "";
    const wk = metrics.through_week ? ", through Week " + Number(metrics.through_week) : "";
    const footHtml = `<div class="mfoot">nflverse${esc(wk)}, CC BY 4.0. Season to date, per play.</div>`;
    return `<div class="mx">${hMetricRows(a, h, g.away.abbr, g.home.abbr)}${hMetricRows(h, a, g.home.abbr, g.away.abbr)}${footHtml}</div>`;
  }
  function hVenue(g) {
    const v = g.venue;
    if (!v || !v.name) return "";
    const place = [v.city, v.region].filter(Boolean).join(", ");
    const roofName = { dome: "Dome", retractable: "Retractable roof", canopy: "Canopy" }[v.roof] || "";
    const roofHtml = roofName ? ` <span class="tag roof">${esc(roofName)}</span>` : "";
    const placeHtml = place ? " · " + esc(place) : "";
    return `<div class="venue"><b>${esc(v.name)}</b>${placeHtml}${roofHtml}</div>`;
  }
  function hCard(g) {
    const star = stars.has(g.id);
    const label = winLabel(g.win);
    const vsHtml = g.neutral ? `<span class="tag vs" title="Neutral site">VS · neutral site</span>` : "";
    const flexHtml = g.time_tbd && g.flex ? `<span class="flexnote">${esc(g.flex)}</span>` : "";
    const metaHtml = `<div class="meta"><span><span class="tag win">${esc(label)}</span>${vsHtml}<span class="kick">${esc(kickText(g))}</span>${flexHtml}</span><span class="right">${hMetaTv(g)}<button class="star${star ? " on" : ""}" data-star="${esc(g.id)}" aria-pressed="${star ? "true" : "false"}" aria-label="Star game">${star ? "★" : "☆"}</button></span></div>`;
    if (g.ph) {
      const roundHtml = esc(g.round || "Matchup to be decided");
      const rowHtml = `<div class="trow">${hChip(null)}<span class="name">TBD</span><span class="rec"></span><span class="score"></span></div>`;
      return `<article class="card is-ph" id="g${esc(g.id)}">${metaHtml}<div class="teams">${rowHtml}${rowHtml}</div><div class="phnote">${roundHtml}. Teams are set after the earlier round.</div></article>`;
    }
    const liveCls = g.state === "in" ? " is-live" : g.state === "post" ? " is-final" : "";
    const bodyHtml = `<a class="cardlink" href="#game/${esc(g.id)}" aria-label="Open game sheet"><div class="teams">${hTeam(g, "away")}${hTeam(g, "home")}</div>${hLive(g)}</a>`;
    return `<article class="card${liveCls}" id="g${esc(g.id)}">${metaHtml}${bodyHtml}${hVenue(g)}${hWx(g)}${hMetrics(g)}</article>`;
  }
  function hDeskCard(g, i, swing) {
    const a = g.away, h = g.home;
    const info = stateInfo(g);
    const whyHtml = (g.desk.why || []).map((w) => `<span class="tag watch">${esc(w)}</span>`).join("");
    const swingNum = Math.round(swing.pts);
    const swHtml = swing.pts >= 4 && swing.toward ? `<span class="tag swing">WP swing ${esc(g[swing.toward].abbr)} +${swingNum}</span>` : "";
    const lpHtml = i === 0 && g.situation && g.situation.last_play ? `<div class="d">${esc(g.situation.last_play.text)}</div>` : "";
    const heroCls = i === 0 ? " hero" : "";
    const rankNum = i + 1;
    const textHtml = esc(info.text) + (g.situation && g.situation.text ? " · " + esc(g.situation.text) : "");
    return `<a class="deskcard${heroCls}" href="#game/${esc(g.id)}"><div class="t"><span class="rk">#${rankNum}</span>${esc(a.abbr)} ${esc(a.score ?? 0)} - ${esc(h.score ?? 0)} ${esc(h.abbr)}</div><div class="d">${textHtml}</div><div class="why">${whyHtml}${swHtml}</div>${lpHtml}</a>`;
  }
  function hNext(g, now) {
    const mins = Math.max(0, Math.round((kickMs(g) - now) / 60000));
    const whenText = mins ? "in " + mins + " min" : "now";
    const sepText = g.neutral ? "vs" : "@";
    return `<a href="#game/${esc(g.id)}"><span>${esc(g.away.abbr)} ${esc(sepText)} ${esc(g.home.abbr)} · ${esc(kickText(g))}</span><span>${esc(whenText)}</span></a>`;
  }

  // ---------- render ----------
  function weekInfo() {
    const src = live || SNAP;
    if (!src || !src.week) return null;
    const n = src.week.number;
    const label = src.week.label || (n ? "Week " + n : "");
    return { label, year: src.season && src.season.year };
  }
  function renderHead() {
    const w = weekInfo();
    $("kicker").textContent = w ? w.label + (w.year ? " · " + w.year : "") : "NFL";
    document.title = w ? "Pro Football Board - " + w.label + (w.year ? ", " + w.year : "") : "Pro Football Board";
    const every = Math.round(pollDelay(games, Date.now()) / 1000);
    $("updated").textContent = lastOk ? "Updated " + clockText(lastOk) + " · refreshes every " + every + "s" : (liveErr ? "Live scores unavailable" : "Loading scores...");
  }
  function renderBanner() {
    const msgs = [];
    let err = false;
    if (liveErr) { msgs.push(lastOk ? "Live scores could not refresh. Showing the last data from " + clockText(lastOk) + "." : "Live scores are unavailable right now."); err = !lastOk; }
    if (live && live.stale) msgs.push("ESPN is slow to answer. Scores shown may be a few minutes old.");
    if (!SNAP) msgs.push("Weather, roof and matchup data appear when this week's snapshot is published.");
    else if (live && !snapUsable()) msgs.push("The weekly snapshot is for another week, so weather and matchup data are hidden.");
    const el = $("banner");
    el.hidden = !msgs.length;
    el.className = "banner" + (err ? " err" : "");
    el.innerHTML = msgs.map((m) => `<p>${esc(m)}</p>`).join("");
  }
  function renderPills() {
    const order = winOrder(games);
    if (!winPicked) win = defaultWindow(games, order);
    const nLive = games.filter(isLive).length;
    const nStar = games.filter((g) => stars.has(g.id)).length;
    const btn = (id, label, on, extraHtml = "") => `<button class="fbtn${on ? " active" : ""}" data-win="${esc(id)}" aria-pressed="${on ? "true" : "false"}">${extraHtml}${esc(label)}</button>`;
    const parts = [];
    const nLiveNum = nLive, nStarNum = nStar;
    if (nLive) parts.push(`<button class="fbtn${view === "live" ? " active" : ""}" data-view="live" aria-pressed="${view === "live" ? "true" : "false"}"><span class="dot"></span>Live<span class="cnt">${nLiveNum}</span></button>`);
    parts.push(btn("all", "All", view === "all" || (!view && win === "all")));
    order.forEach((w) => {
      const dotHtml = games.some((g) => g.win === w && isLive(g)) ? `<span class="dot"></span>` : "";
      parts.push(btn(w, winLabel(w), !view && win === w, dotHtml));
    });
    if (nStar) parts.push(`<button class="fbtn${view === "starred" ? " active" : ""}" data-view="starred" aria-pressed="${view === "starred" ? "true" : "false"}">★<span class="cnt">${nStarNum}</span></button>`);
    $("pills").innerHTML = parts.join("");
  }
  function renderDesk() {
    const el = $("desk");
    const now = Date.now();
    const liveG = games.filter((g) => isLive(g) && g.desk && !g.ph);
    const soon = games.filter((g) => g.state === "pre" && !g.ph && kickMs(g) - now <= 1800000 && kickMs(g) - now >= -60000)
      .sort((a, b) => kickMs(a) - kickMs(b)).slice(0, 4);
    if (!liveG.length && !soon.length) { el.innerHTML = ""; el.hidden = true; return; }
    el.hidden = false;
    let html = "";
    if (liveG.length) {
      const items = liveG.map((g) => ({ id: g.id, eff: effScore(g.desk.score, swingOf(ring[g.id], now).pts), prog: (g.period || 0) * 1000 - (g.clock_s || 0), kick: kickMs(g) }));
      const order = deskOrder(items, topId);
      topId = order[0];
      const byId = {};
      liveG.forEach((g) => { byId[g.id] = g; });
      const cardsHtml = order.slice(0, 3).map((id, i) => hDeskCard(byId[id], i, swingOf(ring[id], now))).join("");
      html += `<h2>Whip-around</h2>${cardsHtml}`;
    } else topId = null;
    const nextHtml = soon.map((g) => hNext(g, now)).join("");
    if (soon.length) html += `<div class="nextup"><h2>Next up</h2>${nextHtml}</div>`;
    el.innerHTML = html;
  }
  function emptyHtml() {
    if (view === "live") {
      const next = games.filter((g) => g.state === "pre" && !g.ph && kickMs(g) < Infinity).sort((a, b) => kickMs(a) - kickMs(b))[0];
      return `<div class="empty">No games are live right now.${next ? `<br />Next kickoff: <b>${esc(next.away.abbr)} ${next.neutral ? "vs" : "@"} ${esc(next.home.abbr)}</b> · ${esc(kickText(next))}` : ""}</div>`;
    }
    if (view === "starred") return `<div class="empty">Tap the star on a game to keep it here.</div>`;
    if (!live && !liveErr) return `<div class="empty">Loading scores...</div>`;
    return `<div class="empty">No games to show yet.</div>`;
  }
  function renderMain() {
    const list = visibleGames();
    const cardsHtml = list.map(hCard).join("");
    $("main").innerHTML = list.length ? `<div class="list cards">${cardsHtml}</div>` : emptyHtml();
  }
  function renderBye() {
    const src = live || SNAP;
    const raw = (src && src.teams_on_bye) || [];
    const names = {};
    if (SNAP && Array.isArray(SNAP.teams_on_bye)) SNAP.teams_on_bye.forEach((t) => { if (t && t.abbr) names[t.abbr] = t; });
    const teams = raw.map((t) => (typeof t === "string" ? (names[t] || { abbr: t }) : t)).filter((t) => t && t.abbr);
    const chipsHtml = teams.map((t) => hChip(t)).join("");
    $("bye").innerHTML = teams.length ? `<b>On bye</b> ${chipsHtml}` : "";
  }
  function render() {
    games = buildGames();
    renderHead(); renderBanner(); renderPills(); renderDesk(); renderMain(); renderBye();
  }

  // ---------- polling ----------
  function snapPast() {
    const end = SNAP && SNAP.week && Date.parse(SNAP.week.end || "");
    return !!end && !isNaN(end) && Date.now() >= end;
  }
  function liveUrl() {
    const w = SNAP && SNAP.week, s = SNAP && SNAP.season;
    if (w && s && w.number && s.type && !snapPast()) return `/api/nfl/live?st=${Number(s.type)}&week=${Number(w.number)}`;
    return "/api/nfl/live";
  }
  function pushRing(list, now) {
    list.forEach((g) => {
      const wp = g.wp && g.wp.home;
      const key = String(g.id);
      if (g.state !== "in" || typeof wp !== "number") { delete ring[key]; return; }
      ring[key] = (ring[key] || []).filter((x) => now - x.t <= SWING_WINDOW_MS).concat([{ t: now, wp }]);
    });
  }
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (document.hidden) { hiddenWait = true; return; }
      pollLive();
    }, pollDelay(games, Date.now()));
  }
  async function pollLive() {
    if (polling) return;
    polling = true;
    clearTimeout(timer);
    hiddenWait = false;
    const ctl = typeof AbortController === "function" ? new AbortController() : null;
    const guard = setTimeout(() => { if (ctl) ctl.abort(); }, 12000);
    try {
      const res = await fetch(liveUrl(), { cache: "no-store", signal: ctl ? ctl.signal : undefined });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (!data || data.ok === false || !Array.isArray(data.games)) throw new Error("bad payload");
      live = data; liveErr = ""; lastOk = new Date();
      pushRing(data.games, Date.now());
    } catch (e) {
      liveErr = String((e && e.message) || e);
    }
    clearTimeout(guard);
    lastPollAt = Date.now();
    polling = false;
    render();
    window.dispatchEvent(new CustomEvent("nfl:update"));
    schedule();
  }

  // ---------- routing and events ----------
  function applyHash() {
    const h = location.hash.replace(/^#/, "");
    const m = /^game\/(\d{9,12})$/.exec(h);
    if (m) {
      openId = m[1];
      if (window.NFLSheet) window.NFLSheet.open(openId);
      return;
    }
    if (openId && window.NFLSheet) window.NFLSheet.close();
    openId = null;
    const lower = h.toLowerCase();
    view = VIEWS.includes(lower) ? lower : "";
    render();
  }
  function clearView() {
    if (VIEWS.includes(location.hash.replace(/^#/, "").toLowerCase())) history.replaceState(null, "", location.pathname + location.search);
    view = "";
  }
  document.addEventListener("click", (ev) => {
    const t = ev.target.closest ? ev.target.closest("[data-win],[data-view],[data-star]") : null;
    if (!t) return;
    if (t.dataset.star) {
      const id = t.dataset.star;
      if (stars.has(id)) stars.delete(id); else stars.add(id);
      try { localStorage.setItem(STAR_KEY, JSON.stringify([...stars])); } catch (e) { /* private mode */ }
      render();
    } else if (t.dataset.view || t.dataset.win === "all") {
      const v = t.dataset.view || "all";
      if (view === v) { clearView(); render(); } else location.hash = v;
      winPicked = winPicked || v === "all";
    } else {
      winPicked = true; win = t.dataset.win;
      clearView();
      render();
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    if (hiddenWait || Date.now() - lastPollAt > pollDelay(games, Date.now())) pollLive();
  });
  async function loadMetrics() {
    try {
      const res = await fetch("/nfl/metrics.json");
      if (!res.ok) return;
      const m = await res.json();
      if (!m || typeof m.teams !== "object" || !m.teams) return;
      metrics = m;
      render();
    } catch (e) { /* optional */ }
  }
  function registerSw() {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator) || location.protocol === "file:") return;
    navigator.serviceWorker.register("/nfl/sw.js", { scope: "/nfl/" }).catch(() => {});
  }
  window.addEventListener("hashchange", applyHash);
  window.NFLBoard = {
    game: (id) => games.find((g) => g.id === String(id)) || null,
    games: () => games.slice(),
    updatedAt: () => lastOk,
  };
  applyHash();
  render();
  pollLive();
  loadMetrics();
  registerSw();
})();
