// Synthetic assets only. Playback uses the checked-in C++ recording WASM.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  catalogue as defaultCatalogue, createMotionPackageLoader, createRecordingWasmAdapter,
} from '../../dist/typescript/index.js';
import {realFactory, digest, channel, profileBytes, fixture, observedFactory, deferred, until, abort, syntheticType} from './motion-package-fixtures.js';

test('module import and loader creation do not fetch or register motion payloads', () => {
  const f = fixture(), before = defaultCatalogue.length;
  const loader = createMotionPackageLoader(f.options);
  assert.deepEqual(f.calls,[]);
  assert.equal(defaultCatalogue.length,before);
  assert.ok(!defaultCatalogue.some(item => item.name === 'pulse'));
  loader.dispose();
  assert.deepEqual(f.calls,[]);
});

test('catalogue requests only the small manifest and returns frozen metadata', async () => {
  const f=fixture(), loader=createMotionPackageLoader(f.options);
  try {
    const manifest=await loader.catalogue();
    assert.deepEqual(f.calls.map(call=>call.path),['manifest.json']);
    assert.strictEqual(await loader.catalogue(),manifest);
    assert.ok(Object.isFrozen(manifest)); assert.ok(Object.isFrozen(manifest.clips));
    assert.ok(Object.isFrozen(manifest.clips[0].metadata.tags));
    assert.equal(manifest.clips[0].metadata.timing_kind,'music');
    assert.ok(!('samples' in manifest.clips[0]));
  } finally {loader.dispose();}
});

test('requested clip uses real C++ WASM at absolute negative pips and decodes physical channels', async () => {
  const f=fixture(), state=observedFactory(), loader=createMotionPackageLoader({...f.options,nativeFactory:state.factory});
  try {
    const motion=await loader.load('pulse');
    assert.deepEqual(f.calls.map(call=>call.path),['manifest.json','profile.json','clips/pulse.json']);
    assert.equal(state.created,1);
    assert.deepEqual(motion.sampleNormalized(-2),[-1,-0.5,-1]);
    assert.deepEqual(motion.sample(-2),[-10,-5,false]);
    assert.deepEqual(motion.sample(-1),[2.5,5,true]);
    assert.deepEqual(motion.sample(0),[10,10,true]);
    assert.deepEqual(state.sampled,[-2,-2,-1,0]);
    assert.equal(motion.clock.beat_zero_seconds,0.125);
    assert.equal(motion.sampleCount,3); assert.equal(motion.startPip,-2);
    for (const pip of [-3,1]) assert.throws(()=>motion.sample(pip),/outside non-looping/);
    for (const pip of [0.5,NaN,Infinity,2147483648,-2147483649]) assert.throws(()=>motion.sample(pip),/integer/);
  } finally {loader.dispose();}
  assert.equal(state.disposed,1);
});

test('concurrent same-clip requests deduplicate fetches and the native handle', async () => {
  const f=fixture(), state=observedFactory(), loader=createMotionPackageLoader({...f.options,nativeFactory:state.factory});
  try {
    const results=await Promise.all(Array.from({length:25},()=>loader.load('pulse')));
    assert.ok(results.every(result=>result===results[0]));
    assert.equal(f.calls.length,3); assert.equal(state.created,1);
    assert.strictEqual(await loader.load('pulse'),results[0]);
    assert.equal(f.calls.length,3);
  } finally {loader.dispose();}
});

test('different clips share only their own loader manifest/profile, with no global cache', async () => {
  const f=fixture(), state=observedFactory();
  const a=createMotionPackageLoader({...f.options,nativeFactory:state.factory});
  const b=createMotionPackageLoader({...f.options,nativeFactory:state.factory});
  try {
    const [first,second]=await Promise.all([a.load('pulse'),a.load('sway')]);
    assert.notStrictEqual(first,second);
    assert.equal(f.calls.filter(call=>call.path==='profile.json').length,1);
    const other=await b.load('pulse');
    assert.notStrictEqual(other,first);
    assert.equal(f.calls.filter(call=>call.path==='profile.json').length,2);
    assert.equal(f.calls.filter(call=>call.path==='manifest.json').length,2);
    assert.equal(state.created,3);
    a.dispose(); assert.equal(first.disposed,true); assert.equal(other.disposed,false);
    assert.deepEqual(other.sample(-2),[-10,-5,false]);
  } finally {a.dispose();b.dispose();}
  assert.equal(state.disposed,3);
});

test('gzip clips verify stored bytes and decode to the same actual native recording', async () => {
  const f=fixture({encoding:'gzip'}), loader=createMotionPackageLoader(f.options);
  try {
    const motion=await loader.load('pulse');
    assert.deepEqual(motion.sampleNormalized(-1),[0.25,0.5,1]);
    assert.ok(f.manifest.clips[0].byte_length<f.manifest.clips[0].decoded_byte_length);
    assert.equal(f.calls.at(-1).path,'clips/pulse.json.gz');
  } finally {loader.dispose();}
});

test('already aborted catalogue/load calls perform no fetch', async () => {
  const f=fixture(), loader=createMotionPackageLoader(f.options), controller=new AbortController();
  controller.abort();
  await abort(loader.catalogue({signal:controller.signal}));
  await abort(loader.load('pulse',{signal:controller.signal}));
  assert.deepEqual(f.calls,[]);loader.dispose();
});

test('one caller abort does not cancel another caller sharing a clip load', async () => {
  const f=fixture(), gate=deferred(), stored=f.assets.get('clips/pulse.json');
  f.assets.set('clips/pulse.json',()=>gate.promise);
  const loader=createMotionPackageLoader(f.options), controller=new AbortController();
  const cancelled=loader.load('pulse',{signal:controller.signal});
  const rejected=abort(cancelled), survivor=loader.load('pulse');
  await until(()=>f.calls.some(call=>call.path==='clips/pulse.json'));
  controller.abort();await rejected;
  assert.equal(f.calls.at(-1).signal.aborted,false);
  gate.resolve(new Response(stored));
  const motion=await survivor;
  assert.deepEqual(motion.sample(0),[10,10,true]);
  assert.equal(f.calls.filter(call=>call.path==='clips/pulse.json').length,1);
  loader.dispose();
});

test('all callers abort the shared fetch and a later request starts a clean retry', async () => {
  const f=fixture(), gate=deferred(), stored=f.assets.get('clips/pulse.json');
  f.assets.set('clips/pulse.json',()=>gate.promise);
  const loader=createMotionPackageLoader(f.options), first=new AbortController(), second=new AbortController();
  const a=abort(loader.load('pulse',{signal:first.signal})), b=abort(loader.load('pulse',{signal:second.signal}));
  await until(()=>f.calls.some(call=>call.path==='clips/pulse.json'));
  const oldSignal=f.calls.at(-1).signal;
  first.abort(); second.abort(); await Promise.all([a,b]);
  assert.equal(oldSignal.aborted,true);
  f.assets.set('clips/pulse.json',stored);
  const motion=await loader.load('pulse');
  gate.resolve(new Response(stored));
  await new Promise(resolve=>setImmediate(resolve));
  assert.strictEqual(await loader.load('pulse'),motion);
  assert.equal(f.calls.filter(call=>call.path==='clips/pulse.json').length,2);
  loader.dispose();
});

test('unload cancels an in-flight clip and stale completion cannot replace its retry', async () => {
  const f=fixture(), gate=deferred(), stored=f.assets.get('clips/pulse.json');
  f.assets.set('clips/pulse.json',()=>gate.promise);
  const loader=createMotionPackageLoader(f.options), cancelled=abort(loader.load('pulse'));
  await until(()=>f.calls.some(call=>call.path==='clips/pulse.json'));
  loader.unload('pulse');await cancelled;
  f.assets.set('clips/pulse.json',stored);
  const latest=await loader.load('pulse');
  gate.resolve(new Response(stored));
  await new Promise(resolve=>setImmediate(resolve));
  assert.strictEqual(await loader.load('pulse'),latest);
  loader.dispose();
});

test('dispose rejects pending native creation immediately and frees a late native result', async () => {
  const f=fixture(), gate=deferred(), entered=deferred();let released=0;
  const nativeFactory=async (recording,options)=>{
    const native=await realFactory(recording,options); entered.resolve(); await gate.promise;
    return {sample:pip=>native.sample(pip),dispose(){released++;native.dispose();}};
  };
  const loader=createMotionPackageLoader({...f.options,nativeFactory}), cancelled=abort(loader.load('pulse'));
  await entered.promise;loader.dispose();await cancelled;
  gate.resolve();await until(()=>released===1);
  await assert.rejects(loader.load('pulse'),/disposed/);
  await assert.rejects(loader.catalogue(),/disposed/);
  loader.dispose();assert.equal(released,1);
});

test('HTTP failure and native factory rejection are evicted and retryable', async () => {
  const f=fixture(), stored=f.assets.get('clips/pulse.json');
  f.assets.set('clips/pulse.json',()=>new Response('unavailable',{status:503}));
  let fail=true;
  const loader=createMotionPackageLoader({...f.options,nativeFactory:(recording,options)=>{
    if (fail) {fail=false;return Promise.reject(undefined);}
    return realFactory(recording,options);
  }});
  await assert.rejects(loader.load('pulse'),/503/);
  f.assets.set('clips/pulse.json',stored);
  await assert.rejects(loader.load('pulse'),error=>error===undefined);
  const motion=await loader.load('pulse');
  assert.deepEqual(motion.sample(0),[10,10,true]);
  assert.equal(f.calls.filter(call=>call.path==='manifest.json').length,1);
  assert.equal(f.calls.filter(call=>call.path==='profile.json').length,1);
  loader.dispose();
});

test('unload invalidates shared handles, releases native memory, and refetches only that clip', async () => {
  const f=fixture(), state=observedFactory(), loader=createMotionPackageLoader({...f.options,nativeFactory:state.factory});
  const motion=await loader.load('pulse');
  loader.unload('pulse');loader.unload('pulse');
  assert.equal(motion.disposed,true);assert.equal(state.disposed,1);
  assert.throws(()=>motion.sample(0),/unloaded/);
  const next=await loader.load('pulse');
  assert.notStrictEqual(next,motion);
  assert.equal(f.calls.filter(call=>call.path==='profile.json').length,1);
  assert.equal(f.calls.filter(call=>call.path==='clips/pulse.json').length,2);
  loader.dispose();loader.dispose();assert.equal(state.disposed,2);
});

test('dispose releases other clips even when a supplied native destructor throws', async () => {
  const f=fixture();let released=0;
  const loader=createMotionPackageLoader({...f.options,nativeFactory:async (recording,options)=>{
    const native=await realFactory(recording,options);
    return {sample:pip=>native.sample(pip),dispose(){native.dispose();released++;if(recording.name==='pulse')throw Error('destructor');}};
  }});
  const [first,second]=await Promise.all([loader.load('pulse'),loader.load('sway')]);
  assert.throws(()=>loader.dispose(),/destructor/);
  assert.equal(first.disposed,true);assert.equal(second.disposed,true);assert.equal(released,2);
  loader.dispose();await assert.rejects(loader.load('sway'),/disposed/);
});

test('unknown clips fetch only the manifest and never allocate playback state', async () => {
  const f=fixture(), loader=createMotionPackageLoader(f.options);
  await assert.rejects(loader.load('missing'),/Unknown motion clip/);
  assert.deepEqual(f.calls.map(call=>call.path),['manifest.json']);loader.dispose();
});

test('package identity, target fingerprint, type, and ordered dimensions are mandatory', async () => {
  for (const change of [options=>options.packageId='other',options=>options.expectedProfile.sha256='a'.repeat(64),
    options=>options.expectedProfile.typeUri=syntheticType+'/other',options=>options.expectedProfile.dimensions=['root_y','root_x','ik_on']]) {
    const f=fixture(), options={...f.options,expectedProfile:{...f.options.expectedProfile}};change(options);
    const loader=createMotionPackageLoader(options);
    await assert.rejects(loader.load('pulse'),/mismatch/);
    assert.deepEqual(f.calls.map(call=>call.path),['manifest.json']);loader.dispose();
  }
});

test('semantic synny alias is canonicalized without creating another profile identity', async () => {
  const f=fixture(), loader=createMotionPackageLoader({...f.options,expectedProfile:{...f.options.expectedProfile,typeUri:syntheticType.replace('syn://','synny://')}});
  assert.equal((await loader.load('pulse')).profile.type_uri,syntheticType);loader.dispose();
});

test('manifest and stored asset SHA-256 checks reject same-sized tampering before native allocation', async () => {
  for (const path of ['manifest.json','profile.json','clips/pulse.json']) {
    const f=fixture(), state=observedFactory(), original=f.assets.get(path);
    const damaged=Buffer.from(original);damaged[damaged.length-1]^=1;f.assets.set(path,damaged);
    const options={...f.options,nativeFactory:state.factory};
    if(path==='manifest.json')options.manifestSha256=digest(original);
    const loader=createMotionPackageLoader(options);
    await assert.rejects(loader.load('pulse'),/SHA-256 integrity mismatch/);
    assert.equal(state.created,0);loader.dispose();
  }
});

test('corrupt profile requests are retryable after their bytes are restored', async () => {
  const f=fixture(), original=f.assets.get('profile.json');
  f.assets.set('profile.json',Buffer.alloc(original.length));
  const loader=createMotionPackageLoader(f.options);
  await assert.rejects(loader.load('pulse'),/integrity/);
  f.assets.set('profile.json',original);
  assert.equal((await loader.load('pulse')).sampleCount,3);
  assert.equal(f.calls.filter(call=>call.path==='profile.json').length,2);loader.dispose();
});

test('bounded streaming rejects misleading Content-Length and oversized streamed content', async () => {
  for (const header of ['999999999','1']) {
    const f=fixture(), original=f.assets.get('clips/pulse.json');let cancelled=false;
    f.assets.set('clips/pulse.json',()=>new Response(new ReadableStream({
      start(controller){controller.enqueue(new Uint8Array(original.length+1));},
      cancel(){cancelled=true;},
    }),{headers:{'Content-Length':header}}));
    const loader=createMotionPackageLoader(f.options);
    await assert.rejects(loader.load('pulse'),/byte length|resource limit/);
    assert.equal(cancelled,true);loader.dispose();
  }
});

test('truncated stored files and decoded gzip size mismatches fail before playback', async () => {
  const f=fixture(), stored=f.assets.get('clips/pulse.json');f.assets.set('clips/pulse.json',stored.subarray(0,stored.length-1));
  const plain=createMotionPackageLoader(f.options);await assert.rejects(plain.load('pulse'),/byte length mismatch/);plain.dispose();
  for(const adjustment of [-1,1]) {
    const g=fixture({encoding:'gzip'});g.manifest.clips[0].decoded_byte_length+=adjustment;g.updateManifest();
    const loader=createMotionPackageLoader(g.options);
    await assert.rejects(loader.load('pulse'),/byte length|resource limit/);loader.dispose();
  }
});

test('manifest rejects paths, excessive native extents, duplicate IDs, invalid timing and unknown fields', async () => {
  const mutations=[
    m=>m.clips[0].path='../outside.json',m=>m.clips[0].path='https://other.example/motion.json',
    m=>m.clips[0].path='clips/%2e%2e/outside.json',m=>m.clips[0].path='clips/pulse.json?key=value',
    m=>m.profile.path='manifest.json',m=>m.clips[0].path='LICENSE.txt',m=>m.clips[0].path='readme.MD',
    m=>m.clips[0].path='THIRD_PARTY_NOTICES.md',m=>m.clips[0].path='SOURCES.json',
    m=>m.clips[1].path='clips/PULSE.json',m=>m.title=' ',m=>m.title='a'.repeat(1025),
    m=>m.clips[0].sample_count=8_388_608,m=>m.clips[0].start_pip=2147483646,
    m=>m.clips[1].id='pulse',m=>m.clips[1].path=m.clips[0].path,
    m=>m.clips[0].decoded_byte_length=64*1024*1024+1,m=>m.clips[0].encoding='br',
    m=>m.clips[0].metadata.timing_kind='guessed',m=>m.version='01.0.0',
    m=>m.version='1.0.0-01',m=>m.default=true,m=>m.profile.sha256='a'.repeat(64),
    m=>m.clips[0].decoded_byte_length++,
  ];
  for (const mutate of mutations) {
    const f=fixture();mutate(f.manifest);f.updateManifest();
    const loader=createMotionPackageLoader(f.options);await assert.rejects(loader.load('pulse'));
    assert.deepEqual(f.calls.map(call=>call.path),['manifest.json']);loader.dispose();
  }
});

test('duplicate JSON keys, including escaped aliases, are rejected', async () => {
  for(const target of ['manifest','recording']) {
    const f=fixture();
    if(target==='manifest') {
      f.assets.set('manifest.json',Buffer.from(f.assets.get('manifest.json').toString().replace('"schema_version":1','"schema_version":9,"schema_version":1')));
    } else {
      const clip=f.manifest.clips[0];
      const raw=Buffer.from(f.assets.get(clip.path).toString().replace('"name":"pulse"','"name":"bad","\\u006eame":"pulse"'));
      f.assets.set(clip.path,raw);clip.sha256=digest(raw);clip.byte_length=raw.length;clip.decoded_byte_length=raw.length;f.updateManifest();
    }
    const loader=createMotionPackageLoader(f.options);await assert.rejects(loader.load('pulse'),/Duplicate JSON key/);loader.dispose();
  }
});

test('recording identity, clock, dimensions, sample precision and discrete semantics are checked', async () => {
  const mutations=[r=>r.name='other',r=>r.dimensions.reverse(),r=>r.clock.start_pip=0,
    r=>r.clock.bpm=0,r=>r.clock.bpm_source=' ',r=>delete r.clock.phase_status,
    r=>r.pips_per_beat=32,r=>r.sample_dtype='float32',r=>r.samples.pop(),
    r=>r.samples[0].pop(),r=>r.samples[0][0]=1.01,r=>r.samples[0][0]=0.1234567890123,
    r=>r.samples[0][2]=0,r=>r.unexpected='field'];
  for(const mutate of mutations) {
    const f=fixture(), state=observedFactory();mutate(f.recordings[0]);f.setRecording(0,f.recordings[0]);
    const loader=createMotionPackageLoader({...f.options,nativeFactory:state.factory});
    await assert.rejects(loader.load('pulse'));assert.equal(state.created,0);loader.dispose();
  }
});

test('profile numbering, bindings, range, value types and enum constraints are checked', async () => {
  const mutations=[p=>p.channels[1].number=1,p=>p.channels[1].array_index=0,
    p=>p.channels[0].maximum=-10,p=>p.channels[0].neutral=99,p=>p.channels[2].interpolation='linear',
    p=>p.channels[0].value_type=null,p=>p.channels[0].enum_items=null,
    p=>p.channels[2].minimum=-1,p=>p.channels[0].enum_items=[[0,'zero']],
    p=>p.channels[0].rotation_mode='INVALID'];
  for(const mutate of mutations) {
    const f=fixture({transformProfile:mutate}), loader=createMotionPackageLoader(f.options);
    await assert.rejects(loader.load('pulse'));
    assert.ok(!f.calls.some(call=>call.path==='clips/pulse.json'));loader.dispose();
  }
});

test('quaternion groups retain wxyz components, reject missing components and non-unit rows', async () => {
  const make=(badRow=false,missing=false)=>fixture({transformProfile:p=>{
    p.channels=Array.from({length:missing?3:4},(_,i)=>channel(i+1,`rotation_${i}`,{
      data_path:'rotation_quaternion',array_index:i,unit:'quaternion',minimum:-1,maximum:1,
      neutral:i===0?1:0,interpolation:'quaternion',rotation_mode:'QUATERNION'}));
  },transformRecording:r=>{r.samples=Array.from({length:3},()=>badRow?[0,0,0,0]:[1,0,0,0]);}});
  const good=make(), loader=createMotionPackageLoader(good.options);
  assert.deepEqual((await loader.load('pulse')).sample(-1),[1,0,0,0]);loader.dispose();
  for(const f of [make(true),make(false,true)]) {
    const bad=createMotionPackageLoader(f.options);await assert.rejects(bad.load('pulse'),/quaternion|Quaternion/);bad.dispose();
  }
});

test('canonical profiles use ASCII bytes and do not accept raw UTF-8 substitutions', async () => {
  const f=fixture(), profile={...f.profile,model:'dancér'};
  const bytes=profileBytes(profile), hash=digest(bytes);f.assets.set('profile.json',bytes);
  f.manifest.profile={path:'profile.json',sha256:hash,byte_length:bytes.length};f.manifest.profile_sha256=hash;f.updateManifest();
  const loader=createMotionPackageLoader({...f.options,expectedProfile:{...f.options.expectedProfile,sha256:hash}});
  await assert.rejects(loader.load('pulse'),/ASCII/);loader.dispose();
});

test('the native adapter requires real WASM exports and never substitutes a JS sampler', async () => {
  assert.throws(()=>createRecordingWasmAdapter({}),/WebAssembly.Module/);
  const empty=await WebAssembly.compile(Uint8Array.from([0,97,115,109,1,0,0,0]));
  const f=fixture(), loader=createMotionPackageLoader({...f.options,nativeFactory:createRecordingWasmAdapter(empty)});
  await assert.rejects(loader.load('pulse'),/native recording sampler exports/);loader.dispose();
});

test('validated native input and returned metadata cannot be mutated after compatibility checks', async () => {
  const f=fixture();let passed;
  const loader=createMotionPackageLoader({...f.options,nativeFactory:(recording,options)=>{passed=recording;return realFactory(recording,options);}});
  const motion=await loader.load('pulse');
  for(const value of [passed,passed.clock,passed.dimensions,passed.samples,passed.samples[0],motion.profile,motion.profile.channels[0],motion.clock])
    assert.ok(Object.isFrozen(value));
  assert.throws(()=>{passed.samples[0][0]=0;},TypeError);
  assert.deepEqual(motion.sample(-2),[-10,-5,false]);loader.dispose();
});

test('time-only clips preserve their explicit metadata without claiming music beat annotations', async () => {
  const f=fixture();f.manifest.clips[0].metadata={timing_kind:'time-only',tempo_map:{bpm:60,source:'synthetic seconds coordinate'}};
  f.recordings[0].clock.bpm=60;f.recordings[0].clock.bpm_source='synthetic seconds coordinate';f.setRecording(0,f.recordings[0]);
  const loader=createMotionPackageLoader(f.options), motion=await loader.load('pulse');
  assert.equal(motion.metadata.timing_kind,'time-only');assert.equal(motion.clock.bpm,60);
  assert.deepEqual(motion.sample(-1),[2.5,5,true]);loader.dispose();
});
