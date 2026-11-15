"""Board client checks: syntax, nflWindowOf and desk helpers (extracted into node), escaping, static copy, a render smoke test."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NFL = ROOT / "nfl"
NODE = shutil.which("node")

FOOTER = ("Independent and unofficial. Not affiliated with, endorsed or sponsored by the National Football League or any team. "
          "Team names are used only to identify teams. Scores and play data via ESPN. Season metrics from nflverse (CC BY 4.0). "
          "Weather by Open-Meteo.com (CC BY 4.0).")


def _src(name: str) -> str:
    return (NFL / name).read_text("utf-8")


def _extract(src: str, funcs: tuple[str, ...], consts: tuple[str, ...] = ()) -> str:
    out = []
    for name in consts:
        m = re.search(rf"\n  const {name} = [^\n]*\n", src)
        if not m:
            raise AssertionError(f"could not extract const {name}")
        out.append(m.group(0))
    for name in funcs:
        m = re.search(rf"\n  function {name}\(.*?\n  }}\n", src, re.S)
        if not m:
            raise AssertionError(f"could not extract {name}")
        out.append(m.group(0))
    return "\n".join(out)


def _node(script: str) -> object:
    p = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise AssertionError("node failed: " + (p.stderr or p.stdout)[:600])
    return json.loads(p.stdout.strip().splitlines()[-1])


def _g(date, **kw):
    return {"date": date, "time_tbd": False, "kind": "regular", "neutral": False, "venue": {"country": "US"}, **kw}


# ---------- syntax and static copy ----------

def test_syntax(check):
    files = sorted(NFL.glob("*.js"))
    check.true("nfl/app.js exists", (NFL / "app.js").exists())
    if not NODE:
        print("node not found; skipping client syntax checks")
        return
    for f in files:
        p = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True)
        check(f"node --check {f.name}", p.returncode, 0)


def test_static(check):
    html = _src("index.html")
    check.true("indexable since launch", 'name="robots"' not in html)
    check.true("canonical", '<link rel="canonical" href="https://cfbgameday.app/nfl" />' in html)
    check.true("own icons, not the college board's", 'href="/nfl/icons/icon-192.png"' in html and '"/icons/icon-192.png"' not in html)
    check.true("title", "<title>Pro Football Board</title>" in html)
    check.true("links /site.css read-only", 'href="/site.css"' in html)
    for asset in ("/nfl/nfl.css", "/nfl/sheet.css", "/nfl/sheet.js", "/nfl/app.js"):
        check.true(f"absolute asset {asset}", asset in html)
    app = _src("app.js")
    check.true("registers /nfl/sw.js with scope /nfl/", 'register("/nfl/sw.js", { scope: "/nfl/" })' in app)
    check.true("sw registration guarded", '"serviceWorker" in navigator' in app and 'location.protocol === "file:"' in app)
    check.true("sw not registered from the html", "serviceWorker" not in html)
    m = re.search(r"<footer>(.*?)</footer>", html, re.S)
    check.true("footer present", m is not None)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1).split("<br")[0])).strip() if m else ""
    check("footer verbatim", text, FOOTER)
    for name, host in (("nflverse", "nflverse.com"), ("Open-Meteo", "open-meteo.com")):
        check.true(f"footer links {name}", re.search(rf'<a href="https://[^"]*{re.escape(host)}[^"]*"[^>]*>{name}', html) is not None)


def test_no_external_art(check):
    for name in ("index.html", "app.js", "nfl.css"):
        src = _src(name)
        check.true(f"{name}: no img tags", "<img" not in src.lower())
        check.true(f"{name}: no css url()", "url(" not in src)
        urls = re.findall(r"https?://[^\s\"'<>)]+", src)
        bad = [u for u in urls if not re.match(r"https://(www\.nflverse\.com|open-meteo\.com|cfbgameday\.app)/", u)]
        check(f"{name}: external urls", bad, [])
        check.true(f"{name}: no logo or headshot paths", re.search(r"(logo|headshot|espncdn)", src, re.I) is None)
    keys = set(re.findall(r'localStorage\.\w+\(\s*([A-Z_]+|"[^"]+")', _src("app.js")))
    consts = dict(re.findall(r'const ([A-Z_]+) = "([^"]+)"', _src("app.js")))
    names = {consts.get(k, k.strip('"')) for k in keys}
    check.true("localStorage keys use nflb_", names and all(n.startswith("nflb_") for n in names), str(names))


# ---------- escaping ----------

def _template_exprs(src: str):
    """Every ${...} expression inside backtick templates, nested templates included. Skips strings and comments."""
    out: list[str] = []
    n = len(src)

    def skip_string(i: int, q: str) -> int:
        i += 1
        while i < n and src[i] != q:
            i += 2 if src[i] == "\\" else 1
        return i + 1

    def template(i: int) -> int:  # i is just past the opening backtick
        while i < n:
            c = src[i]
            if c == "\\":
                i += 2
            elif c == "`":
                return i + 1
            elif src.startswith("${", i):
                i = expr(i + 2)
            else:
                i += 1
        return i

    def expr(i: int) -> int:  # i is just past "${"; returns the index after the closing brace
        start, depth = i, 1
        while i < n:
            c = src[i]
            if c in "\"'":
                i = skip_string(i, c)
                continue
            if c == "`":
                i = template(i + 1)
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    out.append(src[start:i])
                    return i + 1
            i += 1
        return i

    i = 0
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            i = src.find("\n", i)
            i = n if i < 0 else i
        elif src.startswith("/*", i):
            i = src.find("*/", i) + 2
        elif c in "\"'":
            i = skip_string(i, c)
        elif c == "`":
            i = template(i + 1)
        else:
            i += 1
    return out


def _single_call(e: str, prefix: re.Pattern) -> bool:
    m = prefix.match(e)
    if not m:
        return False
    depth = 0
    for i in range(m.end() - 1, len(e)):
        depth += e[i] == "("
        depth -= e[i] == ")"
        if depth == 0:
            return i == len(e) - 1
    return False


_ESC = re.compile(r"esc\(")
_HELPER = re.compile(r"h[A-Z]\w*\(")
_NUMBER = re.compile(r"Number\(")


def _interp_ok(e: str) -> bool:
    e = e.strip()
    if _single_call(e, _ESC) or _single_call(e, _HELPER) or _single_call(e, _NUMBER):
        return True
    if re.fullmatch(r"\w+(Html|Cls|Pct|Num)", e):
        return True
    if re.fullmatch(r"[^`]+\?\s*\"[^\"`]*\"\s*:\s*\"[^\"`]*\"", e):   # literal-only ternary
        return True
    if re.search(r"\.map\(", e) and e.endswith('.join("")') and ("`" in e or _HELPER.search(e)):   # nested templates are checked on their own
        return True
    if re.fullmatch(r"[^?`]+\?\s*`.*`\s*:\s*\"\"", e, re.S):   # cond ? `markup` : ""
        return True
    return False


def test_escaping(check):
    src = _src("app.js")
    exprs = _template_exprs(src)
    check.true("templates found", len(exprs) > 40, str(len(exprs)))
    bad = [e.strip()[:70] for e in exprs if not _interp_ok(e)]
    check("unescaped interpolations", bad, [])
    check.true("esc defined", "function esc(" in src)
    check.true("no document.write or eval", not re.search(r"document\.write|\beval\(|new Function", src))
    check.true("only controlled innerHTML", len(re.findall(r"\.innerHTML\s*=", src)) <= 8)
    # the scanner itself must flag a raw interpolation
    check.true("scanner flags raw", not _interp_ok("g.away.name"))
    check.true("scanner accepts esc", _interp_ok("esc(g.away.name)"))
    check.true("scanner rejects esc(a)+b", not _interp_ok("esc(a) + b"))


# ---------- extracted pure functions ----------

def test_window_of(check):
    if not NODE:
        return
    src = _src("app.js")
    fns = _extract(src, ("ctParts", "abroad", "nflWindowOf"), ("CT", "CT_PARTS"))
    cases = [
        # fixture dates (2026): [label, game, want]
        ("TNF W11", _g("2026-11-20T01:15Z"), "tnf"),
        ("Wed night GB@LAR W12", _g("2026-11-26T01:00Z"), "wed"),
        ("Thanksgiving noon", _g("2026-11-26T18:00Z"), "thanks"),
        ("Thanksgiving late", _g("2026-11-27T01:20Z"), "thanks"),
        ("Black Friday", _g("2026-11-27T20:00Z"), "blackfri"),
        ("Sun early noon CT", _g("2026-11-29T18:00Z"), "sunE"),
        ("Sun late 3:05", _g("2026-11-29T21:05Z"), "sunL"),
        ("SNF", _g("2026-11-30T01:20Z"), "snf"),
        ("MNF", _g("2026-12-01T01:15Z"), "mnf"),
        ("Christmas eve game (Thu CT)", _g("2026-12-25T01:15Z"), "xmas"),
        ("Christmas day noon (Fri)", _g("2026-12-25T18:00Z"), "xmas"),
        ("Christmas night (Fri CT)", _g("2026-12-26T01:15Z"), "xmas"),
        ("Sat Dec 19", _g("2026-12-19T18:00Z"), "sat"),
        ("Sat Dec 26 not xmas", _g("2026-12-26T18:00Z"), "sat"),
        ("flex TBD", _g("2026-12-27T05:00Z", time_tbd=True), "flex"),
        ("flex TBD W18", _g("2027-01-10T05:00Z", time_tbd=True), "flex"),
        ("Int'l AM Munich 14:30Z", _g("2026-11-08T14:30Z", neutral=True, venue={"country": "DE"}), "intl"),
        ("Int'l AM neutral, venue unknown", {"date": "2025-09-28T13:30Z", "neutral": True, "kind": "regular"}, "intl"),
        ("Sun 11:00 CT abroad is early", _g("2026-11-08T17:00Z", venue={"country": "GB"}), "sunE"),
        ("US 8:30 CT is early", _g("2026-11-08T14:30Z"), "sunE"),
        ("Mexico City Sun night", _g("2026-11-23T01:20Z", neutral=True, venue={"country": "MX"}), "snf"),
        ("CDT noon", _g("2026-09-13T17:00Z"), "sunE"),
        ("CDT 12:29", _g("2026-09-13T17:29Z"), "sunE"),
        ("CDT 12:30", _g("2026-09-13T17:30Z"), "sunL"),
        ("CST 12:30", _g("2026-11-29T18:30Z"), "sunL"),
        ("CST 5:59 pm", _g("2026-11-29T23:59Z"), "sunL"),
        ("CST 6:00 pm", _g("2026-11-30T00:00Z"), "snf"),
        ("Brazil Friday", _g("2025-09-06T00:00Z", neutral=True, venue={"country": "BR"}), "fri"),
        ("Tuesday", _g("2026-11-24T18:00Z"), "other"),
        ("Wild Card", _g("2027-01-16T05:00Z", kind="playoff", round="Wild Card", time_tbd=True), "post:Wild Card"),
        ("playoff without round", _g("2027-01-23T21:00Z", kind="playoff"), "post:Playoffs"),
        ("Pro Bowl", _g("2027-02-01T01:00Z", kind="all_star"), "probowl"),
        ("bad date", _g("nonsense"), "flex"),
    ]
    script = fns + f"""
const cases = {json.dumps([c[1] for c in cases])};
console.log(JSON.stringify(cases.map(nflWindowOf)));
"""
    got = _node(script)
    for (label, _, want), g in zip(cases, got):
        check(f"window {label}", g, want)


def test_desk_helpers(check):
    if not NODE:
        return
    src = _src("app.js")
    fns = _extract(src, ("defaultWindow", "pollDelay", "swingOf", "effScore", "deskOrder", "hex6", "lum", "contrast", "chipColors"),
                   ("CARD_BG", "SWING_WINDOW_MS", "HYSTERESIS"))
    now = 1_800_000_000_000
    iso = lambda dt: __import__("datetime").datetime.fromtimestamp((now + dt) / 1000, __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases = {
        "defaultLive": [[{"win": "snf", "state": "in"}, {"win": "tnf", "state": "post"}, {"win": "sunE", "state": "post"}], ["tnf", "sunE", "snf"]],
        "defaultNext": [[{"win": "tnf", "state": "post"}, {"win": "sunE", "state": "pre"}, {"win": "snf", "state": "pre"}], ["tnf", "sunE", "snf"]],
        "defaultAllFinal": [[{"win": "tnf", "state": "post"}, {"win": "mnf", "state": "post"}], ["tnf", "mnf"]],
        "defaultEmpty": [[], []],
        "delayLive": [[{"state": "in", "date": iso(-5_000_000)}]],
        "delaySoon": [[{"state": "pre", "date": iso(50 * 60_000)}]],
        "delayFar": [[{"state": "pre", "date": iso(61 * 60_000)}]],
        "delayTbd": [[{"state": "pre", "date": iso(10 * 60_000), "time_tbd": True}]],
        "delayStalePre": [[{"state": "pre", "date": iso(-5 * 3_600_000)}]],
        "delayAllFinal": [[{"state": "post", "date": iso(-3_600_000)}]],
    }
    script = fns + f"""
const now = {now};
const C = {json.dumps(cases)};
const out = {{}};
out.defaultLive = defaultWindow(...C.defaultLive);
out.defaultNext = defaultWindow(...C.defaultNext);
out.defaultAllFinal = defaultWindow(...C.defaultAllFinal);
out.defaultEmpty = defaultWindow(...C.defaultEmpty);
for (const k of ["delayLive", "delaySoon", "delayFar", "delayTbd", "delayStalePre", "delayAllFinal"]) out[k] = pollDelay(C[k][0], now);
const s = (a) => a.map(([dt, wp]) => ({{ t: now + dt, wp }}));
out.swingUp = swingOf(s([[-170000, 0.5], [-60000, 0.55], [0, 0.62]]), now + 0);
out.swingDown = swingOf(s([[-100000, 0.7], [0, 0.55]]), now);
out.swingOld = swingOf(s([[-200000, 0.2], [0, 0.9]]), now);
out.swingOne = swingOf(s([[0, 0.5]]), now);
out.swingEmpty = swingOf(undefined, now);
out.eff = [effScore(60, 3.4), effScore(60, 30), effScore(95, 0)];
const it = (id, eff, prog, kick) => ({{ id, eff, prog, kick }});
out.orderPlain = deskOrder([it("a", 50, 0, 0), it("b", 70, 0, 0), it("c", 60, 0, 0)], null);
out.orderHold = deskOrder([it("a", 60, 0, 0), it("b", 64, 0, 0), it("c", 10, 0, 0)], "a");
out.orderBreak = deskOrder([it("a", 60, 0, 0), it("b", 65, 0, 0), it("c", 10, 0, 0)], "a");
out.orderGone = deskOrder([it("b", 65, 0, 0), it("c", 10, 0, 0)], "a");
out.orderTieProg = deskOrder([it("a", 50, 1000, 5), it("b", 50, 3000, 9)], null);
out.orderTieKick = deskOrder([it("a", 50, 1000, 9), it("b", 50, 1000, 5)], null);
out.chips = ["021018", "eb0028", "003b75", "ffffff", "ffb612", "0b1220", "", "zzzzzz"].map((c) => chipColors({{ color: c, alt: "eb0028" }}));
out.chipNone = chipColors(null);
out.chipHashed = chipColors({{ color: "#c8102e", alt: "" }});
console.log(JSON.stringify(out));
"""
    o = _node(script)
    check("default live window", o["defaultLive"], "snf")
    check("default next window", o["defaultNext"], "sunE")
    check("default all final", o["defaultAllFinal"], "mnf")
    check("default empty", o["defaultEmpty"], "all")
    check("poll live 20s", o["delayLive"], 20000)
    check("poll within 60 min 60s", o["delaySoon"], 60000)
    check("poll idle 120s", o["delayFar"], 120000)
    check("poll tbd time idle", o["delayTbd"], 120000)
    check("poll long-stale pre idle", o["delayStalePre"], 120000)
    check("poll all final idle", o["delayAllFinal"], 120000)
    check("swing up", (round(o["swingUp"]["pts"], 6), o["swingUp"]["toward"]), (12.0, "home"))
    check("swing down", (round(o["swingDown"]["pts"], 6), o["swingDown"]["toward"]), (15.0, "away"))
    check("swing ignores samples older than 3 min", o["swingOld"], {"pts": 0, "toward": None})
    check("swing needs two samples", o["swingOne"], {"pts": 0, "toward": None})
    check("swing empty", o["swingEmpty"], {"pts": 0, "toward": None})
    check("eff bonus rounds and caps at 15", o["eff"], [63, 75, 95])
    check("desk order by eff", o["orderPlain"], ["b", "c", "a"])
    check("hysteresis holds #1 under 5", o["orderHold"], ["a", "b", "c"])
    check("hysteresis releases at 5", o["orderBreak"], ["b", "a", "c"])
    check("hysteresis with the hero gone", o["orderGone"], ["b", "c"])
    check("tie: later in game first", o["orderTieProg"], ["b", "a"])
    check("tie: earlier kick next", o["orderTieKick"], ["b", "a"])
    # HOU 021018 is near card black: alt. IND 003b75 navy is also dark but readable against the card.
    check("chip: near-black falls back to alt", o["chips"][0]["bg"], "eb0028")
    check("chip: color kept", o["chips"][1]["bg"], "eb0028")
    check("chip: white text on red", o["chips"][1]["fg"], "ffffff")
    check("chip: white keeps dark text", (o["chips"][3]["bg"], o["chips"][3]["fg"]), ("ffffff", "111111"))
    check("chip: gold gets dark text", (o["chips"][4]["bg"], o["chips"][4]["fg"]), ("ffb612", "111111"))
    check("chip: card colour falls back", o["chips"][5]["bg"], "eb0028")
    check("chip: empty falls back", o["chips"][6]["bg"], "eb0028")
    check("chip: junk rejected", o["chips"][7]["bg"], "eb0028")
    check("chip: no colors is neutral", o["chipNone"]["bg"], "2a3a5a")
    check("chip: hash prefix accepted", o["chipHashed"]["bg"], "c8102e")
    for c in o["chips"] + [o["chipNone"], o["chipHashed"]]:
        check.true("chip colors are bare hex", re.fullmatch(r"[0-9a-f]{6}", c["bg"]) and re.fullmatch(r"[0-9a-f]{6}", c["fg"]) is not None)


# ---------- render smoke test (stub DOM in node) ----------

HARNESS = r"""
const vm = require("vm");
const cfg = JSON.parse(process.env.CFG);
const els = {};
const el = (id) => (els[id] ||= { id, innerHTML: "", textContent: "", hidden: false, className: "", dataset: {} });
const handlers = { doc: {}, win: {} };
const timers = [];
const opened = [];
const regs = [];
const fetched = [];
let fetchMode = "ok";
let step = 0;
const store = {};
const ctx = {
  console, Intl, Date, Math, JSON, Number, String, Array, Object, Set, Promise, isNaN, isFinite, parseInt, RegExp, Error,
  localStorage: { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; } },
  location: { hash: cfg.hash || "", pathname: "/nfl/", search: "" },
  history: { replaceState: (a, b, url) => { ctx.location.hash = url.includes("#") ? url.slice(url.indexOf("#")) : ""; } },
  CustomEvent: function (n) { this.type = n; },
  AbortController: function () { this.signal = {}; this.abort = () => {}; },
  setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
  clearTimeout: () => {},
  navigator: { serviceWorker: { register: (u, o) => { regs.push([u, o]); return Promise.resolve(); } } },
  fetch: async (url) => {
    fetched.push(url);
    if (url.startsWith("/nfl/metrics.json")) return cfg.metrics ? { ok: true, json: async () => cfg.metrics } : { ok: false, status: 404 };
    if (fetchMode === "fail") throw new Error("network down");
    const payload = cfg.lives[Math.min(step, cfg.lives.length - 1)];
    step += 1;
    return { ok: true, json: async () => payload };
  },
};
ctx.document = {
  hidden: false, title: "",
  getElementById: el,
  addEventListener: (t, f) => { handlers.doc[t] = f; },
};
ctx.window = {
  NFL_DATA: cfg.snap, addEventListener: (t, f) => { handlers.win[t] = f; }, dispatchEvent: () => {},
  NFLSheet: { open: (id) => opened.push(id), close: () => opened.push("closed") },
};
vm.createContext(ctx);
const flush = () => new Promise((r) => setImmediate(r));
(async () => {
  vm.runInContext(cfg.src, ctx);
  await flush(); await flush();
  const out = { first: {} };
  const snap = () => ({ main: el("main").innerHTML, desk: el("desk").innerHTML, banner: el("banner").innerHTML, bannerHidden: el("banner").hidden,
                         pills: el("pills").innerHTML, bye: el("bye").innerHTML, updated: el("updated").textContent, kicker: el("kicker").textContent, title: ctx.document.title });
  out.first = snap();
  out.url1 = fetched[0];
  out.delay1 = timers[timers.length - 1].ms;
  // second poll (timer fires): win probability moves
  timers[timers.length - 1].fn(); await flush(); await flush();
  out.second = snap();
  // third poll fails: last data stays, banner appears
  fetchMode = "fail";
  timers[timers.length - 1].fn(); await flush(); await flush();
  out.third = snap();
  // routing
  ctx.location.hash = "#game/401873066"; handlers.win.hashchange();
  ctx.location.hash = "#live"; handlers.win.hashchange();
  out.liveView = snap();
  ctx.location.hash = ""; handlers.win.hashchange();
  out.opened = opened;
  out.fetchedAll = fetched;
  out.regs = regs;
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def _w11_payloads():
    """A live payload in the section 3.2 shape built from the W11 scoreboard fixture, in three polls."""
    import sys
    sys.path.insert(0, str(ROOT))
    from nflcore import venues

    sb = json.loads((ROOT / "scripts" / "fixtures" / "nfl" / "sb_2026_w11.json").read_text())
    evs = {e["shortName"]: e for e in sb["events"]}

    def team(e, side):
        c = next(c for c in e["competitions"][0]["competitors"] if c["homeAway"] == side)
        t = c["team"]
        return t, {"id": t["id"], "abbr": t["abbreviation"], "name": t["name"], "score": 0, "record": "3-5", "timeouts": 3, "linescores": []}

    def mk(short, state, **kw):
        e = evs[short]
        (at, a), (ht, h) = team(e, "away"), team(e, "home")
        g = {"id": e["id"], "state": state, "status": "STATUS_SCHEDULED", "statusDetail": "", "statusShort": "", "period": 0, "periodLabel": "", "clock": "",
             "clock_s": 0, "completed": False, "ot": False, "result": None, "date": e["date"].replace("Z", ":00Z") if len(e["date"]) == 17 else e["date"],
             "time_tbd": False, "flex_note": "", "neutral": e["competitions"][0]["neutralSite"], "placeholder": False, "venue_name": "", "broadcasts": ["CBS"],
             "away": a, "home": h, "situation": None, "wp": None, "desk": None}
        g.update(kw)
        return g, at, ht

    live_a, at, ht = mk("IND @ HOU", "pre")
    out, snap = [], []

    def snap_team(t):
        return {"id": t["id"], "abbr": t["abbreviation"], "nv": t["abbreviation"], "name": t["name"], "full": t["displayName"], "color": t["color"], "alt": t["alternateColor"], "record": {"w": 3, "l": 5, "t": 0, "text": "3-5"}, "score": ""}

    def add(short, state, snapkw=None, **kw):
        g, at_, ht_ = mk(short, state, **kw)
        e = evs[short]
        v = venues.venue(e["competitions"][0]["venue"]["id"])
        s = {"id": e["id"], "date": g["date"], "time_tbd": False, "kick_ct": "", "flex_note": "", "kind": "regular", "round": None, "placeholder": False,
             "neutral": g["neutral"], "state": "pre", "broadcasts": [], "venue": {"id": v["id"], "name": v["name"], "city": v["city"], "region": v["region"], "country": v["country"], "roof": v["roof"]} if v else None,
             "away": snap_team(at_), "home": snap_team(ht_), "wx_status": "ok", "wx": {"temp": 48, "wind": 12, "gusts": 20, "pop": 10, "apparent": 44, "label": "Clear", "flags": ["WIND"], "roof_note": ""}}
        s.update(snapkw or {})
        snap.append(s)
        out.append(g)
        return g

    add("IND @ HOU", "pre", {"wx_status": "retractable"})
    add("MIA @ BUF", "in", status="STATUS_IN_PROGRESS", period=3, periodLabel="Q3", clock="8:06", clock_s=486,
        away={"id": "15", "abbr": "MIA", "name": "<img src=x onerror=alert(1)>", "score": 17, "record": "5-4", "timeouts": 2, "linescores": []},
        situation={"text": "3rd & 5 at BUF 40", "down": 3, "distance": 5, "stoppage": False, "possession": "away", "possession_abbr": "MIA", "yard_text": "BUF 40",
                   "yl100": 40, "is_red_zone": False, "goal_to_go": False, "last_play": {"id": "1", "text": "<script>alert(1)</script> Pass incomplete", "type": "Pass"}},
        wp={"home": 0.5, "tie": 0.0}, desk={"score": 71.0, "why": ["One score, Q4"]})
    add("NO @ CHI", "in", status="STATUS_IN_PROGRESS", period=4, periodLabel="Q4", clock="2:00", clock_s=120,
        situation={"text": None, "down": None, "distance": None, "stoppage": True, "possession": "home", "possession_abbr": "CHI", "yard_text": "NO 12",
                   "yl100": 12, "is_red_zone": True, "goal_to_go": True, "last_play": {"id": "2", "text": "Timeout", "type": "Timeout"}},
        wp={"home": 0.4, "tie": 0.0}, desk={"score": 90.0, "why": ["Red zone", "2-minute"]})
    add("TEN @ DAL", "post", status="STATUS_FINAL", completed=True, result="home", ot=True,
        away={"id": "10", "abbr": "TEN", "name": "Titans", "score": 20, "record": "2-7", "timeouts": 0, "linescores": []},
        home={"id": "6", "abbr": "DAL", "name": "Cowboys", "score": 23, "record": "4-4-1", "timeouts": 0, "linescores": []})
    add("MIN VS SF", "pre", neutral=True)
    ph = dict(out[0])
    ph.update(id="401872910", placeholder=True, away=None, home=None, date="2027-01-16T05:00:00Z", time_tbd=True)
    out.append(ph)
    bye = ["ATL", "CLE"]
    base = {"ok": True, "v": 1, "count": len(out), "fetched_at": "2026-11-22T20:00:00Z", "source_host": "x", "stale": False,
            "season": {"year": 2026, "type": 2}, "week": {"number": 11, "label": "Week 11"}, "teams_on_bye": bye, "warnings": []}
    poll1 = {**base, "games": out}
    g2 = json.loads(json.dumps(out))
    g2[1]["wp"] = {"home": 0.64, "tie": 0.0}
    g2[1]["home"]["score"] = 14
    poll2 = {**base, "games": g2, "stale": True}
    snapshot = {"schema": 1, "season": {"year": 2026, "type": 2}, "week": {"number": 11, "label": "Week 11", "end": "2099-01-01T00:00:00Z"},
                "teams_on_bye": [{"id": "1", "abbr": "ATL", "name": "Falcons"}], "games": snap}
    snapshot["games"][3]["away"]["color"] = "red;background:url(//x.test/a.png)"
    return poll1, poll2, snapshot


def test_render(check):
    if not NODE:
        return
    src = _src("app.js")
    poll1, poll2, snapshot = _w11_payloads()

    def run(snap, hash_="", metrics=None):
        env = {"CFG": json.dumps({"src": src, "lives": [poll1, poll2], "snap": snap, "hash": hash_, "metrics": metrics}), "PATH": str(Path(NODE).parent)}
        p = subprocess.run([NODE, "-e", HARNESS], capture_output=True, text=True, env=env, timeout=60)
        if p.returncode:
            raise AssertionError("harness failed: " + p.stderr[:800])
        return json.loads(p.stdout.strip().splitlines()[-1])

    snapshot["games"][1]["away"]["full"] = "<img src=x onerror=alert(1)>"
    o = run(snapshot)
    f, s2, s3 = o["first"], o["second"], o["third"]
    oa = run(snapshot, "#all")["first"]
    check("snapshot week pins the live url", o["url1"], "/api/nfl/live?st=2&week=11")
    check("live game sets a 20s poll", o["delay1"], 20000)
    check("title", f["title"], "Pro Football Board - Week 11, 2026")
    check("kicker", f["kicker"], "Week 11 · 2026")
    check.true("updated caption", re.match(r"Updated \d{1,2}:\d{2}:\d{2} (AM|PM) CT", f["updated"]) is not None, f["updated"])
    m = oa["main"]
    check.true("hostile team name is escaped", "&lt;img src=x" in m and "<img" not in m)
    check.true("hostile play text is escaped", "&lt;script&gt;" in m and "<script" not in m)
    check.true("hostile snapshot color never reaches markup", "x.test" not in m and "url(" not in m)
    check.true("live pill and clock", 'class="livepill">LIVE' in m and "Q3 8:06" in m)
    check.true("down and distance shown", "3rd &amp; 5 at BUF 40" in m)
    check.true("stoppage shown instead of stray text", "Stoppage" in m and "RED ZONE" not in m and "GOAL TO GO" in m)
    check.true("field strip with red zone", m.count('class="field"') == 2 and 'class="rzone l"' in m)
    check.true("final with overtime", "FINAL/OT" in m)
    check.true("neutral tag", "VS · neutral site" in m)
    check.true("placeholder card", "is-ph" in m and "Teams are set after" in m and "TBD" in m)
    check.true("flex note slot stays empty without a note", "flexnote" not in m)
    check.true("weather slot from snapshot", "Clear" in m and "mph" in m)
    check.true("HOU near-black color falls back to alt", "background:#eb0028" in m)
    check.true("live games sort first", m.index("is-live") < m.index("is-final"))
    ids = re.findall(r'<article class="card[^"]*" id="g(\d+)"', m)
    check("sorted: live by desk score, upcoming by kick, TBD last, final last", ids,
          ["401873071", "401873070", "401873066", "401873077", "401872910", "401873073"])
    check.true("default window shows only its own games", f["main"].count("<article") == 3, str(f["main"].count("<article")))
    check.true("every card links to its sheet", 'href="#game/401873066"' in m)
    check.true("bye strip", "On bye" in f["bye"] and ">ATL<" in f["bye"] and ">CLE<" in f["bye"])
    check.true("desk shows hero and reasons", "Whip-around" in f["desk"] and "Red zone" in f["desk"] and f["desk"].index("CHI") < f["desk"].index("MIA"))
    check.true("desk never shows betting words", re.search(r"odds|spread|cover|wager", f["desk"] + m, re.I) is None)
    check.true("default pill is the live window", "dot" in f["pills"] and 'aria-pressed="true"' in f["pills"])
    check.true("live banner clear on a good poll", f["bannerHidden"] is True)
    check.true("second poll: swing chip", "WP swing" in s2["desk"] and "+14" in s2["desk"], s2["desk"][:300])
    check.true("second poll: stale banner", "slow to answer" in s2["banner"])
    check.true("failed poll keeps the last data", s3["main"] == s2["main"] and "could not refresh" in s3["banner"])
    check.true("live view lists only live games", "is-final" not in o["liveView"]["main"] and "is-live" in o["liveView"]["main"])
    check("service worker registered once with scope", o["regs"], [["/nfl/sw.js", {"scope": "/nfl/"}]])
    check.true("no metrics file: no metrics block", "class=\"mx\"" not in oa["main"])
    check("sheet opened then closed on leaving the route", o["opened"], ["401873066", "closed"])

    # no snapshot: live only, canonical url, a banner saying what is missing
    o2 = run(None)
    check("no snapshot: canonical url", o2["url1"], "/api/nfl/live")
    check.true("no snapshot: banner names what is missing", "snapshot" in o2["first"]["banner"].lower())
    o2a = run(None, "#all")["first"]
    check.true("no snapshot: cards still render", o2a["main"].count("<article") == 6)
    check.true("no snapshot: hostile live name escaped", "&lt;img src=x" in o2a["main"] and "<img" not in o2a["main"])
    check.true("no snapshot: no weather block", 'class="wx"' not in o2["first"]["main"])
    check.true("no snapshot: neutral chip for unknown colors", "background:#2a3a5a" in o2a["main"])
    check.true("no snapshot: bye from live abbreviations", ">ATL<" in o2["first"]["bye"])

    # a snapshot from another week is ignored, with a banner
    other = json.loads(json.dumps(snapshot))
    other["week"]["number"] = 10
    o3 = run(other)
    check.true("stale snapshot week: ignored", 'class="wx"' not in o3["first"]["main"] and "another week" in o3["first"]["banner"])
    # an expired snapshot window stops pinning the live request
    old = json.loads(json.dumps(snapshot))
    old["week"]["end"] = "2020-01-01T00:00:00Z"
    check("expired snapshot week: canonical url", run(old)["url1"], "/api/nfl/live")
    # hash routes
    check.true("#all lists every window", run(snapshot, "#all")["first"]["main"].count("<article") == 6)


# ---------- weather and metrics rendering with the real generated files ----------

WX_FUNCS = ("ctText", "compass", "wxStale", "signed", "hWx", "ord", "metricsFor", "hMetricRows", "hMetrics", "esc")
WX_SCRIPT = r"""
const ESC_RE = new RegExp("[&<>\"']", "g");
const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" };
const KICK_FMT = new Intl.DateTimeFormat("en-US", { timeZone: "America/Chicago", weekday: "short", hour: "numeric", minute: "2-digit" });
const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const STALE_MS = 18 * 3600000;
let metrics = JSON.parse(process.env.METRICS);
let live = null;
const SNAP = { season: { year: 2026, type: 2 } };
%s
const games = JSON.parse(process.env.GAMES);
const mkSide = (t) => ({ abbr: t.abbr });
const out = {};
out.cards = games.map((g) => {
  const x = { wx: g.wx, wx_status: g.wx_status, ph: false, away: mkSide(g.away), home: mkSide(g.home) };
  return { wx: hWx(x), mx: hMetrics(x), status: g.wx_status };
});
out.compass = [0, 11, 22.5, 90, 180, 270, 348.75, 360, null, "x"].map(compass);
const now = Date.now();
out.stale = [wxStale({ stale: true }, now), wxStale({ fetched_at: new Date(now - 3600000).toISOString() }, now), wxStale({ fetched_at: new Date(now - 24 * 3600000).toISOString() }, now), wxStale(null, now)];
const base = { temp: 40, wind: 5, winddir: 90, fetched_at: "2026-11-15T20:56:37Z", label: "Clear", flags: ["<b>x</b>"] };
out.staleHtml = hWx({ wx: { ...base, stale: true }, wx_status: "ok" });
out.freshHtml = hWx({ wx: { ...base, fetched_at: new Date().toISOString() }, wx_status: "ok" });
out.errHtml = hWx({ wx: null, wx_status: "error" });
out.naHtml = hWx({ wx: { ...base }, wx_status: "na" });
out.small = (() => {
  const m = JSON.parse(JSON.stringify(metrics));
  const t = games.find((g) => g.home.abbr in m.teams);
  m.teams[t.home.abbr].small_sample = true;
  metrics = m;
  return hMetrics({ ph: false, away: mkSide(t.away), home: mkSide(t.home) });
})();
console.log(JSON.stringify(out));
"""

BETTING = re.compile("|".join(["od" + "ds", "spr" + "ead", "mon" + "eyline", "co" + "ver", "wa" + "ger", "ed" + "ge", "fav" + "orite", "should win", "pi" + "ck", "pro" + "j", "implied", "bet"]), re.I)


def test_wx_metrics(check):
    if not NODE:
        return
    src = _src("app.js")
    snap = json.loads((NFL / "games.json").read_text("utf-8"))
    metrics = json.loads((NFL / "metrics.json").read_text("utf-8"))
    script = WX_SCRIPT % _extract(src, WX_FUNCS)
    env = {"PATH": str(Path(NODE).parent), "GAMES": json.dumps(snap["games"]), "METRICS": json.dumps(metrics)}
    p = subprocess.run([NODE, "-e", script], capture_output=True, text=True, env=env, timeout=60)
    if p.returncode:
        raise AssertionError("wx harness failed: " + p.stderr[:800])
    o = json.loads(p.stdout.strip().splitlines()[-1])
    cards = o["cards"]
    check("one card per generated game", len(cards), len(snap["games"]))
    for c, g in zip(cards, snap["games"]):
        tag = f"{g['shortName']} ({g['wx_status']})"
        st = g["wx_status"]
        if st == "dome":
            check.true(f"{tag}: Indoors", "<b>Indoors</b>" in c["wx"] and "mph" not in c["wx"])
        elif st in ("ok", "retractable", "canopy"):
            check.true(f"{tag}: temp, wind with compass, rain", "mph" in c["wx"] and "Rain" in c["wx"] and "<b>" in c["wx"] and re.search(r"Wind</div><div class=\"val\">\d+ mph [NESW]{1,3}<", c["wx"]) is not None, c["wx"][:300])
            for f in (g["wx"].get("flags") or []):
                check.true(f"{tag}: chip {f}", f'<span class="flag">{f}</span>' in c["wx"])
            if g["wx"].get("roof_note"):
                check.true(f"{tag}: roof note", g["wx"]["roof_note"] in c["wx"])
        else:
            check(f"{tag}: nothing rendered", c["wx"], "")
        check.true(f"{tag}: metrics block with footnote", c["mx"].count("EPA/play") == 2 and f"through Week {metrics['through_week']}, CC BY 4.0" in c["mx"] and "PROE" in c["mx"] and "Success rate" in c["mx"], c["mx"][:200])
        check.true(f"{tag}: no betting vocabulary", BETTING.search(c["wx"] + c["mx"]) is None, (BETTING.search(c["wx"] + c["mx"]) or [""])[0] if BETTING.search(c["wx"] + c["mx"]) else "")
    check("compass points", o["compass"], ["N", "N", "NNE", "E", "S", "W", "N", "N", "", ""])
    check("staleness", o["stale"], [True, False, True, False])
    check.true("stale forecast marked with fetched time", "Forecast from" in o["staleHtml"] and "CT" in o["staleHtml"])
    check.true("fresh forecast has no stale note", "Forecast from" not in o["freshHtml"])
    check.true("flags are escaped", "<b>x</b>" not in o["staleHtml"] and "&lt;b&gt;x" in o["staleHtml"])
    check("failed weather renders nothing", o["errHtml"], "")
    check("placeholder status renders nothing", o["naHtml"], "")
    check("small_sample hides the metrics block", o["small"], "")
