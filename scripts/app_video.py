"""Narrated app walkthrough (~90 s) and social promo (~35 s), recorded in the iOS simulator.

    python3 scripts/app_video.py narrate [--cut promo]   # ElevenLabs lines, eleven_v4 by default (spends credits)
    python3 scripts/app_video.py record [--cut both|walkthrough|promo] [--desktop]

`record` boots the simulator, reinstalls the Debug build (fresh stars), drives the
app with AXe while `simctl io recordVideo` runs, logs when each narration line
starts, then lays the lines in at exactly those moments. Output is 1080x1920
H.264 in ios/video/out/ with an .srt beside each video; the promo also gets
burned-in captions and an end card. The promo is also written as an App Store app
preview: 886x1920, 30 fps, ~10 Mbps, AAC 256k stereo, no end card (Guideline 2.3.4:
real footage only), and it must come out 15-30 s. --desktop copies the results to ~/Desktop.

Web content inside the app is not in AXe's accessibility tree, but
`describe-ui --point` reaches it, so buttons are found by probing points.
Record during live games: the Live tab and the game sheet are the point.
Media under ios/video/ is gitignored.
"""
import json, os, shutil, signal, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VID = ROOT / "ios" / "video"
OUT = VID / "out"
STUDIO = Path.home() / "projects" / "dailylocks-studio"
APP = ROOT / "ios/build/DerivedData/Build/Products/Debug-iphonesimulator/CFBGameDay.app"
BUNDLE = "com.hoynelabs.cfbgameday"
UDID = os.environ.get("SIM_UDID", "1923BADE-293A-48EB-A4C8-B24767FA45D9")   # iPhone 17 Pro Max (3CD2868D crashed WebContent on 10/02)
GAP = 0.5            # silence after each line before the next beat
BG = "0x0b1220"

LINES = {
    "walkthrough": [
        "This is CFB GameDay Board on iPhone, on a college football Saturday. The Board tab has every FBS game this week, with kickoff times in Central.",
        "Up top, the live desk lists every game in progress, and the weather desk flags rain, wind, heat, and altitude at kickoff.",
        "Each card has the stadium, the kickoff-hour forecast, the TV network, and the posted line, with projected scores until kickoff.",
        "The lines sheet puts the whole slate in one table, and it downloads as a spreadsheet.",
        "The Live tab shows only the games in progress: score, clock, down and distance, and whether each side is covering the posted spread and total. It updates every thirty seconds.",
        "Tap any game that has kicked off for its game sheet: the line score and every scoring play.",
        "The box score, and each team's leaders.",
        "And every drive, with ESPN's win probability across the game.",
        "Star a game, and it waits for you on the Starred tab.",
        "Search finds any team, stadium, city, or network.",
        "No accounts, no ads, and no wagering. CFB GameDay Board is free on the App Store, and on the web at CFB GameDay dot app.",
    ],
    "promo": [   # also the App Store app preview: real footage, no "covering", no spoken URL (Guideline 2.3.4)
        "Every FBS game. One board.",
        "Kickoff weather at every stadium, and TV for every game.",
        "Live scores every thirty seconds, once they kick.",
        "Tap a game for the box score and drives.",
        "CFB GameDay Board. Free on iPhone.",
    ],
}
CAPTIONS = {   # promo on-screen text, same order as LINES["promo"]
    "promo": [
        "Every FBS game. One board.",
        "Kickoff weather + TV for every game",
        "Live scores every 30 seconds",
        "Box score and drives",
        None,   # X cut: end card carries its own text; App Store cut: plays over the footage
    ],
}


def sh(*cmd, check=True, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, check=check, **kw)


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------- narration

def narrate(cuts):
    for cut in cuts:
        lines = LINES[cut]
        d = VID / cut
        (d / "lines").mkdir(parents=True, exist_ok=True)
        (d / "narration.txt").write_text("\n".join(lines) + "\n")
        env = dict(os.environ, NARRATION=str(d / "narration.txt"), LINES_DIR=str(d / "lines"),
                   ELEVENLABS_MODEL=os.environ.get("ELEVENLABS_MODEL", "eleven_v4"))
        r = subprocess.run(["npx", "tsx", str(ROOT / "ios" / "narrate.mts"), "0.95"], cwd=STUDIO, env=env)
        if r.returncode:
            sys.exit(f"narration failed for {cut}")


def lines_index(cut):
    p = VID / cut / "lines" / "index.json"
    if not p.exists():
        sys.exit(f"{p} missing: run `python3 scripts/app_video.py narrate` first")
    idx = {l["n"]: l for l in json.loads(p.read_text())["lines"]}
    if len(idx) != len(LINES[cut]):
        sys.exit(f"{cut}: {len(idx)} rendered lines, script has {len(LINES[cut])}; re-run narrate")
    return idx


# ---------------------------------------------------------------- simulator

def axe(*a, check=False):
    return sh("axe", *a, "--udid", UDID, check=check)


def probe(pt):
    r = axe("describe-ui", "--point", f"{pt[0]},{pt[1]}")
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return None
    f = d.get("frame") or {}
    return (d.get("AXLabel") or "", f.get("x", 0) + f.get("width", 0) / 2, f.get("y", 0) + f.get("height", 0) / 2)


def find(match, xs, ys):
    """First element (top to bottom, then left to right) whose label satisfies match."""
    pts = [(x, y) for y in ys for x in xs]
    with ThreadPoolExecutor(12) as ex:
        for hit in ex.map(probe, pts):
            if hit and hit[0] and match(hit[0]):
                return hit[1], hit[2]
    return None


def tap(pt, settle=0.8):
    axe("tap", "-x", f"{pt[0]:.0f}", "-y", f"{pt[1]:.0f}")
    time.sleep(settle)


def tab(name, settle=1.5):
    axe("tap", "--label", name, "--element-type", "RadioButton")
    time.sleep(settle)


def swipe(dy, dur=0.7, settle=0.6):
    y0 = 620 if dy > 0 else 250
    axe("swipe", "--start-x", "200", "--start-y", str(y0), "--end-x", "200", "--end-y", str(y0 - dy), "--duration", str(dur))
    time.sleep(settle)


def to_top():
    tap((200, 12), settle=1.0)       # status bar tap scrolls the web view to the top


CHIP_ROWS = range(150, 460, 10)


def chip(label, settle=1.0):
    pt = find(lambda l: l == label, range(30, 400, 25), CHIP_ROWS)
    if pt:
        tap(pt, settle)
    else:
        log(f"chip {label!r} not found")
    return bool(pt)


def setup_sim():
    sh("xcrun", "simctl", "boot", UDID, check=False)
    sh("xcrun", "simctl", "bootstatus", UDID, "-b", check=False, timeout=300)
    sh("xcrun", "simctl", "ui", UDID, "appearance", "dark", check=False)
    sh("xcrun", "simctl", "status_bar", UDID, "override", "--batteryState", "charged", "--batteryLevel", "100",
       "--wifiBars", "3", "--cellularBars", "4", "--operatorName", "", check=False)
    src_mtime = max(p.stat().st_mtime for p in (ROOT / "ios" / "CFBGameDay").rglob("*.swift"))
    if not APP.exists() or APP.stat().st_mtime < src_mtime:
        log("building the simulator app")
        sh("xcodegen", "generate", cwd=ROOT / "ios")
        sh("xcodebuild", "-project", "ios/CFBGameDay.xcodeproj", "-scheme", "CFBGameDay", "-configuration", "Debug",
           "-destination", f"id={UDID}", "-derivedDataPath", "ios/build/DerivedData", "build", "-quiet", cwd=ROOT, timeout=900)


def fresh_launch():
    sh("xcrun", "simctl", "terminate", UDID, BUNDLE, check=False)
    sh("xcrun", "simctl", "uninstall", UDID, BUNDLE, check=False)
    sh("xcrun", "simctl", "install", UDID, APP)
    sh("xcrun", "simctl", "launch", UDID, BUNDLE)
    for _ in range(40):                       # wait for the board to render
        hit = probe((200, 107))
        if hit and "GameDay" in hit[0]:
            time.sleep(2.0)
            return
        time.sleep(1)
    sys.exit("board never rendered in the simulator")


# ---------------------------------------------------------------- recording

class Take:
    def __init__(self, cut, raw):
        self.cut, self.raw, self.idx = cut, raw, lines_index(cut)
        self.cues, self.until = [], 0.0

    def __enter__(self):
        self.proc = subprocess.Popen(["xcrun", "simctl", "io", UDID, "recordVideo", "--codec=h264", "--force", str(self.raw)],
                                     stderr=subprocess.PIPE, text=True)
        deadline = time.time() + 20
        while time.time() < deadline:
            ln = self.proc.stderr.readline()
            if "Recording started" in ln:
                break
        self.t0 = time.monotonic()
        time.sleep(0.8)
        return self

    def __exit__(self, *exc):
        time.sleep(0.3)
        self.proc.send_signal(signal.SIGINT)
        self.proc.wait(timeout=60)

    def say(self, n):
        """Narration line n starts now; the beat's actions run while it plays."""
        self.hold()
        t = time.monotonic() - self.t0
        self.cues.append((n, t))
        self.until = time.monotonic() + self.idx[n]["durationSec"] + GAP
        log(f"{self.cut} line {n:02d} at {t:5.1f}s")

    def hold(self, extra=0.0):
        left = self.until + extra - time.monotonic()
        if left > 0:
            time.sleep(left)


def open_game(r):
    """Game sheet for a live game if there is one, else the first final. Returns False if neither."""
    tab("Live", settle=2.0)
    to_top()
    pt = find(lambda l: l.startswith("LIVE ") or "›" in l, [70, 200], range(300, 790, 12)) \
        or find(lambda l: l == "Game", [60, 90], range(120, 790, 10))
    if not pt:
        tab("Board", settle=1.5)
        to_top()
        chip("All")
        pt = find(lambda l: l == "Game", [60, 90], range(120, 790, 10))
    if pt:
        tap(pt, settle=2.5)
    return bool(pt)


def sheet_tab(label):
    row = find(lambda l: l == "Scoring", [50, 80, 110], range(220, 620, 8))
    y = row[1] if row else 440
    pt = find(lambda l: l == label, range(30, 400, 20), [y])
    if pt:
        tap(pt, settle=1.2)


def close_sheet():
    pt = find(lambda l: l == "Close", [370, 380, 390], range(100, 330, 8))
    tap(pt or (382, 210), settle=1.0)


def walkthrough(r):
    r.say(1)
    r.hold(0.3)
    r.say(2)
    swipe(330, dur=1.2)
    time.sleep(1.2)
    swipe(220, dur=1.0)
    r.say(3)
    to_top()
    chip("Primetime+")
    swipe(380, dur=1.2)
    time.sleep(1.5)
    swipe(260, dur=1.0)
    r.say(4)
    to_top()
    chip("Lines sheet", settle=1.5)
    swipe(300, dur=1.2)
    time.sleep(1.0)
    swipe(300, dur=1.2)
    r.hold()
    to_top()
    chip("Cards", settle=0.5)
    chip("All times", settle=0.5)
    r.say(5)
    tab("Live", settle=2.0)
    to_top()
    time.sleep(1.5)
    swipe(260, dur=1.2)
    time.sleep(2.0)
    swipe(260, dur=1.2)
    r.hold()
    r.say(6)
    open_game(r)
    time.sleep(1.5)
    swipe(250, dur=1.0)
    r.say(7)
    sheet_tab("Box")
    time.sleep(2.2)
    sheet_tab("Leaders")
    r.say(8)
    sheet_tab("Drives")
    r.hold(0.5)
    close_sheet()
    r.say(9)
    tab("Board", settle=1.5)
    to_top()
    swipe(330, dur=1.0)
    star = find(lambda l: l == "☆", [360, 370, 380], range(80, 790, 10))
    if star:
        tap(star, settle=1.0)
    tab("Starred", settle=2.5)
    r.say(10)
    tab("Board", settle=1.2)
    to_top()
    field = find(lambda l: l.startswith("Search"), [120, 200], range(200, 260, 8)) or (200, 233)
    tap(field, settle=1.0)
    axe("type", "Iowa")
    time.sleep(1.8)
    tap((200, 100), settle=0.8)       # blur the field so the keyboard drops before About
    r.say(11)
    tab("About", settle=2.0)
    r.hold(1.0)


def promo(r):
    r.say(1)
    time.sleep(1.0)
    swipe(330, dur=1.0)
    r.say(2)
    swipe(300, dur=1.1)
    time.sleep(1.2)
    swipe(250, dur=1.0)
    r.say(3)
    tab("Live", settle=1.5)
    to_top()
    swipe(240, dur=1.0)
    r.say(4)
    open_game(r)
    sheet_tab("Box")
    time.sleep(1.4)
    sheet_tab("Drives")
    r.hold(0.4)


# ---------------------------------------------------------------- mux

def probe_len(p):
    return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p).stdout.strip())


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(cut, cues, path):
    out, k = [], 1
    for n, t in cues:
        words = json.loads((VID / cut / "lines" / f"{n:02d}.json").read_text())["words"]
        for i in range(0, len(words), 7):
            chunk = words[i:i + 7]
            out.append(f"{k}\n{srt_time(t + chunk[0]['start'])} --> {srt_time(t + chunk[-1]['end'] + 0.15)}\n"
                       + " ".join(w["word"] for w in chunk) + "\n")
            k += 1
    path.write_text("\n".join(out))


def render_caption(text, path):
    sh("swift", ROOT / "scripts" / "render_text.swift", "caption", text, path, timeout=120)


def mux(take, out, appstore=False):
    cut, idx, cues = take.cut, take.idx, list(take.cues)
    width = 886 if appstore else 1080
    last_n, last_t = cues[-1]
    main_len = min(probe_len(take.raw), last_t + idx[last_n]["durationSec"] + 1.0)
    endcard = cut == "promo" and not appstore
    if endcard:   # the promo's closing line plays over the end card, not the recording
        main_len = min(probe_len(take.raw), cues[-2][1] + idx[cues[-2][0]]["durationSec"] + 0.6)
        cues[-1] = (last_n, main_len + 0.3)
    total = cues[-1][1] + idx[cues[-1][0]]["durationSec"] + (1.2 if endcard else 0.6)

    inputs = ["-i", take.raw]
    vf = [f"[0:v]trim=0:{main_len:.3f},setpts=PTS-STARTPTS,fps=30,scale=-2:1920,"
          f"pad={width}:1920:(ow-iw)/2:0:color={BG},setsar=1[v0]"]
    vlast, k = "v0", 1
    if cut in CAPTIONS:
        caps = OUT / f"{cut}_captions"
        caps.mkdir(exist_ok=True)
        for (n, t), text in zip(cues, CAPTIONS[cut]):
            if not text:
                continue
            png = caps / f"{n:02d}.png"
            render_caption(text, png)
            inputs += ["-i", png]
            end = t + idx[n]["durationSec"] + GAP
            vf.append(f"[{k}:v]scale={min(1000, width - 66)}:-1[p{k}]")   # captions render 1000 wide
            vf.append(f"[{vlast}][p{k}]overlay=(W-w)/2:H*0.74:enable='between(t,{t:.2f},{end:.2f})'[c{k}]")
            vlast, k = f"c{k}", k + 1
    if endcard:
        card = OUT / "endcard.png"
        sh("swift", ROOT / "scripts" / "render_text.swift", "card", ROOT / "icons" / "icon-512.png", card, timeout=120)
        inputs += ["-loop", "1", "-t", f"{total - main_len:.3f}", "-i", card]
        vf.append(f"[{k}:v]fps=30,scale=1080:1920,setsar=1,format=yuv420p[card]")
        vf.append(f"[{vlast}]format=yuv420p[main];[main][card]concat=n=2:v=1:a=0[v]")
        k += 1
    else:
        vf.append(f"[{vlast}]format=yuv420p,trim=0:{total:.3f}[v]")
    labels = []
    for n, t in cues:
        inputs += ["-i", VID / cut / "lines" / f"{n:02d}.mp3"]
        ms = int(t * 1000)
        vf.append(f"[{k}:a]adelay={ms}|{ms}[a{n}]")
        labels.append(f"[a{n}]")
        k += 1
    vf.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0,apad,atrim=0:{total:.3f}[a]")
    if appstore:   # App Store Connect app preview spec
        enc = ["-c:v", "libx264", "-profile:v", "high", "-level", "4.0", "-b:v", "10M", "-maxrate", "12M",
               "-bufsize", "20M", "-r", "30", "-c:a", "aac_at", "-b:a", "256k", "-ar", "48000", "-ac", "2"]   # aac_at holds 256k; ffmpeg aac lands ~155k
    else:
        enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k"]
    sh("ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(vf), "-map", "[v]", "-map", "[a]",
       *enc, "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", f"{total:.3f}", out, timeout=900)
    write_srt(cut, cues, out.with_suffix(".srt"))
    (OUT / f"{cut}_cues.json").write_text(json.dumps(cues))
    length = probe_len(out)
    log(f"{out.name}: {length:.1f}s")
    if appstore and not 15 <= length <= 30:
        sys.exit(f"{out.name} is {length:.1f}s; App Store previews must be 15-30 s. Trim the promo beats or lines.")


def record(cuts, desktop):
    OUT.mkdir(parents=True, exist_ok=True)
    for c in cuts:
        lines_index(c)
    setup_sim()
    stamp = time.strftime("%Y-%m-%d")
    made = []
    for c in cuts:
        fresh_launch()
        raw = OUT / f"{c}-raw.mp4"
        with Take(c, raw) as r:
            (walkthrough if c == "walkthrough" else promo)(r)
        out = OUT / f"cfb-gameday-{c}-{stamp}.mp4"
        mux(r, out)
        made += [out, out.with_suffix(".srt")]
        if c == "promo":
            store = OUT / f"cfb-gameday-promo-appstore-{stamp}.mp4"
            mux(r, store, appstore=True)
            made.append(store)
    if desktop:
        dest = Path.home() / "Desktop" / f"cfb-gameday-video-{stamp}"
        dest.mkdir(exist_ok=True)
        for p in made:
            shutil.copy2(p, dest / p.name)
        log(f"copied to {dest}")
    return made


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("narrate", "record"):
        sys.exit(__doc__)
    cut = a[a.index("--cut") + 1] if "--cut" in a else "both"
    cuts = ["walkthrough", "promo"] if cut == "both" else [cut]
    if a[0] == "narrate":
        narrate(cuts)
    else:
        record(cuts, "--desktop" in a)
