"""Lay narration lines over the phone screen recording at the moments they describe.

    python3 scripts/review_mux.py ios/review/walkthrough-raw.mp4 ios/review/cues.txt

cues.txt: one line per narration line, "NN  seconds" where seconds is when that
beat starts on screen (from QuickTime or ffplay). Lines are ios/review/lines/NN.mp3
from ios/narrate.ts. The video track is copied untouched. Overlaps are reported
and the next cue is pushed back so lines never talk over each other.
"""
import json, subprocess, sys
from pathlib import Path

raw, cues_path = Path(sys.argv[1]), Path(sys.argv[2])
lines_dir = raw.parent / "lines"
out = raw.with_name("walkthrough.mp4")
index = {l["n"]: l for l in json.loads((lines_dir / "index.json").read_text())["lines"]}

def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

video_len = probe(raw)
cues = []
for ln in cues_path.read_text().splitlines():
    ln = ln.split("#")[0].strip()
    if ln:
        n, t = ln.split()
        cues.append((int(n), float(t)))

inputs, filters, labels, cursor = ["-i", str(raw)], [], [], 0.0
for i, (n, t) in enumerate(cues, start=1):
    dur = index[n]["durationSec"]
    if t < cursor:
        print(f"line {n:02d}: cue {t:.1f}s overlaps previous line, pushed to {cursor:.1f}s")
        t = cursor
    if t + dur > video_len:
        print(f"line {n:02d}: ends at {t + dur:.1f}s, past the video ({video_len:.1f}s)")
    cursor = t + dur + 0.3
    inputs += ["-i", str(lines_dir / index[n]["file"])]
    filters.append(f"[{i}:a]adelay={int(t * 1000)}|{int(t * 1000)}[a{i}]")
    labels.append(f"[a{i}]")
    print(f"line {n:02d}: {t:6.1f}s to {t + dur:6.1f}s")

mix = "".join(labels) + f"amix=inputs={len(labels)}:normalize=0,apad[aout]"
cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters + [mix]),
       "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
       "-shortest", str(out)]
subprocess.run(cmd, check=True, capture_output=True)
print(f"\nwrote {out} ({probe(out):.1f}s)")
