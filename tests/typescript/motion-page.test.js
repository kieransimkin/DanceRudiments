import test from 'node:test';
import assert from 'node:assert/strict';
import {mountCharacterMotion} from '../../examples/motion-packages/page-motion.mjs';
import {fixture,wasmBytes,deferred,until} from './motion-package-fixtures.js';

function pageFixture() {
  const f=fixture(), source='a'.repeat(64), poses=[], errors=[];
  f.assets.set('recording.wasm',wasmBytes);
  for(let index=0;index<2;index++) {
    f.manifest.clips[index].start_pip=-2+index*3;
    f.manifest.clips[index].metadata={clip_id:source,original_clip_id:source,chunk_index:index,
      chunk_count:2,total_sample_count:6,timing_kind:'time-only',timing_mode:'time-only'};
    f.recordings[index].clock.start_pip=-2+index*3;
    f.recordings[index].clock.bpm=60;
    f.recordings[index].clock.bpm_source='synthetic seconds coordinate';
    f.setRecording(index,f.recordings[index]);
  }
  let current=-2, listener;
  const clock={currentPip:()=>current,subscribe(callback){listener=callback;return()=>{listener=undefined;};}};
  const tick=pip=>{current=pip;listener?.(pip);};
  const options={manifestUrl:f.options.manifestUrl,packageId:f.options.packageId,
    wasmUrl:'https://motion.example/packs/fixture/recording.wasm',fetchAsset:f.options.fetch,
    rig:{target:f.options.expectedProfile,applyChannels(profile,values){poses.push([...values]);}},
    clock,selection:{sourceClipId:source},timing:'seconds-preview',onError:error=>errors.push(error)};
  return {...f,options,poses,errors,tick,subscribed:()=>Boolean(listener)};
}

test('page example loads one current chunk, ignores redundant ticks, and rejects stale seek completion',async()=>{
  const f=pageFixture(), gate=deferred(), stored=f.assets.get('clips/pulse.json');
  f.assets.set('clips/pulse.json',()=>gate.promise);
  const page=mountCharacterMotion(f.options);
  await until(()=>f.calls.some(call=>call.path==='clips/pulse.json'));
  f.tick(-1);f.tick(0);f.tick(-2);
  assert.equal(f.calls.filter(call=>call.path==='clips/pulse.json').length,1);
  assert.equal(f.calls.some(call=>call.path==='clips/sway.json'),false);
  const firstSignal=f.calls.find(call=>call.path==='clips/pulse.json').signal;
  f.tick(1);
  await until(()=>f.poses.length===1);
  assert.equal(firstSignal.aborted,true);
  assert.deepEqual(f.poses,[[-10,-5,false]]);
  gate.resolve(new Response(stored));
  await page.ready;
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(f.poses.length,1);
  f.tick(3);assert.deepEqual(f.poses.at(-1),[10,10,true]);
  f.tick(4);assert.equal(f.poses.length,2); // no looping beyond final chunk
  f.tick(1);await until(()=>f.calls.filter(call=>call.path==='clips/sway.json').length===2);
  await until(()=>f.poses.length===3); // out-of-range update unloaded the previous clip
  assert.deepEqual(f.errors,[]);
  page.dispose();assert.equal(f.subscribed(),false);
  f.tick(2);assert.equal(f.poses.length,3);
});

test('page example route abort cancels a pending clip and never applies its late result',async()=>{
  const f=pageFixture(), gate=deferred(), stored=f.assets.get('clips/pulse.json'), route=new AbortController();
  f.assets.set('clips/pulse.json',()=>gate.promise);
  const page=mountCharacterMotion({...f.options,signal:route.signal});
  await until(()=>f.calls.some(call=>call.path==='clips/pulse.json'));
  const request=f.calls.at(-1);
  route.abort();assert.equal(request.signal.aborted,true);assert.equal(f.subscribed(),false);
  gate.resolve(new Response(stored));await page.ready;
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(f.poses,[]);assert.deepEqual(f.errors,[]);page.dispose();
});

test('page example labels time-only preview, refuses musical claims, and checks complete contiguous chunks',async()=>{
  const musical=pageFixture(), page=mountCharacterMotion({...musical.options,timing:'music'});
  await assert.rejects(page.ready,/explicit source tempo and beat phase/);
  assert.equal(musical.calls.some(call=>call.path.startsWith('clips/')),false);
  assert.equal(musical.subscribed(),false);
  const gap=pageFixture();gap.manifest.clips[1].start_pip=2;gap.updateManifest();
  const incomplete=mountCharacterMotion(gap.options);
  await assert.rejects(incomplete.ready,/complete contiguous chunk manifest/);
  assert.equal(gap.calls.some(call=>call.path.startsWith('clips/')),false);
});

test('page example reports one failed load until explicit retry, without a per-frame retry loop',async()=>{
  const f=pageFixture(), stored=f.assets.get('clips/pulse.json');
  f.assets.set('clips/pulse.json',()=>new Response('unavailable',{status:503}));
  const page=mountCharacterMotion(f.options);await page.ready;
  assert.equal(f.errors.length,1);assert.deepEqual(f.poses,[]);
  for(let index=0;index<20;index++)f.tick(-1);
  assert.equal(f.calls.filter(call=>call.path==='clips/pulse.json').length,1);
  f.assets.set('clips/pulse.json',stored);await page.retry();
  assert.equal(f.calls.filter(call=>call.path==='clips/pulse.json').length,2);
  assert.deepEqual(f.poses,[[2.5,5,true]]);page.dispose();
});
