/**
 * Render each line of ios/narration.txt to its own mp3 through the ElevenLabs
 * client in ~/projects/dailylocks-studio (its .env holds the key and voice).
 *
 *   cd /Users/cv/projects/dailylocks-studio && npx tsx /Users/cv/projects/cfb-gameday/ios/narrate.mts [speed] [--only N]
 *
 * --only N re-renders one line and patches it into index.json.
 *
 * Writes ios/review/lines/NN.mp3 + NN.json and ios/review/lines/index.json.
 * Spends real credits: one per character, about 800 for the whole file.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { readFileSync } from "node:fs";
import { synthesize } from "/Users/cv/projects/dailylocks-studio/src/lib/elevenlabs/index.ts";

const STUDIO = "/Users/cv/projects/dailylocks-studio";
const HERE = "/Users/cv/projects/cfb-gameday/ios";

for (const line of readFileSync(join(STUDIO, ".env"), "utf8").split("\n")) {
  const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim();
}

const argv = process.argv.slice(2);
const onlyIdx = argv.indexOf("--only");
const only = onlyIdx >= 0 ? Number(argv[onlyIdx + 1]) : 0;
const speed = Number(argv.find((a) => /^[0-9.]+$/.test(a)) ?? "0.9");
const lines = (await readFile(join(HERE, "narration.txt"), "utf8"))
  .split("\n").map((s) => s.trim()).filter(Boolean);
const dir = join(HERE, "review", "lines");
await mkdir(dir, { recursive: true });

type Entry = { n: number; file: string; durationSec: number; credits: number; text: string };
let index: Entry[] = [];
if (only) index = JSON.parse(await readFile(join(dir, "index.json"), "utf8")).lines;
let credits = 0;
for (const [i, text] of lines.entries()) {
  if (only && i + 1 !== only) continue;
  const n = String(i + 1).padStart(2, "0");
  const r = await synthesize(text, { speed });
  await writeFile(join(dir, `${n}.mp3`), r.audio);
  await writeFile(join(dir, `${n}.json`), JSON.stringify({ text, durationSec: r.durationSec, words: r.words }, null, 2));
  const entry: Entry = { n: i + 1, file: `${n}.mp3`, durationSec: r.durationSec, credits: r.credits, text };
  index = [...index.filter((e) => e.n !== entry.n), entry].sort((a, b) => a.n - b.n);
  credits += r.credits;
  console.log(`${n}  ${r.durationSec.toFixed(2)}s  ${text.slice(0, 60)}`);
}
await writeFile(join(dir, "index.json"), JSON.stringify({ speed, credits, lines: index }, null, 2) + "\n");
console.log(`\n${index.length} lines, ${credits} credits this run, ${index.reduce((a, l) => a + l.durationSec, 0).toFixed(1)}s of speech`);
console.log(`voice ${process.env.ELEVENLABS_VOICE_ID}, speed ${speed}`);
