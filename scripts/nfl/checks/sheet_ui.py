"""Game sheet client (nfl/sheet.js, nfl/sheet.css): syntax, pure helpers under node, escaping and vocabulary scans."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from .repo import BETTING, PRIVATE

ROOT = Path(__file__).resolve().parents[3]
JS = ROOT / "nfl" / "sheet.js"
CSS = ROOT / "nfl" / "sheet.css"
NODE = shutil.which("node")

# Built from fragments so this file never matches its own scan.
EXTRA_WORDS = re.compile(r"\b(" + "|".join(("cov" + "er(s|ed|ing)?", "le" + "an", "proj" + "ection", "pre" + "dict(or|ion)?")) + r")\b", re.I)


def _pure_source() -> str:
    src = JS.read_text()
    a = src.index('"use strict";') + len('"use strict";')
    return src[a:src.index("// pure:end")]


def _node(expr_js: str):
    script = f"const api = (function () {{{_pure_source()}\nreturn {{ esc, int, periodLabel, lineLabels, downText, phase, defaultTab, totals, statusText, chipStyle, helmetColors, wpValues, wpPath, wpTicks, isBigPlay, playMatches, allPlays, sideOf, trackerGeom, panelHtml }};\n}})();\nconsole.log(JSON.stringify({expr_js}));"
    out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
    if out.returncode:
        raise RuntimeError(out.stderr.strip()[:600])
    return json.loads(out.stdout)


def _team(abbr, name, color):
    return {"id": abbr.lower() + "1", "abbr": abbr, "name": name, "color": color}


def _play(i, text, **kw):
    p = {"id": f"p{i}", "seq": i, "period": 3, "periodLabel": "Q3", "clock": "10:02", "down": 1, "distance": 10, "yard_text": "ATL 35",
         "text": text, "type": "Pass Reception", "kind": "play", "scoring": False, "score_value": 0, "away": 7, "home": 3,
         "wp": None, "penalty": False, "turnover": False, "yards": 5}
    p.update(kw)
    return p


def _game(state="IN_PROGRESS", **over):
    d = {
        "ok": True, "v": 1, "id": "401873058", "state": state, "period": 3, "periodLabel": "Q3", "clock": "10:02",
        "teams": {"away": _team("KC", "Kansas City Chiefs", "e31837"), "home": _team("ATL", "Atlanta Falcons", "000000")},
        "linescores": {"away": [7, 3, 0], "home": [0, 7]}, "ot_periods": 0, "result": None,
        "scoring": [{"id": "s1", "drive_id": "d1", "period": 1, "periodLabel": "Q1", "clock": "5:00", "team": "KC", "kind": "TD", "text": "Mahomes pass for 12 yds", "away": 7, "home": 0}],
        "drives": [
            {"id": "d1", "team": "KC", "desc": "8 plays, 75 yards, 4:10", "result": "Touchdown", "live": False, "scoring": True,
             "start": {"period": 1, "periodLabel": "Q1", "clock": "9:00", "yard_text": "KC 25", "yl100": 75}, "plays": 8, "yards": 75, "time": "4:10",
             "plays_list": [_play(1, "Run for 5 yds", type="Rush"), _play(2, "Long pass for 41 yds", yards=41),
                            _play(3, "Holding on offense", penalty=True, yards=-10, type="Penalty"),
                            _play(4, "Coin Toss", kind="admin", type="Coin Toss", down=0, distance=0),
                            _play(5, "TD <img src=x onerror=alert(1)>", scoring=True, score_value=7, yards=12)]},
            {"id": "d2", "team": "ATL", "desc": "3 plays", "result": None, "live": True,
             "start": {"period": 3, "periodLabel": "Q3", "clock": "12:00", "yard_text": "ATL 30", "yl100": 70}, "plays": 3, "yards": 15, "time": "1:50",
             "plays_list": [_play(6, "Pass intercepted", turnover=True, yards=0), _play(7, "Kickoff 65 yds", type="Kickoff", yards=65, down=0),
                            _play(8, "Official Timeout", kind="admin", type="Official Timeout")]},
        ],
        "current_drive_id": "d2", "tracker": {"drive_id": "d2", "team": "ATL", "start_yl": 30, "cur_yl": 85, "plays": 3, "yards": 15, "elapsed": "1:50"},
        "winprob": {"points": [{"p": 0.5, "pid": "p1", "seq": 1, "t": 0}, {"p": 0.4, "pid": "p2", "seq": 2, "t": 1}, {"p": 0.7, "pid": "p6", "seq": 6, "t": 2}],
                    "quarters": [[1, 0], [2, 1], [5, 2]], "ot_at": None},
        "box": [["First downs", "12", "9"], ["Total yards", "250", "180"]],
        "leaders": {"away": [{"cat": "Passing", "name": "Mahomes", "line": "20/30, 250"}], "home": [{"cat": "Rushing", "name": "Robinson", "line": "12 car, 60"}]},
        "warnings": [],
    }
    d.update(over)
    return d


def _hostile():
    d = _game()
    bad = '"><script>alert(1)</script><b onclick="x'
    d["teams"]["away"].update(name=bad, abbr=bad, color='red" onmouseover="x')
    d["drives"][0]["id"] = '1" onclick="x'
    d["drives"][0]["team"] = bad
    d["scoring"][0].update(text=bad, kind=bad, team=bad)
    d["box"] = [[bad, bad, bad]]
    d["leaders"]["away"] = [{"cat": bad, "name": bad, "line": bad}]
    d["periodLabel"] = bad
    d["clock"] = bad
    return d


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: set[str] = set()
        self.attrs: set[str] = set()

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        self.attrs.update(k for k, _ in attrs)

    handle_startendtag = handle_starttag


def _parse(html: str) -> _Tags:
    p = _Tags()
    p.feed(html)
    return p


# --- static scans ---------------------------------------------------------

def _scan(src: str):
    """Yield every ${...} expression in every template literal (nested too) and every innerHTML assignment RHS."""
    exprs: list[str] = []
    n = len(src)

    def string(i, q):
        i += 1
        while i < n and src[i] != q:
            i += 2 if src[i] == "\\" else 1
        return i + 1

    def regex(i):
        i += 1
        cls = False
        while i < n:
            c = src[i]
            if c == "\\":
                i += 2
                continue
            if c == "[":
                cls = True
            elif c == "]":
                cls = False
            elif c == "/" and not cls:
                break
            i += 1
        i += 1
        while i < n and src[i].isalpha():
            i += 1
        return i

    def template(i):
        i += 1
        while i < n:
            c = src[i]
            if c == "\\":
                i += 2
            elif c == "`":
                return i + 1
            elif c == "$" and src[i + 1] == "{":
                start = i + 2
                i = code(start, True)
                exprs.append(src[start:i - 1])
            else:
                i += 1
        return i

    def code(i, in_expr):
        depth = 0
        prev = ""
        while i < n:
            c = src[i]
            if c in "\"'":
                i = string(i, c); prev = "s"; continue
            if c == "`":
                i = template(i); prev = "s"; continue
            if c == "/" and src[i + 1] == "/":
                i = src.index("\n", i); continue
            if c == "/" and src[i + 1] == "*":
                i = src.index("*/", i) + 2; continue
            if c == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~"):
                i = regex(i); prev = "s"; continue
            if in_expr:
                if c == "{":
                    depth += 1
                elif c == "}":
                    if depth == 0:
                        return i + 1
                    depth -= 1
            if not c.isspace():
                prev = c
            i += 1
        return i

    code(0, False)
    return exprs


def _split_top(e: str, sep: str):
    parts, depth, i, cur = [], 0, 0, ""
    while i < len(e):
        c = e[i]
        if c in "\"'`":
            j = i + 1
            while j < len(e) and e[j] != c:
                j += 2 if e[j] == "\\" else 1
            cur += e[i:j + 1]; i = j + 1; continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if depth == 0 and e.startswith(sep, i):
            parts.append(cur); cur = ""; i += len(sep); continue
        cur += c; i += 1
    parts.append(cur)
    return parts


def _single_call(e: str, name_re: str) -> bool:
    m = re.match(name_re + r"\(", e)
    if not m:
        return False
    depth, i = 1, m.end()
    while i < len(e) and depth:
        c = e[i]
        if c in "\"'`":
            j = i + 1
            while j < len(e) and e[j] != c:
                j += 2 if e[j] == "\\" else 1
            i = j
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    return depth == 0 and i == len(e)


def _safe_expr(e: str) -> bool:
    e = e.strip()
    if re.fullmatch(r"\w*Html", e) or re.fullmatch(r'"[^"]*"|\d+', e) or (e.startswith("`") and e.endswith("`")):
        return True
    if any(_single_call(e, p) for p in (r"esc", r"int", r"f1", r"CSS\.escape", r"\w+Html")):
        return True
    alts = _split_top(e, "||")
    if len(alts) > 1:
        return all(_safe_expr(a) for a in alts)
    q = _split_top(e, "?")
    if len(q) == 2:
        branches = _split_top(q[1], ":")
        return len(branches) == 2 and all(_safe_expr(b) for b in branches)
    return False


def test_sheet_files(check):
    check.true("nfl/sheet.js exists", JS.is_file())
    check.true("nfl/sheet.css exists", CSS.is_file())
    if not JS.is_file():
        return
    if not NODE:
        print("node not found; skipping sheet_ui node checks")
        return
    r = subprocess.run([NODE, "--check", str(JS)], capture_output=True, text=True)
    check("node --check nfl/sheet.js", r.returncode, 0)
    src = JS.read_text()
    check.true("exports NFLSheet open/close/refresh", re.search(r"window\.NFLSheet = \{ open, close, refresh \}", src) is not None)
    check.true("dialog role and modal", 'role="dialog" aria-modal="true"' in src)
    check.true("Escape closes", 'e.key === "Escape"' in src)
    check.true("focus trap on Tab", 'e.key === "Tab"' in src)
    check.true("20 s poll", "POLL_MS = 20000" in src)
    check.true("polling pauses when hidden", "document.hidden" in src and "visibilitychange" in src)
    check.true("polling only while live", 'phase(S.d) !== "live"' in src)
    check.true("endpoint", '"/api/nfl/game?id="' in src)
    check.true("pure markers", "// pure:start" in src and "// pure:end" in src)


def test_sheet_escaping(check):
    if not JS.is_file():
        return
    src = JS.read_text()
    exprs = _scan(src)
    check.true("found template expressions", len(exprs) > 100, str(len(exprs)))
    bad = [e.strip()[:80] for e in exprs if not _safe_expr(e)]
    check("template expressions not wrapped in esc/int/f1 or an *Html builder", bad, [])
    sinks = re.findall(r"\.innerHTML\s*(\+?=)\s*([^;]+);", src)
    check.true("innerHTML sinks found", len(sinks) >= 2, str(len(sinks)))
    for op, rhs in sinks:
        rhs = rhs.strip()
        check.true(f"innerHTML assignment is whole-markup: {rhs[:40]}", op == "=" and (re.fullmatch(r"\w*Html", rhs) or rhs.startswith("`")))
    for pat in (r"insertAdjacentHTML", r"outerHTML", r"document\.write", r"\beval\(", r"new Function"):
        check.true(f"no {pat}", re.search(pat, src) is None)
    check.true("no remote script or fetch outside the game endpoint", not re.search(r"https?:", src))


def test_sheet_vocabulary(check):
    for path in (JS, CSS):
        if not path.is_file():
            continue
        text = path.read_text()
        for name, pat in (("betting", BETTING), ("extra", EXTRA_WORDS)):
            m = pat.search(text)
            check.true(f"no {name} words in {path.name}", m is None, m.group(0) if m else "")
        for pat in PRIVATE:
            check.true(f"no private name in {path.name}", pat.search(text) is None, pat.pattern)
    if CSS.is_file():
        css = CSS.read_text()
        sel = [s.strip() for blk in re.findall(r"([^{}]+)\{", re.sub(r"/\*.*?\*/", "", css, flags=re.S)) for s in blk.split(",")]
        loose = [s for s in sel if s.startswith(".") and not s.startswith(".ns-") or s in ("body", "html", "*")]
        check("css selectors outside ns- namespace", loose, [])


# --- pure helpers under node ------------------------------------------------

def test_sheet_helpers(check):
    if not NODE or not JS.is_file():
        return
    g = _game()
    plays = [_play(1, "a", yards=20), _play(2, "b", yards=19), _play(3, "c", yards=40, penalty=True), _play(4, "d", yards=60, type="Kickoff"),
             _play(5, "e", yards=30, kind="admin"), _play(6, "f", yards=54, type="Field Goal Good"), _play(7, "g", turnover=True, yards=0),
             _play(8, "h", scoring=True, yards=2), _play(9, "i", penalty=True, yards=-5), _play(10, "j", yards=25, type="Pass Reception")]
    expr = f"""(() => {{
  const plays = {json.dumps(plays)};
  const filt = f => plays.filter(p => api.playMatches(f, p)).map(p => p.id);
  return {{
    periods: [0, 1, 4, 5, 6, 7].map(api.periodLabel),
    lines: [api.lineLabels(4), api.lineLabels(5), api.lineLabels(6)],
    down: [{{ down: 3, distance: 7 }}, {{ down: -1, distance: 5 }}, {{ down: 0 }}, {{ down: 4, distance: null }}, {{ down: 2, distance: 0 }}, null].map(api.downText),
    big: plays.map(api.isBigPlay),
    f_all: filt("all"), f_scoring: filt("scoring"), f_big: filt("big"), f_turn: filt("turnover"), f_pen: filt("penalty"),
    wpvals: [api.wpValues([{{ p: 0.5 }}, {{ p: 1 }}, {{ p: 0 }}]), api.wpValues([{{ p: 50 }}, {{ p: 75 }}]), api.wpValues([{{ p: null }}, {{ p: "x" }}, {{}}])],
    wppath: [api.wpPath([0, 50, 100], 300, 90), api.wpPath([50], 300, 90)],
    ticks: api.wpTicks({{ quarters: [[1, 0], [2, 10], [3, 20], [4, 30], [5, 99]], ot_at: 40 }}, 50).map(t => [t.label, Math.round(t.pct)]),
    ticks2: api.wpTicks({{ quarters: [["Q1", 0], ["OT", 5]], ot_at: 5 }}, 10).map(t => t.label),
    geom: [api.trackerGeom({{ start_yl: 75, cur_yl: 59 }}, "away"), api.trackerGeom({{ start_yl: 75, cur_yl: 15 }}, "away"),
           api.trackerGeom({{ start_yl: 25, cur_yl: 41 }}, "home"), api.trackerGeom({{ start_yl: null, cur_yl: 95 }}, "home"),
           api.trackerGeom({{ start_yl: 100, cur_yl: -40 }}, "home"), api.trackerGeom(null, "home"), api.trackerGeom({{ start_yl: 1, cur_yl: 1 }}, null)],
    side: [api.sideOf({json.dumps(g)}, {{ team: "ATL", drive_id: "d2" }}), api.sideOf({json.dumps(g)}, {{ team: "kc1" }}), api.sideOf({json.dumps(g)}, {{ drive_id: "d1" }}), api.sideOf({json.dumps(g)}, {{ team: "ZZZ" }})],
    chip: ["003594", "#FFFFFF", "zzz", 'red" onmouseover="x', null, "ffb612"].map(api.chipStyle),
    esc: api.esc('<a href="x">&\\'</a>'),
    phase: ["IN_PROGRESS", "in", "HALFTIME", "END_PERIOD", "post", "FINAL", "pre", "SCHEDULED"].map(s => api.phase({{ state: s }})).concat(api.phase({{ state: "DELAYED", drives: [{{}}] }})),
    tab: [api.defaultTab({{ state: "in" }}), api.defaultTab({{ state: "post" }}), api.defaultTab({{ state: "pre" }})],
    totals: [api.totals({json.dumps(g)}), api.totals({{ linescores: {{ away: [], home: [] }}, scoring: [{{ away: 3, home: 7 }}] }}), api.totals({{}})],
    status: [api.statusText({json.dumps(g)}), api.statusText({{ state: "in", status: "STATUS_HALFTIME", period: 2 }}), api.statusText({{ state: "in", status: "STATUS_END_PERIOD", periodLabel: "Q1" }}),
             api.statusText({{ state: "post", linescores: {{ away: [7, 7, 7, 7, 3], home: [7, 7, 7, 7, 0] }}, ot_periods: 1 }}),
             api.statusText({{ state: "post", linescores: {{ away: [7, 7, 7, 7, 0, 0], home: [7, 7, 7, 7, 0, 0] }}, ot_periods: 2, result: "tie" }}),
             api.statusText({{ state: "post", linescores: {{ away: [10, 7, 7, 7], home: [7, 7, 7, 7] }}, ot_periods: 0 }}),
             api.statusText({{ state: "DELAYED", period: 2, drives: [{{}}] }}), api.statusText({{ state: "post", status: "STATUS_POSTPONED" }})],
  }};
}})()"""
    r = _node(expr)
    check("period labels", r["periods"], ["", "Q1", "Q4", "OT", "2OT", "3OT"])
    check("linescore labels", r["lines"], [["Q1", "Q2", "Q3", "Q4"], ["Q1", "Q2", "Q3", "Q4", "OT"], ["Q1", "Q2", "Q3", "Q4", "1OT", "2OT"]])
    check("down text", r["down"], ["3rd & 7", "", "", "4th", "2nd & 0", ""])
    check("big play flags", r["big"], [True, False, False, False, False, False, False, False, False, True])
    check("filter all excludes admin", r["f_all"], ["p1", "p2", "p3", "p4", "p6", "p7", "p8", "p9", "p10"])
    check("filter scoring", r["f_scoring"], ["p8"])
    check("filter big plays", r["f_big"], ["p1", "p10"])
    check("filter turnovers", r["f_turn"], ["p7"])
    check("filter penalties", r["f_pen"], ["p3", "p9"])
    check("wp values", r["wpvals"], [[50, 100, 0], [50, 75], []])
    check("wp path", r["wppath"], ["M0.0,90.0L150.0,45.0L300.0,0.0", ""])
    check("wp ticks (quarter 5 beyond the data is dropped)", r["ticks"], [["Q1", 0], ["Q2", 20], ["Q3", 41], ["Q4", 61], ["OT", 82]])
    check("wp ticks do not duplicate OT", r["ticks2"], ["Q1", "OT"])
    geo = r["geom"]
    check("away offence moves right", [geo[0]["x0"], geo[0]["x1"], geo[0]["dir"], geo[0]["rzX"], geo[0]["red"]], [35, 51, 1, 90, False])
    check("away red zone", geo[1]["red"], True)
    check("home offence moves left", [geo[2]["x0"], geo[2]["x1"], geo[2]["dir"], geo[2]["rzX"], geo[2]["red"]], [85, 69, -1, 10, False])
    check("missing start spot gives no tracker", geo[3], None)
    check("spots are clamped to the field", [geo[4]["x0"], geo[4]["x1"]], [10, 110])
    check("no tracker or no side", [geo[5], geo[6]], [None, None])
    check("possession side", r["side"], ["home", "away", "away", None])
    check("team chip styles", r["chip"], ["background:#003594;color:#ffffff", "background:#ffffff;color:#0b1220", "background:#22314d;color:#f4f7fb",
                                          "background:#22314d;color:#f4f7fb", "background:#22314d;color:#f4f7fb", "background:#ffb612;color:#0b1220"])
    check("esc", r["esc"], "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;")
    check("phase", r["phase"], ["live", "live", "live", "live", "final", "final", "pre", "pre", "hold"])
    check("default tab", r["tab"], ["drives", "scoring", "drives"])
    check("totals sum linescores, fall back to scoring", r["totals"], [{"away": 10, "home": 7}, {"away": 3, "home": 7}, {"away": 0, "home": 0}])
    check("status text", r["status"], ["Q3 10:02", "Halftime", "End of Q1", "Final/OT", "Final/2OT · Tie", "Final", "Delayed", "Postponed"])


def test_sheet_render(check):
    if not NODE or not JS.is_file():
        return
    live, final, ot = _game(), _game("post", ot_periods=0), _game("post", linescores={"away": [7, 7, 7, 7, 3, 0], "home": [7, 7, 7, 7, 0, 3]}, ot_periods=2, tracker=None)
    pre = _game("SCHEDULED", drives=[], scoring=[], linescores={"away": [], "home": []}, winprob={"points": [], "quarters": [], "ot_at": None}, tracker=None)
    expr = f"""(() => {{
  const P = api.panelHtml, L = {json.dumps(live)}, F = {json.dumps(final)}, O = {json.dumps(ot)}, Z = {json.dumps(pre)}, H = {json.dumps(_hostile())};
  const u = (d, k) => Object.assign({{ id: d.id, d, error: null }}, k || {{}});
  const out = {{
    live_default: P(u(L)), live_closed: P(u(L, {{ drv: {{ d2: false }} }})), final_default: P(u(F)), pre: P(u(Z)),
    ot: P(u(O)), loading: P({{ id: "1", d: null, error: null }}), failed: P({{ id: "1", d: null, error: "x" }}), retry: P(u(L, {{ error: "boom" }})),
    plays_all: P(u(L, {{ tab: "plays", filter: "all" }})), plays_big: P(u(L, {{ tab: "plays", filter: "big" }})), plays_turn: P(u(L, {{ tab: "plays", filter: "turnover" }})),
    wp_live: P(u(L, {{ tab: "wp" }})), wp_final: P(u(F, {{ tab: "wp" }})), box: P(u(L, {{ tab: "box" }})), leaders: P(u(L, {{ tab: "leaders" }})), scoring: P(u(L, {{ tab: "scoring" }})),
    bogus_tab: P(u(L, {{ tab: "nope" }})),
    hostile: ["drives", "plays", "wp", "scoring", "box", "leaders"].map(t => P(u(H, {{ tab: t }}))),
  }};
  return out;
}})()"""
    r = _node(expr)
    live_html = r["live_default"]
    check.true("live opens on Drives", 'id="ns-tab-drives"' in live_html and 'aria-selected="true"' in live_html.split('id="ns-tab-drives"')[1][:200])
    check.true("live drive starts open", re.search(r'data-did="d2"[^>]* open', live_html) is not None)
    check.true("finished drive starts closed", re.search(r'data-did="d1"[^>]* open', live_html) is None)
    check.true("user can close the live drive", re.search(r'data-did="d2"[^>]* open', r["live_closed"]) is None)
    check.true("admin plays are folded", 'class="ns-admin"' in live_html and "2 admin plays" not in live_html and "1 admin play" in live_html)
    check.true("field tracker drawn for a live game", 'class="ns-field"' in live_html and "Red zone" in live_html)
    check.true("newest drive first while live", live_html.index('data-did="d2"') < live_html.index('data-did="d1"'))
    check.true("possession marker", 'aria-label="has the ball"' in live_html)
    check.true("helmets beside the chips, in both end zones and at the ball", live_html.count('class="ns-hel"') >= 4 and live_html.split('class="ns-field"')[1].split("ns-fcap")[0].count('viewBox="0 0 24 20"') == 3)
    check.true("helmet is a drawn shape, never an image", "<img" not in live_html and "<image" not in live_html and "href=" not in live_html)
    check("helmet colours: second colour, or grey when it would vanish or match", _node("[{color:'0080c6',alt:'ffc20e'},{color:'29126f',alt:'000000'},{color:'d3bc8d',alt:'d3bc8d'},{color:'zz'},null].map(api.helmetColors)"),
          [{"shell": "#0080c6", "mask": "#ffc20e"}, {"shell": "#29126f", "mask": "#d5dbe6"}, {"shell": "#d3bc8d", "mask": "#d5dbe6"}, {"shell": "#22314d", "mask": "#d5dbe6"}, {"shell": "#22314d", "mask": "#d5dbe6"}])
    check.true("live default has LIVE pill", ">LIVE<" in live_html)
    check.true("dialog heading", 'id="ns-title"' in live_html and "KC at ATL game detail" in live_html)
    check.true("tablist has six tabs", live_html.count('role="tab"') == 6)
    check.true("final opens on Scoring", 'id="ns-tab-scoring"' in r["final_default"] and 'aria-labelledby="ns-tab-scoring"' in r["final_default"])
    check.true("final shows FINAL and no tracker", ">FINAL<" in r["final_default"] and 'class="ns-field"' not in r["final_default"])
    check.true("final drives are chronological and all closed", " open" not in re.findall(r'<details class="ns-drive[^>]*>', _node("(() => api.panelHtml({ id: '1', d: " + json.dumps(final) + ", tab: 'drives' }))()"))[0])
    check.true("OT columns", all(x in r["ot"] for x in ("<th>1OT</th>", "<th>2OT</th>")) and "Final/2OT" in r["ot"])
    check.true("pre game has no tabs", 'role="tab"' not in r["pre"] and "opens at kickoff" in r["pre"].lower())
    check.true("loading and error states", "Loading" in r["loading"] and "data-retry" in r["failed"])
    check.true("poll failure keeps data and says so", "Update failed" in r["retry"] and 'id="ns-tab-drives"' in r["retry"])
    check.true("unknown tab falls back to the default", 'aria-labelledby="ns-tab-drives"' in r["bogus_tab"])
    check.true("big play filter keeps only big plays", "Long pass for 41 yds" in r["plays_big"] and "Run for 5 yds" not in r["plays_big"] and "Kickoff 65" not in r["plays_big"])
    check.true("all filter hides admin plays", "Coin Toss" not in r["plays_all"] and "Official Timeout" not in r["plays_all"])
    check.true("turnover filter", "Pass intercepted" in r["plays_turn"] and "Long pass" not in r["plays_turn"])
    check.true("filters have pressed state", 'aria-pressed="true"' in r["plays_big"] and r["plays_big"].count("data-filter=") == 5)
    check.true("WP is labelled as ESPN's", "ESPN win probability" in r["wp_live"] and "ESPN win probability" in r["wp_final"])
    check.true("WP shows the latest point only while live", "latest ATL 70%" in r["wp_live"] and "latest" not in r["wp_final"])
    check.true("WP never names a winner", not re.search(r"\b(wins|won|winner|victor)\b", r["wp_final"], re.I) and "not a result" in r["wp_final"])
    check.true("WP has quarter ticks and an axis", "ns-wq" in r["wp_live"] and "ns-wpaxis" in r["wp_live"] and 'viewBox="0 0 300 90"' in r["wp_live"])
    check.true("box and leaders render", "First downs" in r["box"] and "Mahomes" in r["leaders"] and "Robinson" in r["leaders"])
    check.true("scoring row", "Mahomes pass for 12 yds" in r["scoring"] and "KC 7 – ATL 0" in r["scoring"])
    allowed_tags = {"div", "span", "button", "h2", "h3", "table", "thead", "tbody", "tr", "th", "td", "b", "i", "svg", "rect", "line", "path", "circle", "polygon", "details", "summary", "p"}
    for name, html in [("live", live_html), ("final", r["final_default"]), ("ot", r["ot"]), ("wp", r["wp_live"]), ("plays", r["plays_all"])] + [(f"hostile{i}", h) for i, h in enumerate(r["hostile"])]:
        p = _parse(html)
        check(f"{name}: only layout tags", sorted(p.tags - allowed_tags), [])
        check(f"{name}: no event-handler attributes", sorted(a for a in p.attrs if a.startswith("on")), [])
    for i, h in enumerate(r["hostile"]):
        check.true(f"hostile tab {i}: no raw script/img", "<script" not in h and "<img" not in h)
    ex = r["live_default"] + _node("(() => api.panelHtml({ id: '1', d: " + json.dumps(_game(drives=_game()["drives"])) + ", tab: 'drives' }))()")
    check.true("play text with markup is escaped", "&lt;img src=x onerror=alert(1)&gt;" in ex and "<img" not in ex)
