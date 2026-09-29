// Run with node --test tests/typescript/initial-wasm.test.mjs. No npm dependencies.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const root=new URL('../../',import.meta.url);
const read=path=>readFileSync(new URL(path,root),'utf8');
const pack=JSON.parse(read('python/dancerudiments_authoring/packs/initial.json'));
const descriptor=JSON.parse(read('collections/initial/preview_wasm.json'));
const bytes=Buffer.from(descriptor.data,'base64');
const {instance}=await WebAssembly.instantiate(bytes,{});
const native=instance.exports;

test('WASM bytes are pinned and have no network/runtime imports',()=>{
  assert.equal(createHash('sha256').update(bytes).digest('hex'),descriptor.wasm_sha256);
  assert.deepEqual(WebAssembly.Module.imports(new WebAssembly.Module(bytes)),[]);
});

test('real compiled C++/WASM agrees with every JSON sample and negative seek',()=>{
  assert.equal(native.pattern_count(),28);
  for (let i=0;i<pack.patterns.length;i++) {
    const p=pack.patterns[i];assert.equal(native.pattern_period(i),p.period_pips);
    const positions=Array.from({length:2*p.period_pips},(_,j)=>j-p.period_pips);
    positions.push(-2147483648,2147483647);
    for (const pip of positions) {
      const wrapped=((pip%p.period_pips)+p.period_pips)%p.period_pips;
      for(let axis=0;axis<3;axis++) assert.equal(native.sample_component(i,pip,axis),p.samples[wrapped][axis],p.name);
    }
  }
});

test('invalid C++/WASM bank requests fail predictably',()=>{
  assert.equal(native.pattern_period(-1),0);assert.equal(native.pattern_period(28),0);
  for(const [i,axis] of [[-1,0],[28,0],[0,-1],[0,3]]) assert.ok(Number.isNaN(native.sample_component(i,0,axis)));
});

test('the standalone gallery embeds the same native module and pack',()=>{
  const html=read('harness/initial-collection.html');
  const match=html.match(/<script type="application\/json" id="data">([\s\S]*?)<\/script>/);
  const payload=JSON.parse(match[1]);
  assert.equal(payload.wasm,descriptor.data);assert.deepEqual(payload.pack,pack);
  assert.equal(payload.collection_id,'initial-01');
  assert.ok(!html.includes('/*__APP__*/'));assert.ok(!html.includes('__PAYLOAD__'));
});
