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
  let day = slateDays.includes(todayCT) ? todayCT : (busiestDay || "all"), win="all", view="cards", ranked=false, starredOnly=false, weatherOnly=false, liveOnly=false, group="all", q="", sort="time";
  let liveStatus = { ok:false, fromFile: location.protocol === "file:", last:null, error:null };

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
  // ESPN dates (Eastern calendar) that still have a game not yet final.
  function liveDatesFor(list, dates) {
    const byDate = {};
    list.forEach(g => {
      const d = kickDate(g); if (!d) return;
      const key = etDateFmt.format(d).replace(/-/g, "");
      (byDate[key] = byDate[key] || []).push(g);
    });
    const known = (dates && dates.length) ? dates.map(String) : Object.keys(byDate).sort();
    return known.filter(k => !byDate[k] || byDate[k].some(g => !isFinal(g)));
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
      [o.details, o.total!=null?`o/u ${o.total}`:"", impl.home!=null?`proj ${a.abbr} ${impl.away} – ${h.abbr} ${impl.home}`:""].filter(Boolean).join(" · "),
      (g.impact_notes||[])[0]||""
    ].filter(Boolean).join("\n");
  }
  async function copyText(text, btn) {
    try { await navigator.clipboard.writeText(text); if (btn) { const old=btn.textContent; btn.textContent="Copied"; setTimeout(()=>btn.textContent=old,1200);} }
    catch(e) { alert(text); }
  }
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
  // Implied score is always prefixed "proj" so it cannot be read as points; dimmed once the game starts.
  function implCell(v, started) {
    if (v == null) return `<div class="impl"></div>`;
    return `<div class="impl ${started?"started":""}" title="Implied score from spread + total (ESPN/DK snapshot), not points"><span class="proj">proj</span>${v}</div>`;
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
        <button class="abtn" data-copy="${g.id}">Copy post</button>
        <a class="abtn" href="${mapsUrl(g)}" target="_blank" rel="noopener">Maps</a>
        ${g.gamecast?`<a class="abtn" href="${g.gamecast}" target="_blank" rel="noopener">ESPN</a>`:`<span class="abtn">ESPN</span>`}
      </div>
      ${flags?`<div class="flags">${flags}</div>`:""}
    </article>`;
  }
  function linesSheet(list) {
    const rows = list.map(g=>{
      const a=g.away||{}, h=g.home||{}, o=g.odds||{}, impl=g.implied||{};
      const math=liveMath(g);
      const score = (isLive(g)||isFinal(g)) ? `${a.score||0}–${h.score||0}` : "";
      return `<tr>
        <td>${clockLabel(g)}<div class="juice">${(g.networks||[]).join("/")}</div></td>
        <td><b>${a.abbr||""}</b> ${g.neutral?"vs":"@"} <b>${h.abbr||""}</b> ${score}<div class="juice">${[g.city,g.state].filter(Boolean).join(", ")}</div></td>
        <td>${o.details||"—"}<div class="juice">${math.coverState||""} ${math.coverBy!=null?math.coverBy:""}</div></td>
        <td>${o.total!=null?o.total:"—"}<div class="juice">${math.total!=null?`${math.combined} pts · ${math.overNeed} to over`:""}</div></td>
        <td>${impl.away!=null?`${impl.away}–${impl.home}`:"—"}</td>
        <td>${g.temp!=null?Math.round(g.temp)+"°":"—"} ${g.wx_emoji||""}<div class="juice">${(g.flags||[]).join(" · ")}</div></td>
      </tr>`;
    }).join("");
    return `<div class="section"><h2>Lines sheet · ${list.length}</h2>
      <div style="overflow-x:auto"><table>
        <thead><tr><th>Kick CT</th><th>Game</th><th>Spread</th><th>Total</th><th>Proj</th><th>Wx</th></tr></thead>
        <tbody>${rows||`<tr><td colspan="6">No games</td></tr>`}</tbody>
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
        const o=g.odds||{}, impl=g.implied||{};
        return `<div class="deskcard"><div class="t">${g.shortName} · ${o.details||""}</div>
          <div class="d">${fmtKick(g)} · ${(g.networks||[]).join("/")} · proj ${impl.away}–${impl.home} · total ${o.total??"—"} · ${g.temp!=null?Math.round(g.temp)+"°":""} ${g.city}, ${g.state}</div></div>`;
      }).join(""):`<div class="empty">No 28-point spreads in this filter.</div>`}
    </div>`;
  }
  function deskHtml(list) {
    const unders = list.filter(g => g.impact_level==="UNDER" || g.impact_level==="WATCH");
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
        html += `<div class="deskcard"><div class="t"><span class="tag heat">LIVE</span>${g.shortName} ${g.away&&g.away.score||0}–${g.home&&g.home.score||0}</div>
          <div class="d">${liveStatusText(g, true)} · ${math.coverState||""} ${math.coverBy!=null?math.coverBy:""} · ${math.combined}/${math.total??"—"} total · ${sit.text||sit.lastPlay||""}</div></div>`;
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
      return [fmtKick(g), a.name, h.name, g.venue, g.city, g.state, (g.networks||[]).join("|"), o.details, o.total, impl.away, impl.home, g.temp, wx.wind, wx.pop, (g.flags||[]).join("|"), (g.impact_notes||[]).join("; ")].map(v => `"${String(v??"").replaceAll('"','""')}"`).join(",");
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
    else html = `<div class="list cards">${list.map(card).join("")||`<div class="empty">No games match those filters.</div>`}</div>`;
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
      </select>`;
    $("days").onclick = e => { const b=e.target.closest("[data-day]"); if(!b)return; day=b.dataset.day; pills(); render(); };
    $("views").onclick = e => { const b=e.target.closest("[data-view]"); if(!b)return; view=b.dataset.view; pills(); render(); };
    $("windows").onclick = e => { const b=e.target.closest("[data-win]"); if(!b)return; win=b.dataset.win; pills(); render(); };
    $("toggles").onclick = e => {
      const g=e.target.closest("[data-group]"); if(g){ group=g.dataset.group; pills(); render(); }
    };
    $("ranked").onclick = () => { ranked=!ranked; pills(); render(); };
    $("starred").onclick = () => { starredOnly=!starredOnly; pills(); render(); };
    $("liveonly").onclick = () => { liveOnly=!liveOnly; pills(); render(); };
    $("refresh").onclick = () => { pollLive(); };
    $("wxonly").onclick = () => { weatherOnly=!weatherOnly; pills(); render(); };
    $("sort").onchange = e => { sort=e.target.value; render(); };
  }
  $("q").addEventListener("input", e => { q=e.target.value; render(); });
  document.addEventListener("click", e => {
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
  function applyHash() {
    const f = hashFilters(location.hash);
    if (!f.known) return;
    liveOnly = f.liveOnly; starredOnly = f.starredOnly; view = f.view;
    pills(); render();
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", applyHash);
  applyHash();
  pills(); render();
  pollLive();
  setInterval(pollLive, 30000);
})();
