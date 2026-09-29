import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import '../../tools/release_demo_assets/beat_player.js';
const {normalizeBeat,eventsBetween,midiRead,midiWrite,BeatTransport,rational}=globalThis.DanceBeat;
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const score={id:'test',title:'Test',period_beats:'4',bpm:120,meter:[4,4],events:[
 {beat:'0',lane:'kick',note:36,channel:9,velocity:1,duration:'1/16'},
 {beat:'1/3',lane:'snare',note:38,channel:9,velocity:.5,duration:'1/16'},
 {beat:'7/2',lane:'bass',note:40,channel:0,velocity:.8,duration:'1/4'}]};
const b=normalizeBeat(score);
function fakeContext(){return {currentTime:0,state:'suspended',destination:{},
 resume(){this.state='running';return Promise.resolve();},close(){this.state='closed';},addEventListener(){},
 createGain(){return {gain:{value:0,setTargetAtTime(){}},connect(){}};},
 createDynamicsCompressor(){return {threshold:{},knee:{},ratio:{},connect(){}};}};}

test('rational quarter notes, including genuine triplets and negative seeks',()=>{
 assert.equal(rational('1/3'),1/3);assert.equal(rational('-7/2'),-3.5);
 for(const value of ['1/0','x',null,NaN,Infinity,'1e6',true])assert.throws(()=>rational(value));
});
test('normalisation rejects malformed positions, velocities and note bytes',()=>{
 for(const e of [{beat:'4'},{beat:'-1'},{note:128},{channel:16},{velocity:0},{velocity:NaN},{duration:'0'}])
   assert.throws(()=>normalizeBeat({...score,events:[{...score.events[0],...e}]}));
 assert.throws(()=>normalizeBeat({...score,period_beats:'0'}));
});
test('half-open scheduling emits every event exactly once across windows',()=>{
 const whole=eventsBetween(b,-4,12);
 const parts=[...eventsBetween(b,-4,0),...eventsBetween(b,0,4),...eventsBetween(b,4,12)];
 assert.deepEqual(parts,whole);assert.equal(whole.length,12);
 assert.deepEqual(eventsBetween(b,3.99,4.01).map(x=>x.beat),[4]);
 assert.deepEqual(eventsBetween(b,-.01,.01).map(x=>x.beat),[0]);
});
test('SMF export preserves 4-beat end marker, triplets, channels, notes and tempo',()=>{
 const out=midiWrite(score,137);const parsed=midiRead(out.bytes);
 assert.equal(parsed.period,4);assert.equal(parsed.events.length,3);assert.equal(parsed.events[1].time,1/3);
 assert.equal(parsed.events[2].channel,0);assert.equal(parsed.events[2].note,40);
 assert.ok(Math.abs(parsed.bpm-137)<.001);assert.equal(out.maxTimingErrorBeats,0);
 assert.deepEqual(parsed.meter,[4,4]);assert.equal(parsed.events[0].velocity,1);
});
test('PPQ expands for sevenths; unsupported denominator combinations are bounded and reported',()=>{
 const seven={...score,events:[{...score.events[0],beat:'1/7'}]};
 const a=midiWrite(seven);assert.equal(a.ppq,6720);assert.equal(a.maxTimingErrorBeats,0);
 const huge={...score,events:[{...score.events[0],beat:'1/100003'}]};const c=midiWrite(huge);
 assert.equal(c.ppq,30720);assert.ok(c.maxTimingErrorBeats>0);assert.ok(c.maxTimingErrorBeats<=.5/c.ppq);
});
test('all truncated MIDI files fail rather than silently becoming shorter loops',()=>{
 const a=midiWrite(score).bytes;
 for(let i=0;i<a.length;i++)assert.throws(()=>midiRead(a.slice(0,i)),'prefix '+i);
});
test('type 2 and SMPTE files are rejected',()=>{
 for(const transform of [a=>{a[9]=2;},a=>{a[12]=128;}]){const a=midiWrite(score).bytes;transform(a);assert.throws(()=>midiRead(a));}
});
test('running status and note-on velocity zero are decoded as note-offs',()=>{
 const header=[77,84,104,100,0,0,0,6,0,0,0,1,1,224];
 const track=[0,153,36,90,60,36,0,0,153,38,70,60,38,0,0,255,47,0];
 const a=new Uint8Array([...header,77,84,114,107,0,0,0,track.length,...track]);
 const p=midiRead(a);assert.equal(p.events.length,2);assert.equal(p.events[0].durationBeats,1/8);assert.equal(p.period,1/4);
});
test('malformed running status, too-large VLQ, metadata and trailing bytes fail closed',()=>{
 const base=midiWrite(score).bytes;
 assert.throws(()=>midiRead(new Uint8Array([...base,0])));
 const header=[77,84,104,100,0,0,0,6,0,0,0,1,1,224];
 for(const tr of [[0,36,99],[255,255,255,255,0,153,36,90],[0,255,81,3,0]]){
  assert.throws(()=>midiRead(new Uint8Array([...header,77,84,114,107,0,0,0,tr.length,...tr])));
 }
});
test('tempo edits and seeks preserve one unwrapped transport phase',async()=>{
 const c=fakeContext(),t=new BeatTransport({contextFactory:()=>c,autoTick:false});const scheduled=[];
 t.voice=(e,when)=>scheduled.push({e,when});t.setScore(score);await t.play();
 assert.equal(scheduled[0].e.note,36);assert.equal(scheduled[0].when,.035);
 c.currentTime=.2;const beat=t.beat();t.setBpm(180);assert.equal(t.beat(),beat);
 t.seek(-.5);assert.equal(t.beat(),-.5);assert.equal(t.bpm,180);
 t.pause();c.currentTime=8;assert.equal(t.beat(),-.5);assert.equal(t.running,false);
 t.dispose();
});
test('mute and silent transport do not create replacement stale events',async()=>{
 const c=fakeContext(),t=new BeatTransport({contextFactory:()=>c,autoTick:false});const notes=[];
 t.voice=e=>notes.push(e.note);t.setScore(score);t.mute('kick',true);await t.play();assert.equal(notes.length,0);
 await t.setSound(false);c.currentTime=.18;t.tick();assert.equal(notes.length,0);assert.equal(t.running,true);
 t.pause();t.dispose();
});
test('pause invalidates pending AudioContext resume',async()=>{
 const c=fakeContext();let resolve;c.resume=()=>new Promise(r=>{resolve=()=>{c.state='running';r();};});
 const t=new BeatTransport({contextFactory:()=>c,autoTick:false});t.setScore(score);const start=t.play();t.pause();resolve();await start;
 assert.equal(t.running,false);assert.equal(t.timer,null);t.dispose();
});
test('every bundled harness beat exports and reloads as real MIDI',()=>{
 const file=process.env.DANCERUDIMENTS_BEATS_JSON || path.join(root,'harness/beats.json');
 const library=JSON.parse(fs.readFileSync(file,'utf8'));
 assert.ok(library.beats.length>=305);assert.ok(library.coverage.dance_scores>=68);
 for(const source of library.beats){
  const out=midiWrite(source,128),p=midiRead(out.bytes,source.title),b=normalizeBeat(source);
  assert.equal(p.events.length,b.events.length,source.id);
  assert.ok(Math.abs(p.period-b.period)<=.5/out.ppq,source.id);
  for(let i=0;i<p.events.length;i++)assert.ok(Math.abs(p.events[i].time-b.events[i].time)<=1/out.ppq,source.id+' '+i);
 }
 const amen=normalizeBeat(library.beats.find(b=>b.id==='amen_four_bar'));
 assert.equal(amen.period,16);assert.equal(amen.events.length,81);
 assert.deepEqual(normalizeBeat(library.beats.find(b=>b.id==='four_floor')).events.map(e=>e.time),[0,1,2,3]);
});
