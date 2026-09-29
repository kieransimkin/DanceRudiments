// Kieran Simkin — https://kieransimkin.co.uk/my-songs/
import { bindNative, catalogue, sample } from "@kieransimkin/dance-rudiments";
import type { RudimentName } from "@kieransimkin/dance-rudiments";
import createDanceRudiments from "@kieransimkin/dance-rudiments/wasm";

async function main(): Promise<void> {
  const dot = document.querySelector<HTMLElement>("#dot");
  const button = document.querySelector<HTMLButtonElement>("#play");
  const tempo = document.querySelector<HTMLInputElement>("#bpm");
  const status = document.querySelector<HTMLElement>("#status");
  if (!dot || !button || !tempo || !status) throw new Error("Missing example elements");
  bindNative(await createDanceRudiments());
  const name: RudimentName = "beat_amen_four_bar_bounce";
  const info = catalogue.find(item => item.name === name);
  if (!info) throw new Error("This release lacks the example movement");
  status.textContent = `${catalogue.length} movements · ${info.periodPips / 64} beat loop`;
  let bpm = 120, beat = 0, origin = performance.now(), playing = false;
  const nowBeat = (now: number): number => beat + (playing ? (now - origin) * bpm / 60000 : 0);
  const pause = (): void => {
    beat = nowBeat(performance.now()); playing = false; button.textContent = "Play";
  };
  button.disabled = false;
  button.onclick = () => {
    if (playing) pause();
    else { origin = performance.now(); playing = true; button.textContent = "Pause"; }
  };
  tempo.onchange = () => {
    const next = Number(tempo.value);
    if (!Number.isFinite(next) || next < 20 || next > 300) { tempo.value = String(bpm); return; }
    const now = performance.now(); beat = nowBeat(now); origin = now; bpm = next;
  };
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  // Start paused for everyone; a reduced-motion request also pauses live motion.
  matchMedia("(prefers-reduced-motion: reduce)").addEventListener("change", event => { if (event.matches) pause(); });
  const frame = (now: number): void => {
    // Reduce modulo THIS movement's period before crossing the int32 boundary.
    const pip = Math.floor(nowBeat(now) * 64) % info.periodPips;
    const v = sample(name, pip);
    dot.style.transform = `translate3d(${v.x * 70}px, ${v.y * 70}px, 0)`;
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
main().catch(error => {
  const status = document.querySelector("#status");
  if (status) status.textContent = `Could not load C++/WASM: ${String(error)}`;
  console.error(error);
});
