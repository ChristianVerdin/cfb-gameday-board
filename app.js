/* loaded after games.js */
(() => {
  const DATA = window.CFB_DATA || { games: [] };
  const games = DATA.games || [];
  const $ = (id) => document.getElementById(id);
  const STAR_KEY = "cfb_gameday_stars_v1";
  const stars = new Set(JSON.parse(localStorage.getItem(STAR_KEY) || "[]"));
  // Client line book: last non-null odds per game. ESPN nulls odds on finals, so this is the closing line.
  const LINES_KEY = "cfb_gameday_lines_v1";
  let lineBook = {};
  try { lineBook = JSON.parse(localStorage.getItem(LINES_KEY) || "{}") || {}; } catch (e) { lineBook = {}; }
  let lineBookDirty = false;
  // Only ids in the current snapshot are ever read back (chooseOdds keys off g.id), so
  // drop the rest: a season of dead ids would otherwise accumulate and be reparsed on
  // every load. Stars are deliberately never pruned - those are user intent.
  {
    const live = new Set(games.map(g => g.id));
    const keep = {};
    let dropped = 0;
    for (const k of Object.keys(lineBook)) { if (live.has(k)) keep[k] = lineBook[k]; else dropped++; }
    if (dropped) { lineBook = keep; lineBookDirty = true; }
  }
  const CT = "America/Chicago";
  const ET = "America/New_York";
  const etDateFmt = new Intl.DateTimeFormat("en-CA", { timeZone: ET, year:"numeric", month:"2-digit", day:"2-digit" });
  const ctDateFmt = new Intl.DateTimeFormat("en-CA", { timeZone: CT, year:"numeric", month:"2-digit", day:"2-digit" });
  const ctTimeFmt = new Intl.DateTimeFormat("en-US", { timeZone: CT, hour:"2-digit", minute:"2-digit", hourCycle:"h23" });
  const ctDayFmt = new Intl.DateTimeFormat("en-US", { timeZone: CT, weekday:"short" });
  function kickDate(g) { const d = new Date(g.date || ""); return isNaN(d) ? null : d; }
  function slateDay(g) { const d = kickDate(g); return d ? ctDateFmt.format(d) : (g.date || "").slice(0,10); }
  const slateDays = [...new Set(games.map(slateDay))].filter(Boolean).sort();
  const days = [{ id:"all", label:"All" }, ...slateDays.map(id => {
    const g = games.find(x => slateDay(x) === id);
    return { id, label: g && kickDate(g) ? ctDayFmt.format(kickDate(g)) : id.slice(5) };
  })];
  const todayCT = ctDateFmt.format(new Date());
  const busiestDay = slateDays.slice().sort((a,b) => games.filter(g=>slateDay(g)===b).length - games.filter(g=>slateDay(g)===a).length)[0];
  const windows = [
    { id:"all", label:"All times" }, { id:"early", label:"Noon" },
    { id:"aft", label:"Afternoon" }, { id:"night", label:"Primetime+" }
  ];
  const views = [
    { id:"cards", label:"Cards" }, { id:"lines", label:"Lines sheet" },
    { id:"tv", label:"By TV" }, { id:"blowouts", label:"Blowouts" }
  ];
  let day = slateDays.includes(todayCT) ? todayCT : (busiestDay || "all"), win="all", view="cards", ranked=false, starredOnly=false, weatherOnly=false, liveOnly=false, confOnly=false, group="all", q="", sort="time";
  let liveStatus = { ok:false, fromFile: location.protocol === "file:", last:null, error:null };
  // Filter panel: collapsed on phones so the first game is above the fold, open on wide screens.
  const FILTERS_KEY = "cfb_gameday_filters_open";
  let filtersOpen = window.matchMedia("(min-width: 900px)").matches;
  try { const s = localStorage.getItem(FILTERS_KEY); if (s !== null) filtersOpen = s === "1"; } catch (e) {}
  function activeFilters() {
    return [group !== "all", confOnly, ranked, starredOnly, liveOnly, weatherOnly, win !== "all", sort !== "time"].filter(Boolean).length;
  }
  function resetFilters() {
    group = "all"; win = "all"; sort = "time"; q = "";
    confOnly = ranked = starredOnly = liveOnly = weatherOnly = false;
    $("q").value = "";
    pills(); render();
  }

  function kickMinutes(g) {
    const d = kickDate(g);
    if (!d) return 0;
    const parts = Object.fromEntries(ctTimeFmt.formatToParts(d).map(p => [p.type, p.value]));
    return (parseInt(parts.hour,10) % 24) * 60 + parseInt(parts.minute,10);
  }
  function windowOf(g) {
    const m = kickMinutes(g);          // CT minutes
    if (m < 13*60+30) return "early";  // through 1:30 PM CT kicks
    if (m < 18*60) return "aft";       // through 5:59 PM CT
    return "night";
  }
  function fmtKick(g) { return g.kick_ct || (g.statusShort || "").replace(/^\d{1,2}\/\d{1,2}\s+-\s+/, ""); }
  function rank(t) { return (t && t.rank && t.rank < 30) ? `<span class="rank">#${t.rank}</span>` : ""; }
  // Conference game: the snapshot's flag when the pipeline has emitted it, else same
  // conference on both sides. A cached games.js predates the field, hence the fallback.
  function isConfGame(g) {
    if (typeof g.conf_game === "boolean") return g.conf_game;
    const h = g.home || {}, a = g.away || {};
    return !!h.conferenceId && h.conferenceId === a.conferenceId
           && h.conference !== "FCS" && h.conference !== "Independent";
  }
  function flagClass(f) {
    if (["EXTREME HEAT","HOT","COLD","FREEZING"].includes(f)) return "hot";
    if (["RAIN RISK","SHOWERS"].includes(f)) return "rain";
    if (f.includes("WIND") || f==="ALTITUDE") return "wind";
    if (f==="INDOOR") return "indoor";
    return "";
  }
  function juice(v) { return (!v || v==="OFF") ? "OFF" : v; }
  function num(v) { const n = Number(v); return Number.isFinite(n) ? n : 0; }
  function isLive(g) { return g.gameState === "in" || g.status === "STATUS_IN_PROGRESS" || g.status === "STATUS_HALFTIME"; }
  function isFinal(g) { return g.gameState === "post" || g.completed || (g.status || "").includes("FINAL"); }
  // CLAUDE.md: the implied score is never shown once a game starts. The real score is
  // on the card by then, and "proj" beside it reads as a prediction of a known result.
  function started(g) { return isLive(g) || isFinal(g); }
  function clockLabel(g) {
    if (isFinal(g)) return "FINAL";
    if (isLive(g)) { const st = g.statusShort || g.statusDetail || "LIVE"; return (g.clock && !st.includes(g.clock)) ? `${st} · ${g.clock}` : st; }
    return fmtKick(g);
  }
  function liveMath(g) {
    const a = g.away || {}, h = g.home || {}, o = g.odds || {};
    const as = num(a.score), hs = num(h.score);
    const combined = as + hs;
    const margin = hs - as;
    const homeSpread = o.spread != null ? Number(o.spread) : null;
    const total = o.total != null ? Number(o.total) : null;
    const out = { combined, margin, as, hs, homeSpread, total };
    if (total != null) {
      out.overNeed = +(total - combined).toFixed(1);
      out.totalState = combined > total ? "OVER" : combined === total ? "PUSH" : "UNDER";
    }
    if (homeSpread != null) {
      const coverBy = +(margin + homeSpread).toFixed(1);
      out.coverBy = coverBy;
      out.coverState = coverBy > 0 ? "HOME COVER" : coverBy === 0 ? "PUSH" : "AWAY COVER";
      out.favNeed = coverBy < 0 ? +(-coverBy).toFixed(1) : 0;
    }
    return out;
  }
  // Which odds to keep: a real incoming line wins (unless the game is over and we already hold its close);
  // a null incoming line falls back to the stored close, then to whatever we had.
  function chooseOdds(stored, incoming, state, current) {
    const real = incoming && (incoming.spread != null || incoming.total != null);
    if (real) return (state === "post" && stored) ? stored : incoming;
    return stored || current || null;
  }
  // ESPN dates (Eastern calendar) that still have a game not yet final. Dates with no games are skipped:
  // api/live 502s when every date it is asked for is empty, and a Tue..Mon slate usually has empty days.
  function liveDatesFor(list, dates) {
    const byDate = {};
    list.forEach(g => {
      const d = kickDate(g); if (!d) return;
      const key = etDateFmt.format(d).replace(/-/g, "");
      (byDate[key] = byDate[key] || []).push(g);
    });
    const known = (dates && dates.length) ? dates.map(String) : Object.keys(byDate).sort();
    return known.filter(k => byDate[k] && byDate[k].some(g => !isFinal(g)));
  }
  // #live / #starred / #all in the URL set the filters (native app tabs and shareable links).
  function hashFilters(hash) {
    const h = String(hash || "").replace(/^#/, "").toLowerCase();
    const views = ["lines", "tv", "blowouts"];
    return { liveOnly: h === "live", starredOnly: h === "starred", view: views.includes(h) ? h : "cards",
             known: ["", "all", "live", "starred", ...views].includes(h) };
  }
  // ESPN sometimes serves "0-0" on the live scoreboard after games were played; keep the real one.
  function betterRecord(current, incoming) {
    if (!incoming) return current || "";
    if (incoming === "0-0" && current && current !== "0-0") return current;
    return incoming;
  }
  function applyLive(g, live) {
    g.gameState = live.state || g.gameState;
    g.status = live.status || g.status;
    g.statusDetail = live.statusDetail || g.statusDetail;
    g.statusShort = live.statusShort || g.statusShort;
    g.period = live.period;
    g.clock = live.clock;
    g.completed = live.completed;
    g.situation = live.situation;
    if (live.home && g.home) {
      g.home.score = String(live.home.score ?? g.home.score ?? "");
      g.home.record = betterRecord(g.home.record, live.home.record);
    }
    if (live.away && g.away) {
      g.away.score = String(live.away.score ?? g.away.score ?? "");
      g.away.record = betterRecord(g.away.record, live.away.record);
    }
    const chosen = chooseOdds(lineBook[g.id], live.odds, live.state, g.odds);
    if (chosen && chosen !== lineBook[g.id]) { lineBook[g.id] = chosen; lineBookDirty = true; }
    if (chosen) {
      g.odds = Object.assign({}, g.odds || {}, chosen);
      if (g.odds.total != null && g.odds.spread != null) {
        const total = Number(g.odds.total), hs = Number(g.odds.spread);
        g.implied = { home: +((total - hs) / 2).toFixed(1), away: +((total + hs) / 2).toFixed(1) };
        g.spread_abs = Math.abs(hs);
        g.blowout = g.spread_abs >= 28;
      }
    }
  }
  async function pollLive() {
    if (liveStatus.fromFile) {
      liveStatus.error = "Open via python3 server.py — file:// cannot pull live scores";
      render();
      return;
    }
    const dates = liveDatesFor(games, DATA.dates);
    if (!dates.length) { liveStatus.ok = true; liveStatus.last = new Date(); render(); return; }   // slate is over
    try {
      const res = await fetch("/api/live?dates=" + dates.join(","), { cache: "no-store" });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "live failed");
      const map = {};
      (data.games || []).forEach(g => { map[g.id] = g; });
      games.forEach(g => { if (map[g.id]) applyLive(g, map[g.id]); });
      if (lineBookDirty) { try { localStorage.setItem(LINES_KEY, JSON.stringify(lineBook)); } catch (e) {} lineBookDirty = false; }
      liveStatus.ok = true;
      liveStatus.error = null;
      liveStatus.last = new Date();
    } catch (err) {
      liveStatus.ok = false;
      liveStatus.error = String(err.message || err);
    }
    render();
    if (sheet) {
      const g = games.find(x => x.id === sheet.id);
      if (g && isLive(g)) loadGame(sheet.id);                              // live: refresh with the board
      else if (g && started(g) && !sheet.data && !sheet.loading) loadGame(sheet.id);   // kicked off while open
      else renderGame();
    }
  }
  function mapsUrl(g) { return "https://maps.apple.com/?q=" + encodeURIComponent([g.venue,g.city,g.state].filter(Boolean).join(" ")); }
  function teamLabel(t) { return t ? `${(t.rank && t.rank<30)?"#"+t.rank+" ":""}${t.name}` : "TBD"; }
  function blurb(g) {
    const a=g.away||{}, h=g.home||{}, o=g.odds||{}, wx=g.wx||{}, impl=g.implied||{};
    return [
      `${teamLabel(a)} ${g.neutral?"vs":"@"} ${teamLabel(h)}`,
      `${fmtKick(g)} · ${(g.networks||g.broadcasts||[]).join("/")}`,
      [g.venue, [g.city,g.state].filter(Boolean).join(", ")].filter(Boolean).join(" · "),
      [g.wx_emoji, g.temp!=null?Math.round(g.temp)+"°":"", g.wx_label, wx.wind!=null?`wind ${Math.round(wx.wind)} ${g.wind_dir||""}`:"", wx.pop!=null?`rain ${wx.pop}%`:""].filter(Boolean).join(" · "),
      [o.details, o.total!=null?`o/u ${o.total}`:"", (!started(g) && impl.home!=null)?`proj ${a.abbr} ${impl.away} – ${h.abbr} ${impl.home}`:""].filter(Boolean).join(" · "),
      (g.impact_notes||[])[0]||""
    ].filter(Boolean).join("\n");
  }
  async function copyText(text, btn) {
    try { await navigator.clipboard.writeText(text); if (btn) { const old=btn.textContent; btn.textContent="Copied"; setTimeout(()=>btn.textContent=old,1200);} }
    catch(e) { alert(text); }
  }
  // Game sheet (#game/<id>): ESPN summary trimmed by /api/game. Every ESPN string goes through esc().
  function esc(v) { return String(v ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[c]); }
  function gameHash(hash) { const m = /^#game\/(\d{6,12})$/.exec(String(hash || "")); return m ? m[1] : null; }
  let sheet = null;   // { id, tab, data, error, loading, fromBoard, prevHash }
  async function loadGame(id) {
    if (!sheet || sheet.id !== id) return;
    sheet.loading = true; renderGame();
    try {
      const res = await fetch("/api/game?id=" + id, { cache: "no-store" });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "game failed");
      if (sheet && sheet.id === id) { sheet.data = data; sheet.error = null; }
    } catch (err) {
      if (sheet && sheet.id === id) sheet.error = String(err.message || err);
    }
    if (sheet && sheet.id === id) { sheet.loading = false; renderGame(); }
  }
  function openGame(id, fromBoard, prevHash) {
    if (sheet && sheet.id === id) return;
    sheet = { id, tab: "scoring", data: null, error: null, loading: false, fromBoard, prevHash };
    document.body.classList.add("gopen");
    const g = games.find(x => x.id === id);
    if (g && started(g) && !liveStatus.fromFile) loadGame(id); else renderGame();
  }
  function closeGame() {
    sheet = null;
    document.body.classList.remove("gopen");
    const el = $("gsheet"); if (el) el.hidden = true;
  }
  function dismissGame() {
    if (sheet && sheet.fromBoard) { history.back(); return; }   // hashchange closes it
    history.replaceState(null, "", location.pathname + location.search);
    closeGame();
  }
  function winprobSvg(wp, a, h) {
    const pts = (wp && wp.points) || [];
    if (pts.length < 2) return "";
    const W = 300, H = 80, x = i => (i * W / (pts.length - 1)).toFixed(1), y = v => (H - v * H / 100).toFixed(1);
    const last = pts[pts.length - 1];
    const lead = last >= 50 ? `${esc(h.abbr)} ${last}%` : `${esc(a.abbr)} ${100 - last}%`;
    // The SVG stretches to the sheet width, so quarter labels are HTML (SVG text would distort).
    const qs = wp.quarters || [];
    const ticks = qs.map(([, i]) => `<line x1="${x(i)}" x2="${x(i)}" y1="0" y2="${H}" class="wq"/>`).join("");
    const labels = qs.map(([q, i]) => `<span class="wt" style="left:${(100 * i / (pts.length - 1)).toFixed(1)}%">${q > 4 ? "OT" : "Q" + q}</span>`).join("");
    return `<div class="wp"><div class="wplab">ESPN win probability · ${lead}</div>
      <div class="wbox"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="ESPN win probability, ${lead}">
        <line x1="0" x2="${W}" y1="${H / 2}" y2="${H / 2}" class="wmid"/>${ticks}
        <polyline points="${pts.map((v, i) => `${x(i)},${y(v)}`).join(" ")}" class="wline"/>
      </svg>${labels}</div><div class="wpaxis"><span>${esc(a.abbr)} ↓</span><span>${esc(h.abbr)} ↑</span></div></div>`;
  }
  function gameBody(g, d) {
    const a = g.away || {}, h = g.home || {};
    const nothing = `<div class="empty">Nothing yet.</div>`;
    const newestFirst = list => isLive(g) ? list.slice().reverse() : list;   // live: latest on top
    if (sheet.tab === "scoring") {
      const rows = newestFirst(d.scoring || []).map(p => `<div class="gplay">
        <div class="gq">Q${esc(p.period)} ${esc(p.clock)}<b>${esc(p.team)}</b></div>
        <div class="gtxt"><b>${esc(p.type)}</b> ${esc(p.text)}</div>
        <div class="gsc">${esc(a.abbr)} ${esc(p.away)} – ${esc(h.abbr)} ${esc(p.home)}</div></div>`).join("");
      return rows || nothing;
    }
    if (sheet.tab === "box") {
      if (!(d.box || []).length) return nothing;
      return `<table class="gbox"><thead><tr><th></th><th>${esc(a.abbr)}</th><th>${esc(h.abbr)}</th></tr></thead><tbody>
        ${d.box.map(r => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td>${esc(r[2])}</td></tr>`).join("")}</tbody></table>`;
    }
    if (sheet.tab === "leaders") {
      const col = (t, list) => `<div class="glead"><h3>${esc(t.name || t.abbr)}</h3>${(list || []).map(l =>
        `<div class="gl"><span>${esc(l.cat)}</span><b>${esc(l.name)}</b><div class="juice">${esc(l.line)}</div></div>`).join("") || nothing}</div>`;
      const L = d.leaders || {};
      return `<div class="gleads">${col(a, L.away)}${col(h, L.home)}</div>`;
    }
    const drives = newestFirst(d.drives || []);
    const cur = d.current && isLive(g) ? [Object.assign({ now: true }, d.current)] : [];
    const rows = [...cur, ...drives].map(r => `<div class="gdrive ${r.score ? "scored" : ""} ${r.now ? "now" : ""}">
      <div class="gq">Q${esc(r.period)}<b>${esc(r.team)}</b></div>
      <div class="gtxt"><b>${r.now ? "On the field" : esc(r.result)}</b> · from ${esc(r.start)}<div class="juice">${esc(r.desc)}</div></div></div>`).join("");
    return winprobSvg(d.winprob, a, h) + (rows || nothing);
  }
  function renderGame() {
    let el = $("gsheet");
    if (!el) {
      el = document.createElement("div");
      el.id = "gsheet"; el.className = "gsheet";
      document.body.appendChild(el);
      el.addEventListener("click", e => {
        if (e.target === el || e.target.closest("[data-gclose]")) { dismissGame(); return; }
        const t = e.target.closest("[data-gtab]");
        if (t && sheet) { sheet.tab = t.dataset.gtab; renderGame(); const b = el.querySelector(".gbody"); if (b) b.scrollTop = 0; return; }
        if (e.target.closest("[data-gretry]") && sheet) loadGame(sheet.id);
      });
    }
    if (!sheet) { el.hidden = true; return; }
    el.hidden = false;
    const g = games.find(x => x.id === sheet.id);
    const panel = body => `<div class="gpanel" role="dialog" aria-modal="true" aria-label="Game detail">
      <button class="gx" data-gclose aria-label="Close">×</button>${body}</div>`;
    if (!g) { el.innerHTML = panel(`<div class="empty">That game isn't on this week's board.</div>`); return; }
    const a = g.away || {}, h = g.home || {}, d = sheet.data;
    const ls = (d && d.linescores) || {};
    const n = Math.max((ls.away || []).length, (ls.home || []).length);
    const qs = Array.from({ length: n }, (_, i) => i < 4 ? `Q${i + 1}` : (n > 5 ? `${i - 3}OT` : "OT"));
    const line = n ? `<table class="glines"><thead><tr><th></th>${qs.map(q => `<th>${q}</th>`).join("")}<th>T</th></tr></thead><tbody>
      ${[[a, ls.away], [h, ls.home]].map(([t, s]) => `<tr><td>${esc(t.abbr)}</td>${qs.map((_, i) => `<td>${esc((s || [])[i] ?? "")}</td>`).join("")}<td><b>${esc(t.score || 0)}</b></td></tr>`).join("")}</tbody></table>` : "";
    const head = `<div class="ghead">
      <div class="gteams"><span>${rank(a)}${esc(a.name || a.abbr)} <b>${started(g) ? esc(a.score || 0) : ""}</b></span>
        <span>${rank(h)}${esc(h.name || h.abbr)} <b>${started(g) ? esc(h.score || 0) : ""}</b></span></div>
      <div class="gstat"><span class="livepill ${isFinal(g) ? "final" : isLive(g) ? "on" : ""}">${isFinal(g) ? "FINAL" : isLive(g) ? "LIVE" : "PRE"}</span>${isFinal(g) ? "" : esc(liveStatusText(g, isLive(g)) || fmtKick(g))}</div>${line}</div>`;
    if (!started(g)) { el.innerHTML = panel(head + `<div class="empty">Game detail opens at kickoff (${esc(fmtKick(g))}).</div>`); return; }
    const tabs = [["scoring", "Scoring"], ["box", "Box"], ["leaders", "Leaders"], ["drives", "Drives"]];
    const nav = `<div class="rowscroll gtabs">${tabs.map(([id, label]) => `<button class="fbtn ${sheet.tab === id ? "active" : ""}" data-gtab="${id}">${label}</button>`).join("")}</div>`;
    let body;
    if (d) body = gameBody(g, d);
    else if (sheet.error) body = `<div class="empty">Couldn't load game detail. <button class="abtn" data-gretry>Retry</button></div>`;
    else body = `<div class="empty">Loading…</div>`;
    const scroll = el.querySelector(".gbody"), top = scroll ? scroll.scrollTop : 0;
    el.innerHTML = panel(head + nav + `<div class="gbody">${body}</div>`);
    const fresh = el.querySelector(".gbody"); if (fresh && sheet.data) fresh.scrollTop = top;   // live refresh keeps place
  }
  document.addEventListener("keydown", e => { if (e.key === "Escape" && sheet) dismissGame(); });
  function toggleStar(id) {
    if (stars.has(id)) stars.delete(id); else stars.add(id);
    localStorage.setItem(STAR_KEY, JSON.stringify([...stars]));
    render();
  }
  function filtered() {
    let list = games.filter(g => {
      if (day!=="all" && slateDay(g)!==day) return false;
      if (win!=="all" && windowOf(g)!==win) return false;
      if (group==="P4/P5" && g.group!=="P4/P5") return false;
      if (group==="G5" && g.group!=="G5") return false;
      if (["SEC","Big Ten","ACC","Big 12"].includes(group)) {
        const confs=[g.home&&g.home.conference, g.away&&g.away.conference];
        if (!confs.includes(group)) return false;
      }
      if (confOnly && !isConfGame(g)) return false;
      if (ranked) {
        const hr=g.home&&g.home.rank&&g.home.rank<30;
        const ar=g.away&&g.away.rank&&g.away.rank<30;
        if (!hr && !ar) return false;
      }
      if (starredOnly && !stars.has(g.id)) return false;
      if (liveOnly && !isLive(g) && !isFinal(g)) return false;
      if (weatherOnly && !(g.flags&&g.flags.length) && g.impact_level==="CLEAR") return false;
      if (q) {
        const blob=[g.name,g.shortName,g.venue,g.city,g.state,...(g.networks||[]),g.home&&g.home.conference,g.away&&g.away.conference].join(" ").toLowerCase();
        if (!blob.includes(q.toLowerCase())) return false;
      }
      return true;
    });
    list = list.slice().sort((a,b)=>{
      if (isLive(a) !== isLive(b)) return isLive(a) ? -1 : 1;
      if (sort==="total") return ((b.odds&&b.odds.total)||0)-((a.odds&&a.odds.total)||0);
      if (sort==="spread") return (b.spread_abs||0)-(a.spread_abs||0);
      if (sort==="temp") return (b.temp||-99)-(a.temp||-99);
      if (sort==="wind") return ((b.wx&&b.wx.wind)||0)-((a.wx&&a.wx.wind)||0);
      if (sort==="rain") return ((b.wx&&b.wx.pop)||0)-((a.wx&&a.wx.pop)||0);
      return (a.date||"").localeCompare(b.date||"");
    });
    return list;
  }
  // Implied score is always prefixed "proj" so it cannot be read as points. Suppressed
  // once the game starts; the empty div stays because .trow is a four-column grid and
  // dropping it would misalign every started card against every pre-kick one.
  function implCell(v, hide) {
    if (v == null || hide) return `<div class="impl"></div>`;
    return `<div class="impl" title="Implied score from spread + total (ESPN/DK snapshot), not points"><span class="proj">proj</span>${v}</div>`;
  }
  function liveStatusText(g, live) {
    const st = g.statusDetail || g.statusShort || "";
    return (live && g.clock && !st.includes(g.clock)) ? `${st} · ${g.clock}` : st;
  }
  function card(g) {
    const a=g.away||{}, h=g.home||{}, o=g.odds||{}, wx=g.wx||{}, impl=g.implied||{};
    const tv=(g.networks||g.broadcasts||[]).join(" / ") || "TBD";
    const flags=(g.flags||[]).map(f=>`<span class="flag ${flagClass(f)}">${f}</span>`).join("");
    const spreadHome=(o.home_spread&&o.home_spread.line)?`${h.abbr||"HOME"} ${o.home_spread.line}`:(o.details||"—");
    const spreadJuice=o.home_spread&&o.home_spread.odds?o.home_spread.odds:"";
    const openSp=o.home_spread&&o.home_spread.open&&o.home_spread.open!==o.home_spread.line?`open ${o.home_spread.open}`:"";
    const wind=wx.wind!=null?`${Math.round(wx.wind)} mph ${g.wind_dir||""}`.trim():"—";
    const gust=wx.gusts!=null?` · gust ${Math.round(wx.gusts)}`:"";
    const venue=[g.venue,[g.city,g.state].filter(Boolean).join(", ")].filter(Boolean).join(" · ");
    const conf=[a.conference,h.conference].filter(Boolean).filter((v,i,arr)=>arr.indexOf(v)===i).join(" / ");
    const on=stars.has(g.id);
    const elev=g.elev_ft?` · ${g.elev_ft.toLocaleString()} ft`:"";
    const math=liveMath(g);
    const live = isLive(g);
    const done = isFinal(g);
    const showScore = live || done;
    const sit = g.situation || {};
    let liveRow = "";
    if (live || done) {
      const coverCls = math.coverState==="HOME COVER" ? "cover-home" : math.coverState==="AWAY COVER" ? "cover-away" : "cover-push";
      const totCls = math.totalState==="OVER" ? "cover-home" : math.totalState==="UNDER" ? "cover-away" : "cover-push";
      liveRow = `<div class="liverow">
        <div><span class="livepill ${done?"final":"on"}">${done?"FINAL":"LIVE"}</span> ${liveStatusText(g, live)}</div>
        <div class="livemath">
          ${math.coverState?`<span class="${coverCls}">${math.coverState}${math.coverBy!=null?` ${math.coverBy>0?"+":""}${math.coverBy}`:""}</span>`:""}
          ${math.total!=null?`<span class="${totCls}">${math.combined} / ${math.total} · need ${math.overNeed} for OVER</span>`:""}
        </div>
        ${sit.text || sit.lastPlay ? `<div class="sit">${sit.isRedZone?"🔴 RZ · ":""}${sit.text||""}${sit.lastPlay?" · "+sit.lastPlay:""}</div>`:""}
      </div>`;
    }
    return `<article class="card ${live?"is-live":""} ${done?"is-final":""}">
      <div class="meta">
        <span>${clockLabel(g)}${conf?" · "+conf:""}</span>
        <span><span class="tv">${tv}</span><button class="star ${on?"on":""}" data-star="${g.id}">${on?"★":"☆"}</button></span>
      </div>
      ${liveRow}
      <div class="teams">
        <div class="trow">
          <img src="${a.logo||""}" alt="" onerror="this.style.opacity=0" />
          <div class="name">${rank(a)}${a.name||"TBD"}<span class="rec">${a.record||""}</span></div>
          ${implCell(impl.away, live || done)}
          <div class="score">${showScore ? (a.score||"0") : ""}</div>
        </div>
        <div class="trow">
          <img src="${h.logo||""}" alt="" onerror="this.style.opacity=0" />
          <div class="name">${rank(h)}${h.name||"TBD"}<span class="rec">${h.record||""}</span></div>
          ${implCell(impl.home, live || done)}
          <div class="score">${showScore ? (h.score||"0") : ""}</div>
        </div>
      </div>
      <div class="venue"><b>${g.neutral?"Neutral · ":""}<a href="${mapsUrl(g)}" target="_blank" rel="noopener">${venue||"Venue TBD"}</a></b>${elev}${g.tickets?" · "+g.tickets:""}</div>
      ${(g.notes&&g.notes[0])?`<div class="venue">${g.notes[0]}</div>`:""}
      <div class="wx">
        <div class="cond"><span>${g.wx_emoji||""} ${g.wx_label||"Weather"}</span><b>${g.temp!=null?Math.round(g.temp)+"°":"—"}F</b></div>
        <div><div class="mini">Wind</div><div class="val">${wind}${gust}</div></div>
        <div><div class="mini">Rain</div><div class="val">${wx.pop!=null?wx.pop+"%":"—"}</div></div>
        <div><div class="mini">Humidity</div><div class="val">${wx.humidity!=null?wx.humidity+"%":"—"}</div></div>
        <div class="note">${(g.impact_notes||[]).join(" · ")}</div>
      </div>
      <div class="odds">
        <div class="od"><div class="lab">Spread</div><div class="big">${spreadHome}</div><div class="juice">${spreadJuice}${openSp?" · "+openSp:""}</div></div>
        <div class="od"><div class="lab">Total</div><div class="big">${o.total!=null?o.total:"—"}</div><div class="juice">${o.over&&o.over.odds?"o/u "+o.over.odds:""}</div></div>
        <div class="od"><div class="lab">Moneyline</div><div class="big">${h.abbr||"H"} ${juice(o.home_ml)}</div><div class="juice">${a.abbr||"A"} ${juice(o.away_ml)}</div></div>
      </div>
      <div class="actions">
        ${showScore ? `<a class="abtn" href="#game/${g.id}">Game</a>` : ""}
        <button class="abtn" data-copy="${g.id}">Copy post</button>
        <a class="abtn" href="${mapsUrl(g)}" target="_blank" rel="noopener">Maps</a>
        ${g.gamecast?`<a class="abtn" href="${g.gamecast}" target="_blank" rel="noopener">ESPN</a>`:`<span class="abtn">ESPN</span>`}
      </div>
      ${flags?`<div class="flags">${flags}</div>`:""}
    </article>`;
  }
  function linesSheet(list) {
    const showProj = list.some(g => !started(g));   // column goes once everything in view has kicked
    const cols = showProj ? 6 : 5;
    const rows = list.map(g=>{
      const a=g.away||{}, h=g.home||{}, o=g.odds||{}, impl=g.implied||{};
      const math=liveMath(g);
      const score = (isLive(g)||isFinal(g)) ? `${a.score||0}–${h.score||0}` : "";
      return `<tr>
        <td>${clockLabel(g)}<div class="juice">${(g.networks||[]).join("/")}</div></td>
        <td>${started(g)?`<a class="glink" href="#game/${g.id}">`:""}<b>${a.abbr||""}</b> ${g.neutral?"vs":"@"} <b>${h.abbr||""}</b> ${score}${started(g)?" ›</a>":""}<div class="juice">${[g.city,g.state].filter(Boolean).join(", ")}</div></td>
        <td>${o.details||"—"}<div class="juice">${math.coverState||""} ${math.coverBy!=null?math.coverBy:""}</div></td>
        <td>${o.total!=null?o.total:"—"}<div class="juice">${math.total!=null?`${math.combined} pts · ${math.overNeed} to over`:""}</div></td>
        ${showProj ? `<td>${(started(g) || impl.away==null) ? "—" : `${impl.away}–${impl.home}`}</td>` : ""}
        <td>${g.temp!=null?Math.round(g.temp)+"°":"—"} ${g.wx_emoji||""}<div class="juice">${(g.flags||[]).join(" · ")}</div></td>
      </tr>`;
    }).join("");
    return `<div class="section"><h2>Lines sheet · ${list.length}</h2>
      <div style="overflow-x:auto"><table>
        <thead><tr><th>Kick CT</th><th>Game</th><th>Spread</th><th>Total</th>${showProj?"<th>Proj</th>":""}<th>Wx</th></tr></thead>
        <tbody>${rows||`<tr><td colspan="${cols}">No games</td></tr>`}</tbody>
      </table></div>
      <div class="actions" style="padding:12px 0 0"><button class="abtn" id="csv">Download CSV</button></div>
    </div>`;
  }
  function tvBoard(list) {
    const map = {};
    list.forEach(g => {
      const nets = (g.networks&&g.networks.length)?g.networks:["Unlisted"];
      nets.forEach(n => { (map[n]=map[n]||[]).push(g); });
    });
    const order = ["ABC","NBC","CBS","FOX","ESPN","ESPNU","FS1","BTN","SEC Network","SECN+","ACC Network","ACCNX","CBSSN","TNT","CW","USA Net","ESPN+","Disney+","MW+","UConn+","ERADM","Unlisted"];
    const keys = [...new Set([...order.filter(k=>map[k]), ...Object.keys(map)])];
    return `<div class="section"><h2>By network</h2>${keys.map(n=>`
      <div class="netblock"><div class="t">${n} · ${map[n].length}</div>
        ${map[n].map(g=>`<div class="netgame"><b>${g.shortName}</b><span>${fmtKick(g)} · ${[g.city,g.state].filter(Boolean).join(", ")} · ${g.odds&&g.odds.details?g.odds.details:""} · ${g.odds&&g.odds.total!=null?"o/u "+g.odds.total:""}</span></div>`).join("")}
      </div>`).join("")}</div>`;
  }
  function blowoutBoard(list) {
    const big = list.filter(g=>g.blowout).sort((a,b)=>(b.spread_abs||0)-(a.spread_abs||0));
    return `<div class="section"><h2>Landslide board · spread 28+</h2>
      ${big.length?big.map(g=>{
        const o=g.odds||{}, impl=g.implied||{}, a=g.away||{}, h=g.home||{};
        const bits = [fmtKick(g), (g.networks||[]).join("/")];
        if (started(g)) bits.push(`${a.score||0}–${h.score||0} ${isFinal(g)?"FINAL":"LIVE"}`);
        else if (impl.away != null) bits.push(`proj ${impl.away}–${impl.home}`);
        bits.push(`total ${o.total??"—"}`);
        if (g.temp != null) bits.push(`${Math.round(g.temp)}°`);
        bits.push(`${g.city}, ${g.state}`);
        const tag = started(g) ? `a href="#game/${g.id}"` : "div";
        return `<${tag} class="deskcard"><div class="t">${g.shortName} · ${o.details||""}</div>
          <div class="d">${bits.filter(Boolean).join(" · ")}</div></${tag.split(" ")[0]}>`;
      }).join(""):`<div class="empty">No 28-point spreads in this filter.</div>`}
    </div>`;
  }
  function deskHtml(list) {
    // under_score is the directional part of the weather (wind/rain/cold). Heat scores
    // impact_score but not this, so hot games stay out of the desk and in the heat list
    // below. Fallback keeps a service-worker-cached snapshot rendering.
    const unders = list.filter(g => g.under_score != null
      ? g.under_score > 0
      : (g.impact_level==="UNDER" || g.impact_level==="WATCH"));
    const heat = list.filter(g => (g.flags||[]).some(f=>f.includes("HEAT")||f==="HOT")).sort((a,b)=>(b.temp||0)-(a.temp||0)).slice(0,5);
    const alt = list.filter(g => (g.flags||[]).includes("ALTITUDE"));
    const indoor = list.filter(g=>g.indoor);
    const liveGames = list.filter(isLive);
    let html = "";
    if (liveGames.length) {
      html += `<h2>Live desk · ${liveGames.length}</h2><div class="desk-grid">`;
      liveGames.forEach(g => {
        const math = liveMath(g);
        const sit = g.situation || {};
        html += `<a class="deskcard" href="#game/${g.id}"><div class="t"><span class="tag heat">LIVE</span>${g.shortName} ${g.away&&g.away.score||0}–${g.home&&g.home.score||0} ›</div>
          <div class="d">${liveStatusText(g, true)} · ${math.coverState||""} ${math.coverBy!=null?math.coverBy:""} · ${math.combined}/${math.total??"—"} total · ${sit.text||sit.lastPlay||""}</div></a>`;
      });
      html += `</div>`;
    }
    if (!unders.length && !heat.length && !alt.length && !liveGames.length) return html;
    html += `<h2>Weather / travel desk</h2><div class="desk-grid">`;
    unders.forEach(g => {
      html += `<div class="deskcard"><div class="t"><span class="tag ${g.impact_level==="UNDER"?"under":"watch"}">${g.impact_level}</span>${g.shortName}</div><div class="d">${(g.impact_notes||[]).join(" · ")} · total ${g.odds&&g.odds.total!=null?g.odds.total:"n/a"}</div></div>`;
    });
    heat.forEach(g => {
      html += `<div class="deskcard"><div class="t"><span class="tag heat">HEAT ${Math.round(g.temp)}°</span>${g.shortName}</div><div class="d">${g.city}, ${g.state} · ${fmtKick(g)}</div></div>`;
    });
    alt.forEach(g => {
      html += `<div class="deskcard"><div class="t"><span class="tag alt">${g.elev_ft.toLocaleString()} ft</span>${g.shortName}</div><div class="d">${g.city}, ${g.state} · ${fmtKick(g)}</div></div>`;
    });
    html += `</div>`;
    if (indoor.length) html += `<div class="d" style="color:var(--muted);font-size:12px;margin-top:6px">${indoor.length} indoor site${indoor.length>1?"s":""} on this slate.</div>`;
    return html;
  }
  function downloadCsv(list) {
    const headers = ["kick_ct","away","home","venue","city","state","tv","spread","total","proj_away","proj_home","temp","wind","rain","flags","notes"];
    const rows = list.map(g=>{
      const a=g.away||{}, h=g.home||{}, o=g.odds||{}, wx=g.wx||{}, impl=g.implied||{};
      const pa = started(g) ? "" : impl.away, ph = started(g) ? "" : impl.home;
      return [fmtKick(g), a.name, h.name, g.venue, g.city, g.state, (g.networks||[]).join("|"), o.details, o.total, pa, ph, g.temp, wx.wind, wx.pop, (g.flags||[]).join("|"), (g.impact_notes||[]).join("; ")].map(v => `"${String(v??"").replaceAll('"','""')}"`).join(",");
    });
    const blob = new Blob([[headers.join(","),...rows].join("\n")], {type:"text/csv"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href=url; a.download=`cfb-gameday-${(DATA.week_label||"slate").toLowerCase().replace(/[^a-z0-9]+/g,"-")}.csv`; a.click();
    URL.revokeObjectURL(url);
  }
  function render() {
    const list = filtered();
    $("desk").innerHTML = deskHtml(list);
    let html = "";
    if (view==="lines") html = linesSheet(list);
    else if (view==="tv") html = tvBoard(list);
    else if (view==="blowouts") html = blowoutBoard(list);
    else html = `<div class="list cards">${list.map(card).join("")||`<div class="empty">No games match those filters.${activeFilters()||q?`<br /><button class="fbtn" data-reset>Reset filters</button>`:""}</div>`}</div>`;
    $("main").innerHTML = html;
    const heat = games.filter(g => (g.flags||[]).some(f=>f.includes("HEAT")||f==="HOT")).length;
    const liveCount = games.filter(isLive).length;
    $("stats").innerHTML = `
      <div class="stat"><b>${list.length}</b><span>Showing</span></div>
      <div class="stat"><b>${liveCount}</b><span>Live now</span></div>
      <div class="stat"><b>${list.filter(g=>g.blowout).length}</b><span>28+ spreads</span></div>
      <div class="stat"><b>${stars.size}</b><span>Starred</span></div>`;
    const when = liveStatus.last ? liveStatus.last.toLocaleTimeString([], {hour:"numeric", minute:"2-digit", second:"2-digit"}) : (DATA.generated_at||"");
    const mode = liveStatus.fromFile ? "FILE MODE — run server.py for live scores" : liveStatus.ok ? `LIVE ${when}` : (liveStatus.error ? `LIVE ERR ${liveStatus.error}` : `Snapshot ${when}`);
    $("updated").textContent = `${mode} · times in CT`;
    const csv = document.getElementById("csv");
    if (csv) csv.onclick = () => downloadCsv(list);
  }
  function pills() {
    $("days").innerHTML = days.map(d=>`<button class="fbtn ${d.id===day?"active":""}" data-day="${d.id}">${d.label}</button>`).join("");
    $("views").innerHTML = views.map(v=>`<button class="fbtn ${v.id===view?"active":""}" data-view="${v.id}">${v.label}</button>`).join("");
    $("windows").innerHTML = windows.map(w=>`<button class="fbtn ${w.id===win?"active":""}" data-win="${w.id}">${w.label}</button>`).join("");
    $("toggles").innerHTML = `
      <button class="fbtn ${group==="all"?"active":""}" data-group="all">All conf</button>
      <button class="fbtn ${group==="P4/P5"?"active":""}" data-group="P4/P5">P4</button>
      <button class="fbtn ${group==="G5"?"active":""}" data-group="G5">G5</button>
      <button class="fbtn ${group==="SEC"?"active":""}" data-group="SEC">SEC</button>
      <button class="fbtn ${group==="Big Ten"?"active":""}" data-group="Big Ten">Big Ten</button>
      <button class="fbtn ${group==="ACC"?"active":""}" data-group="ACC">ACC</button>
      <button class="fbtn ${group==="Big 12"?"active":""}" data-group="Big 12">Big 12</button>
      <button class="fbtn ${confOnly?"active":""}" id="confonly">Conf game</button>
      <button class="fbtn ${ranked?"active":""}" id="ranked">Ranked</button>
      <button class="fbtn ${starredOnly?"active":""}" id="starred">Starred</button>
      <button class="fbtn ${liveOnly?"active":""}" id="liveonly">Live</button>
      <button class="fbtn" id="refresh">Refresh</button>
      <button class="fbtn ${weatherOnly?"active":""}" id="wxonly">Weather</button>
      <select id="sort">
        <option value="time"${sort==="time"?" selected":""}>Sort: time</option>
        <option value="total"${sort==="total"?" selected":""}>Sort: total</option>
        <option value="spread"${sort==="spread"?" selected":""}>Sort: spread</option>
        <option value="temp"${sort==="temp"?" selected":""}>Sort: heat</option>
        <option value="wind"${sort==="wind"?" selected":""}>Sort: wind</option>
        <option value="rain"${sort==="rain"?" selected":""}>Sort: rain</option>
      </select>
      ${activeFilters()?`<button class="fbtn" data-reset>Reset</button>`:""}`;
    const n = activeFilters(), ft = $("ftoggle");
    ft.classList.toggle("active", n > 0);
    ft.classList.toggle("open", filtersOpen);
    ft.setAttribute("aria-expanded", String(filtersOpen));
    ft.innerHTML = `Filters${n ? ` <span class="fcount">${n}</span>` : ""}`;
    $("filters").hidden = !filtersOpen;
    $("days").onclick = e => { const b=e.target.closest("[data-day]"); if(!b)return; day=b.dataset.day; pills(); render(); };
    $("views").onclick = e => { const b=e.target.closest("[data-view]"); if(!b)return; view=b.dataset.view; pills(); render(); };
    $("windows").onclick = e => { const b=e.target.closest("[data-win]"); if(!b)return; win=b.dataset.win; pills(); render(); };
    $("toggles").onclick = e => {
      const g=e.target.closest("[data-group]"); if(g){ group=g.dataset.group; pills(); render(); }
    };
    $("confonly").onclick = () => { confOnly=!confOnly; pills(); render(); };
    $("ranked").onclick = () => { ranked=!ranked; pills(); render(); };
    $("starred").onclick = () => { starredOnly=!starredOnly; pills(); render(); };
    $("liveonly").onclick = () => { liveOnly=!liveOnly; pills(); render(); };
    $("refresh").onclick = () => { pollLive(); };
    $("wxonly").onclick = () => { weatherOnly=!weatherOnly; pills(); render(); };
    $("sort").onchange = e => { sort=e.target.value; render(); };
  }
  $("q").addEventListener("input", e => { q=e.target.value; render(); });
  $("ftoggle").onclick = () => {
    filtersOpen = !filtersOpen;
    try { localStorage.setItem(FILTERS_KEY, filtersOpen ? "1" : "0"); } catch (e) {}
    pills();
  };
  document.addEventListener("click", e => {
    if (e.target.closest("[data-reset]")) { resetFilters(); return; }
    const s=e.target.closest("[data-star]"); if(s){ toggleStar(s.dataset.star); return; }
    const c=e.target.closest("[data-copy]"); if(c){ const g=games.find(x=>x.id===c.dataset.copy); if(g) copyText(blurb(g), c); }
  });
  if (DATA.week_label && $("kicker")) $("kicker").textContent = DATA.week_label;
  // PWA: UI shell cached by sw.js; live data is never served from cache.
  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  const A2HS_KEY = "cfb_gameday_a2hs_dismissed";
  const iosSafari = /iphone|ipad|ipod/i.test(navigator.userAgent) && /safari/i.test(navigator.userAgent) && !/crios|fxios/i.test(navigator.userAgent);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  if (iosSafari && !standalone && !window.cfbNative && !localStorage.getItem(A2HS_KEY) && $("a2hs")) {
    $("a2hs").hidden = false;
    $("a2hs-x").onclick = () => { localStorage.setItem(A2HS_KEY, "1"); $("a2hs").hidden = true; };
  }
  function applyHash(e) {
    const gid = gameHash(location.hash);
    // e: reached by navigation, so Back closes it. Back to the hash it was opened from
    // only closes the sheet; re-applying filters would scroll the board to the top.
    if (gid) { openGame(gid, !!e, e && e.oldURL ? new URL(e.oldURL).hash : ""); return; }
    if (sheet) { const back = location.hash === sheet.prevHash; closeGame(); if (back) return; }
    const f = hashFilters(location.hash);
    if (!f.known) return;
    liveOnly = f.liveOnly; starredOnly = f.starredOnly; view = f.view;
    pills(); render();
    if (f.view !== "cards") { const m = $("main"); if (m) m.scrollIntoView({ block: "start" }); }
    else window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", applyHash);
  applyHash();
  pills(); render();
  pollLive();
  setInterval(pollLive, 30000);
})();
