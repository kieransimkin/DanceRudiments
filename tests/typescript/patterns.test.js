// Wrapper contract tests. The separate wasm-smoke.mjs tests the actual C++ WASM.
import test from 'node:test';
import assert from 'node:assert/strict';
import { bindNative, createPatternLibrary, sample } from '../../dist/typescript/index.js';

function pack() {
  return {format:'dancerudiments.compiled-pack', schema_version:1, pips_per_beat:64, patterns:[{
    name:'custom', description:'test', period_pips:2, samples:[[0,0,0],[1,-.5,0]],
    source_sha256:'a'.repeat(64), provenance:{license:'MIT'}, diagnostics:{}
  }]};
}
function mock({fail=false}={}) {
  const calls=[];
  let alive=0;
  class Offsets {
    constructor(){this.rows=[];alive++;}
    push_back(v){this.rows.push(v);}
    delete(){alive--;}
  }
  class Pattern {
    constructor(name,description,values){this.name=name;this.rows=[...values.rows];alive++;}
    delete(){alive--;}
  }
  class Library {
    constructor(patterns){
      if(fail) throw new Error('construction failed');
      assert.equal(patterns[0].rows.length,2);alive++;
    }
    sample(name,pip){calls.push([name,pip]);return {x:.25,y:.5,z:0};}
    delete(){alive--;}
  }
  return {module:{sample:(name,pip)=>({x:0,y:0,z:0}), OffsetVector:Offsets,
                  SampledPattern:Pattern, PatternLibrary:Library},
          alive:()=>alive, calls};
}

test('requires a native implementation; there is no JavaScript sampling fallback',()=>{
  bindNative({sample(){}});
  assert.throws(()=>createPatternLibrary(pack()),/sampled-pattern/);
});
test('delegates sampling to C++, owns one handle, disposes idempotently',()=>{
  const m=mock();bindNative(m.module);
  const library=createPatternLibrary(pack());
  assert.equal(m.alive(),1);
  assert.deepEqual(library.sample('custom',-1),{x:.25,y:.5,z:0});
  assert.deepEqual(m.calls,[['custom',-1]]);
  assert.equal(library.catalogue().length,68);
  assert.equal(library.catalogue().at(-1).dimensions,2);
  library.dispose();library.dispose();assert.equal(m.alive(),0);
  assert.throws(()=>library.sample('custom',0),/disposed/);
});
test('rejects fractional and overflowing pips before crossing WASM boundary',()=>{
  const m=mock();bindNative(m.module);const library=createPatternLibrary(pack());
  try {
    for(const pip of [.5,NaN,Infinity,2147483648,-2147483649]) {
      assert.throws(()=>library.sample('custom',pip),/32-bit/);
      assert.throws(()=>sample('circle',pip),/32-bit/);
    }
    library.sample('custom',-2147483648);
    library.sample('custom',2147483647);
  } finally {library.dispose();}
});
test('validates data and collisions before allocating native objects',()=>{
  const m=mock();bindNative(m.module);
  const changes=[p=>p.pips_per_beat=16,p=>p.patterns[0].period_pips=3,
    p=>p.patterns[0].name='circle',p=>p.patterns[0].samples[0][0]=NaN,
    p=>p.patterns[0].samples[0][2]=2,p=>p.patterns.push(p.patterns[0]),
    p=>p.patterns[0].source_sha256='bad'];
  for(const change of changes){const p=pack();change(p);assert.throws(()=>createPatternLibrary(p));}
  assert.equal(m.alive(),0);
});
test('frees intermediate objects if the native bank constructor throws',()=>{
  const m=mock({fail:true});bindNative(m.module);
  assert.throws(()=>createPatternLibrary(pack()),/construction failed/);
  assert.equal(m.alive(),0);
});
test('rebinding global native module does not redirect an existing bank',()=>{
  const m=mock();bindNative(m.module);const library=createPatternLibrary(pack());
  bindNative({sample(){throw new Error('wrong runtime');}});
  try {library.sample('custom',0);assert.equal(m.calls.length,1);}
  finally {library.dispose();}
});
test('returns frozen catalogue metadata and rejects unknown names',()=>{
  const m=mock();bindNative(m.module);const library=createPatternLibrary(pack());
  try {
    assert.ok(Object.isFrozen(library.catalogue()));
    assert.ok(Object.isFrozen(library.catalogue().at(-1)));
    assert.throws(()=>library.sample('missing',0),/Unknown/);
  } finally {library.dispose();}
});
