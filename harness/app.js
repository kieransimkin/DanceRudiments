import { catalogue, sample, wrapPip } from "./dancerudiments.js";

const grid = document.querySelector("#grid");
const bpm = document.querySelector("#bpm");
const amplitude = document.querySelector("#amplitude");
const playButton = document.querySelector("#play");
const pipSlider = document.querySelector("#pip");
const pipText = document.querySelector("#pip-text");
let playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
let absolutePip = 0, lastTime = performance.now(), accumulator = 0;

const cards = catalogue.map(info => {
  const card = document.createElement("article");
  card.className = "card";
  card.innerHTML = `<header><h2>${info.name.replaceAll("_"," ")}</h2><span>${info.periodPips} pips · ${info.dimensions}D</span></header><p>${info.description}</p><div class="stage"><div class="axes"></div><div class="subject" aria-hidden="true"></div><svg class="trail" viewBox="0 0 240 160" aria-hidden="true"><polyline/></svg></div><output></output>`;
  grid.append(card);
  const points = Array.from({length: info.periodPips}, (_, p) => {
    const v = sample(info.name, p); return `${120+v.x*88},${80+v.y*58}`;
  }).join(" ");
  card.querySelector("polyline").setAttribute("points", points);
  return { info, subject: card.querySelector(".subject"), output: card.querySelector("output") };
});

function render() {
  const amp = Number(amplitude.value);
  pipSlider.value = String(wrapPip(absolutePip, 256));
  pipText.textContent = String(absolutePip);
  for (const card of cards) {
    const local = wrapPip(absolutePip, card.info.periodPips), v = sample(card.info.name, absolutePip);
    card.subject.style.transform = `translate3d(${v.x*amp}px, ${v.y*amp}px, 0) scale(${1 + v.z*.08})`;
    card.output.textContent = `pip ${local}  x ${v.x.toFixed(3)}  y ${v.y.toFixed(3)}  z ${v.z.toFixed(3)}`;
  }
}

function frame(now) {
  const elapsed = Math.min(100, now-lastTime); lastTime = now;
  if (playing) {
    accumulator += elapsed;
    const pipMs = 60000 / Number(bpm.value) / 64;
    while (accumulator >= pipMs) { absolutePip++; accumulator -= pipMs; }
    render();
  }
  requestAnimationFrame(frame);
}
playButton.addEventListener("click", () => { playing=!playing; playButton.textContent=playing?"Pause":"Play"; lastTime=performance.now(); });
document.querySelector("#previous").addEventListener("click", () => { playing=false; playButton.textContent="Play"; absolutePip--; render(); });
document.querySelector("#next").addEventListener("click", () => { playing=false; playButton.textContent="Play"; absolutePip++; render(); });
pipSlider.addEventListener("input", () => { playing=false; playButton.textContent="Play"; absolutePip=Number(pipSlider.value); render(); });
playButton.textContent=playing?"Pause":"Play"; render(); requestAnimationFrame(frame);
