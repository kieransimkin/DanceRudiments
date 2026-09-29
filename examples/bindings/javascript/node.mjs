// Kieran Simkin — https://kieransimkin.co.uk/my-songs/
// With no arguments, use the npm package. Optional two paths test a local build.
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
const [wrapper, wasm] = process.argv.slice(2);
if (Boolean(wrapper) !== Boolean(wasm)) throw new Error("Supply BOTH wrapper and WASM-loader paths, or neither.");
const api = await import(wrapper ? pathToFileURL(resolve(wrapper)).href : "@kieransimkin/dance-rudiments");
const { default: createDanceRudiments } = await import(wasm ? pathToFileURL(resolve(wasm)).href : "@kieransimkin/dance-rudiments/wasm");
api.bindNative(await createDanceRudiments());
const name = "beat_amen_four_bar_bounce";
const info = api.catalogue.find(item => item.name === name);
if (!info) throw new Error("Installed release predates Club 05; use the current checkout.");
console.log(`JavaScript + C++/WASM: ${api.catalogue.length} movements`);
console.log(`${name}: ${info.periodPips / 64} beats`);
for (const pip of [-1, 0, 16, 32, 48, 64]) {
  const v = api.sample(name, pip);
  console.log(`pip ${pip} -> ${v.x.toFixed(6)}, ${v.y.toFixed(6)}, ${v.z.toFixed(6)}`);
}
console.log("Music: https://kieransimkin.co.uk/my-songs/");
