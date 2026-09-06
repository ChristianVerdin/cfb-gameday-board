/**
 * Render each line of ios/narration.txt to its own mp3 through the ElevenLabs
 * client in ~/projects/dailylocks-studio (its .env holds the key and voice).
 *
 *   cd /Users/cv/projects/dailylocks-studio && npx tsx /Users/cv/projects/cfb-gameday/ios/narrate.mts [speed]
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

const speed = Number(process.argv[2] ?? "0.9");
const lines = (await readFile(join(HERE, "narration.txt"), "utf8"))
  .split("\n").map((s) => s.trim()).filter(Boolean);
const dir = join(HERE, "review", "lines");
await mkdir(dir, { recursive: true });

const index: { n: number; file: string; durationSec: number; credits: number; text: string }[] = [];
let credits = 0;
for (const [i, text] of lines.entries()) {
  const n = String(i + 1).padStart(2, "0");
  const r = await synthesize(text, { speed });
  await writeFile(join(dir, `${n}.mp3`), r.audio);
  await writeFile(join(dir, `${n}.json`), JSON.stringify({ text, durationSec: r.durationSec, words: r.words }, null, 2));
  index.push({ n: i + 1, file: `${n}.mp3`, durationSec: r.durationSec, credits: r.credits, text });
  credits += r.credits;
  console.log(`${n}  ${r.durationSec.toFixed(2)}s  ${text.slice(0, 60)}`);
}
await writeFile(join(dir, "index.json"), JSON.stringify({ speed, credits, lines: index }, null, 2) + "\n");
console.log(`\n${lines.length} lines, ${credits} credits, ${index.reduce((a, l) => a + l.durationSec, 0).toFixed(1)}s of speech`);
console.log(`voice ${process.env.ELEVENLABS_VOICE_ID}, speed ${speed}`);
