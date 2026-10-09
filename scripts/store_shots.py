#!/usr/bin/env python3
"""Captioned App Store screenshots from raw simulator captures.

    python3 scripts/store_shots.py RAW_DIR OUT_DIR

RAW_DIR holds simulator screenshots named <device>-<n>-<slug>.png, where device is
iphone (1320x2868, 6.9") or ipad (2064x2752, 13"). Each becomes OUT_DIR/<device>-<n>-<slug>.png
at the same pixel size, and every iphone capture also gives an iphone65 one (1284x2778, 6.5"): a headline over the screenshot, rendered by headless Chrome
(the same route as icons/og.png), then flattened to RGB because App Store Connect
rejects alpha. Apple's rule (Guideline 2.3.3): captions are fine as long as the app
in use stays the main subject. No prices, URLs or betting language in the copy.
"""
import html
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SIZES = {"iphone": (1320, 2868), "iphone65": (1284, 2778), "ipad": (2064, 2752)}

CAPTIONS = {
    "board": ("Every FBS game", "The whole slate on one screen",
              "Kickoff time, venue, TV and the posted line for every game"),
    "weather": ("Kickoff weather", "Stadium weather at kickoff",
                "Wind, rain and heat flagged for every outdoor game"),
    "game": ("Game sheet", "Every score, drive and stat",
             "Scoring, box score, leaders and win probability"),
    "lines": ("Lines sheet", "Every posted line, side by side",
              "Spread, total and opener from ESPN's feed"),
    "tv": ("By network", "Find any game on TV",
           "Every game grouped by channel and streaming service"),
}

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:#0b1220;
  font-family:-apple-system,"SF Pro Display","Helvetica Neue",Arial,sans-serif;color:#f4f7fb}}
.bg{{position:absolute;inset:0;background:
  radial-gradient({gw}px {gh}px at 50% -6%,rgba(232,195,106,.20),transparent 70%),
  linear-gradient(180deg,#121c31 0%,#0b1220 55%)}}
.cap{{position:absolute;left:{pad}px;right:{pad}px;top:{top}px;text-align:center}}
.eyebrow{{color:#e8c36a;font-weight:800;letter-spacing:.2em;text-transform:uppercase;font-size:{eye}px}}
h1{{text-wrap:balance;margin:{gap}px 0 0;font-size:{head}px;line-height:1.04;letter-spacing:-.025em;font-weight:800}}
p{{text-wrap:balance;margin:{gap}px auto 0;max-width:{pmax}px;font-size:{sub}px;line-height:1.3;color:#aab7cc;font-weight:500}}
.shot{{position:absolute;left:50%;transform:translateX(-50%);top:{shot_top}px;width:{shot_w}px;
  border-radius:{radius}px;overflow:hidden;border:{border}px solid #2a3a5a;
  box-shadow:0 40px 120px rgba(0,0,0,.65),0 0 0 1px rgba(232,195,106,.08)}}
.shot img{{display:block;width:100%}}
</style></head><body><div class="bg"></div>
<div class="cap"><div class="eyebrow">{eyebrow}</div><h1>{headline}</h1><p>{sub_text}</p></div>
<div class="shot"><img src="{src}"></div></body></html>"""


def layout(device):
    # The whole screen fits, tab bar included, with a margin under it.
    if device.startswith("iphone"):
        return dict(pad=90, top=140, eye=40, head=104, sub=46, gap=26, pmax=1080,
                    shot_top=640, shot_w=985, radius=92, border=6, gw=1500, gh=1000)
    return dict(pad=160, top=120, eye=40, head=104, sub=46, gap=24, pmax=1500,
                shot_top=540, shot_w=1560, radius=52, border=6, gw=2200, gh=1000)


def render(raw: Path, out: Path, device: str):
    slug = raw.stem.split("-", 2)[2]
    w, h = SIZES[device]
    eyebrow, headline, sub_text = CAPTIONS[slug]
    page = PAGE.format(w=w, h=h, src=raw.resolve().as_uri(), eyebrow=html.escape(eyebrow),
                       headline=html.escape(headline), sub_text=html.escape(sub_text), **layout(device))
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "shot.html"
        png = Path(tmp) / "shot.png"
        src.write_text(page, "utf-8")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                        "--force-device-scale-factor=1", f"--window-size={w},{h}", f"--screenshot={png}", src.as_uri()],
                       check=True, capture_output=True)
        # RGB, exact size: App Store Connect refuses PNGs with an alpha channel.
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png), "-vf", f"crop={w}:{h}:0:0",
                        "-pix_fmt", "rgb24", str(out)], check=True)
    print(f"{out}  {w}x{h}")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    raw_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for raw in sorted(raw_dir.glob("*.png")):
        device = raw.stem.split("-", 1)[0]
        render(raw, out_dir / raw.name, device)
        if device == "iphone":   # the 6.5" set from the same capture
            render(raw, out_dir / raw.name.replace("iphone-", "iphone65-"), "iphone65")


if __name__ == "__main__":
    main()
