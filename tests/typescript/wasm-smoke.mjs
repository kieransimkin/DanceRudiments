// Run after compiling the wrapper, example pack, and actual Emscripten module:
// node tests/typescript/wasm-smoke.mjs build-wasm/dancerudiments.js generated/starter.json
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {bindNative, createPatternLibrary, catalogue} from '../../dist/typescript/index.js';

const modulePath=path.resolve(process.argv[2] ?? 'build-wasm/dancerudiments.js');
const packPath=path.resolve(process.argv[3] ?? 'generated/starter.json');
const createModule=(await import(pathToFileURL(modulePath).href)).default;
const wasmBinary=await fs.readFile(modulePath.replace(/\.js$/,'.wasm'));
const native=await createModule({wasmBinary});
bindNative(native);
const pack=JSON.parse(await fs.readFile(packPath,'utf8'));
const library=createPatternLibrary(pack);
try {
  assert.equal(library.catalogue().length, new Set([...catalogue.map(p=>p.name), ...pack.patterns.map(p=>p.name)]).size);
  for(const p of pack.patterns) {
    const positions=[-2147483648,2147483647];
    for(let i=-p.period_pips;i<=p.period_pips*2;i++)positions.push(i);
    for(const pip of positions.reverse()) {
      const v=library.sample(p.name,pip);
      const i=((pip%p.period_pips)+p.period_pips)%p.period_pips;
      assert.deepEqual([v.x,v.y,v.z],p.samples[i]);
    }
  }
  assert.deepEqual(library.sample('circle',64),native.sample('circle',0));
} finally {library.dispose();}
// Also exercise native (not merely wrapper) input rejection and exception support.
const offsets=new native.OffsetVector();
try {
  offsets.push_back({x:NaN,y:0,z:0});
  assert.throws(()=>new native.SampledPattern('bad','',offsets));
} finally {offsets.delete();}
console.log('Real WASM: every exported sample and arbitrary-seek check passed');
