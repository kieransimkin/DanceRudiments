// Tests the actual native demo snapshot, not a JS motion implementation.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { catalogue, bindNative, createPatternLibrary } from '../../dist/typescript/index.js';
const pack=JSON.parse(fs.readFileSync(new URL('../../python/dancerudiments_authoring/packs/initial.json',import.meta.url)));
const wasm=JSON.parse(fs.readFileSync(new URL('../../collections/initial/preview_wasm.json',import.meta.url)));
const native=(await WebAssembly.instantiate(Buffer.from(wasm.data,'base64'),{})).instance.exports;
const indices=new Map(pack.patterns.map((p,i)=>[p.name,i]));
let alive=0;
const mock={
  sample(name,pip){const i=indices.get(name);return {x:native.sample_component(i,pip,0),y:native.sample_component(i,pip,1),z:native.sample_component(i,pip,2)};},
  OffsetVector:class {constructor(){alive++;} push_back(){} delete(){alive--; }},
  SampledPattern:class {constructor(){alive++;} delete(){alive--; }},
  PatternLibrary:class {constructor(){alive++;} sample(name,pip){return mock.sample(name,pip);} delete(){alive--;}}
};
test('default catalogue contains the 15 primitives and 628 unique sampled defaults',()=>{
  assert.equal(catalogue.length,643);assert.equal(new Set(catalogue.map(p=>p.name)).size,643);
  for(const p of pack.patterns)assert.equal(catalogue.find(x=>x.name===p.name).periodPips,p.period_pips);
});
test('loading the exact approved pack remains idempotent in the wrapper',()=>{
  bindNative(mock);const lib=createPatternLibrary(pack);
  assert.equal(lib.catalogue().length,643);assert.equal(alive,1);
  assert.deepEqual(lib.sample('lfo_breathe',-1),mock.sample('lfo_breathe',-1));
  lib.dispose();assert.equal(alive,0);
});
test('changed defaults are rejected before any native allocation',()=>{
  bindNative(mock);const changed=structuredClone(pack);changed.patterns[0].samples[10][0]=.123;
  assert.throws(()=>createPatternLibrary(changed),/override/);assert.equal(alive,0);
});
