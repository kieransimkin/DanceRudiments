// Shared synthetic fixtures. Native sampling uses the checked-in C++ WASM.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import {createRecordingWasmAdapter} from '../../dist/typescript/motion-packages.js';
const wasmBytes = Buffer.from(readFileSync(new URL('../../python/dancerudiments_authoring/harness_assets/recording.wasm.b64', import.meta.url), 'utf8').trim(), 'base64');
const wasm = await WebAssembly.compile(wasmBytes);
const realFactory = createRecordingWasmAdapter(wasm);
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const encode = value => Buffer.from(JSON.stringify(value));
const url = 'https://motion.example/packs/fixture/manifest.json';
const syntheticType = 'syn://type/danceflow/motion/rigify/custom/fixture';

function channel(number, name, extra = {}) {
  return {number, name, bone:'root', data_path:'location', array_index:number - 1,
    unit:'Blender units', minimum:-10, maximum:10, neutral:0, value_type:'float',
    interpolation:'linear', rotation_mode:'', enum_items:[], ...extra};
}
// Match Python's sorted, ASCII, finite canonical profile bytes, including the
// float-typed channel range/neutral fields. No trailing newline is present.
function profileBytes(profile) {
  function sorted(value) {
    if (Array.isArray(value)) return value.map(sorted);
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, sorted(value[key])]));
  }
  return Buffer.from(JSON.stringify(sorted(profile)).replace(/"(minimum|maximum|neutral)":(-?\d+)(?=[,}])/g, '"$1":$2.0'));
}
function fixture({encoding = 'json', transformProfile, transformRecording} = {}) {
  const profile = {format:'dancerudiments.rig-profile', schema_version:1, type_uri:syntheticType,
    model:'fixture', version:1, channels:[channel(1,'root_x'), channel(2,'root_y'),
      channel(3,'ik_on',{data_path:'["IK_FK"]',array_index:-1,unit:'boolean',minimum:0,maximum:1,
        value_type:'boolean',interpolation:'step'})], source:{synthetic:true}};
  transformProfile?.(profile);
  const profileRaw = profileBytes(profile), fingerprint = digest(profileRaw);
  const recordings = ['pulse','sway'].map(name => ({format:'dancerudiments.recording',schema_version:1,
    pips_per_beat:64,sample_dtype:'float64',sample_decimals:12,name,
    dimensions:profile.channels.map(item => item.name),
    clock:{bpm:120,bpm_source:'synthetic authored timing',bpm_status:'confirmed',
      beat_zero_seconds:0.125,phase_status:'supplied',start_pip:-2},
    samples:[[-1,-0.5,-1],[0.25,0.5,1],[1,1,1]],provenance:{synthetic:true}}));
  for (const recording of recordings) transformRecording?.(recording);
  const assets = new Map([['profile.json',profileRaw]]), calls = [];
  const manifest = {format:'dancerudiments.motion-package',schema_version:1,id:'synthetic',version:'1.0.0',
    title:'Synthetic motion fixture',type_uri:syntheticType,profile_sha256:fingerprint,
    dimensions:profile.channels.map(item => item.name),
    profile:{path:'profile.json',sha256:fingerprint,byte_length:profileRaw.length},
    clips:recordings.map(recording => {
      const decoded = encode(recording), stored = encoding === 'gzip' ? gzipSync(decoded) : decoded;
      const path = `clips/${recording.name}.json${encoding === 'gzip' ? '.gz' : ''}`;
      assets.set(path,stored);
      return {id:recording.name,path,sha256:digest(stored),byte_length:stored.length,
        decoded_byte_length:decoded.length,encoding,start_pip:-2,sample_count:3,
        metadata:{timing_kind:'music',tags:['synthetic'],source_url:'https://example.org/synthetic'}};
    }),license:{spdx:'CC0-1.0',attribution:'Synthetic test fixture'},provenance:{synthetic:true}};
  const updateManifest = () => assets.set('manifest.json',encode(manifest));
  updateManifest();
  const fetch = async (input, init) => {
    const path = new URL(input).pathname.replace('/packs/fixture/','');
    calls.push({path,signal:init.signal});
    assert.equal(init.credentials,'omit');
    const body = assets.get(path);
    if (typeof body === 'function') return body(init);
    if (body === undefined) return new Response('missing',{status:404});
    return new Response(body);
  };
  const options = {manifestUrl:url,packageId:'synthetic',
    expectedProfile:{typeUri:syntheticType,sha256:fingerprint,dimensions:manifest.dimensions},
    fetch,nativeFactory:realFactory};
  function setRecording(index, value) {
    const descriptor = manifest.clips[index], decoded = encode(value);
    const stored = descriptor.encoding === 'gzip' ? gzipSync(decoded) : decoded;
    descriptor.byte_length = stored.length; descriptor.decoded_byte_length = decoded.length;
    descriptor.sha256 = digest(stored); assets.set(descriptor.path,stored); updateManifest();
  }
  return {profile,manifest,recordings,assets,calls,options,updateManifest,setRecording};
}
function observedFactory() {
  const state = {created:0,disposed:0,sampled:[],signals:[]};
  state.factory = async (recording, options) => {
    state.signals.push(options.signal);
    const native = await realFactory(recording,options);
    state.created++;
    return {sample(pip) { state.sampled.push(pip); return native.sample(pip); },
      dispose() { state.disposed++; native.dispose(); }};
  };
  return state;
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes,no) => {resolve=yes;reject=no;});
  return {promise,resolve,reject};
}
async function until(predicate) {
  const end = Date.now() + 5000;
  while (!predicate()) {
    if (Date.now() > end) throw Error('Timed out waiting for test checkpoint');
    await new Promise(resolve => setImmediate(resolve));
  }
}
const abort = promise => assert.rejects(promise,error => error?.name === 'AbortError');

export {wasmBytes, realFactory, digest, channel, profileBytes, fixture, observedFactory, deferred, until, abort, syntheticType};
