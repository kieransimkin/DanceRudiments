import test from 'node:test';
import assert from 'node:assert/strict';
import {createStandaloneRigMotion} from '../../dist/typescript/motion-packages.js';
import {fixture, observedFactory, deferred, until, abort} from './motion-package-fixtures.js';

function standalone() {
  const f=fixture(), state=observedFactory();
  const document={format:'dancerudiments.rig-motion',schema_version:1,
    type_uri:f.profile.type_uri,profile_sha256:f.manifest.profile_sha256,
    profile:structuredClone(f.profile),recording:structuredClone(f.recordings[0])};
  return {document,state,options:{profile:f.profile,profileSha256:f.manifest.profile_sha256,
    nativeFactory:state.factory},bytes:()=>Buffer.from(JSON.stringify(document))};
}

test('explicit standalone loading uses the existing C++ WASM and physical profile decoder', async()=>{
  const f=standalone(), loaded=await createStandaloneRigMotion(f.bytes(),f.options);
  assert.equal(loaded.motion.startPip,-2);assert.equal(loaded.motion.sampleCount,3);
  assert.deepEqual(loaded.motion.sample(-2),[-10,-5,false]);
  assert.deepEqual(loaded.motion.sampleNormalized(-1),[.25,.5,1]);
  assert.deepEqual(loaded.motion.sample(0),[10,10,true]);
  assert.deepEqual(f.state.sampled,[-2,-1,0]);
  assert.throws(()=>loaded.motion.sample(1),/outside non-looping/);
  loaded.dispose();loaded.dispose();assert.equal(f.state.disposed,1);
  assert.equal(loaded.motion.disposed,true);
  assert.throws(()=>loaded.motion.sample(-2),/disposed/);
});

test('claimed fingerprint cannot substitute changed profile channels or rest metadata',async()=>{
  for(const mutate of [
    d=>{d.profile.channels[0].maximum=20;},
    d=>{d.profile.source.synthetic=false;},
    d=>{d.profile_sha256='f'.repeat(64);},
    d=>{d.recording.dimensions.reverse();},
  ]){
    const f=standalone();mutate(f.document);
    await assert.rejects(createStandaloneRigMotion(f.bytes(),f.options),/profile|dimensions/);
    assert.equal(f.state.created,0);
  }
});

test('standalone validation rejects duplicate keys, invalid precision, discrete values and native bounds',async()=>{
  const f=standalone();
  const duplicate=Buffer.from(f.bytes().toString().replace('"schema_version":1','"schema_version":1,"schema_version":1'));
  await assert.rejects(createStandaloneRigMotion(duplicate,f.options),/Duplicate JSON key/);
  for(const mutate of [
    d=>{d.recording.samples[0][0]=1.01;},
    d=>{d.recording.samples[0][0]=.1234567890123;},
    d=>{d.recording.samples[0][2]=0;},
    d=>{d.recording.clock.start_pip=2147483646;},
    d=>{d.recording.clock.start_pip=-2147483649;},
  ]){
    const x=standalone();mutate(x.document);
    await assert.rejects(createStandaloneRigMotion(x.bytes(),x.options));
    assert.equal(x.state.created,0);
  }
});

test('aborting standalone native construction releases the returned handle exactly once',async()=>{
  const f=standalone(), gate=deferred(), controller=new AbortController();let entered=false;
  const pending=createStandaloneRigMotion(f.bytes(),{...f.options,signal:controller.signal,
    nativeFactory:async(recording,options)=>{
      const handle=await f.state.factory(recording,options);entered=true;await gate.promise;return handle;
    }});
  const rejected=abort(pending);
  await until(()=>entered);controller.abort();gate.resolve();await rejected;
  assert.equal(f.state.created,1);assert.equal(f.state.disposed,1);
});
