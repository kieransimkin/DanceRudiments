import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import '../../tools/song_loop_viewer/motion-assets.js';

const assets=globalThis.DanceRudimentsMotionAssets;
function identity(bytes){return {path:'motion-assets/motion-1.preview.json',byte_length:bytes.length,
  sha256:createHash('sha256').update(bytes).digest('hex')};}
const response=bytes=>async()=>new Response(bytes);

test('lazy preview verifies every byte before returning it',async()=>{
  const bytes=new TextEncoder().encode('{"poses":[]}');
  assert.deepEqual(await assets.verifiedAsset(identity(bytes),{fetch:response(bytes)}),bytes);
  await assert.rejects(assets.verifiedAsset({...identity(bytes),sha256:'a'.repeat(64)},
    {fetch:response(bytes)}),/SHA-256/);
  await assert.rejects(assets.verifiedAsset({...identity(bytes),byte_length:bytes.length-1},
    {fetch:response(bytes)}),/exceeds its bound/);
  await assert.rejects(assets.verifiedAsset({...identity(bytes),byte_length:bytes.length+1},
    {fetch:response(bytes)}),/length changed/);
});

test('asset paths and size budgets are rejected before fetching',async()=>{
  let calls=0;const fetch=()=>{calls++;throw Error('must not fetch');};
  const bytes=new Uint8Array([1]);
  for(const path of ['../master.mp3','https://example.com/a','audio/../secret.mp3','motion-assets/motion-1.preview.json?x=1'])
    await assert.rejects(assets.verifiedAsset({...identity(bytes),path},{fetch}),/identity/);
  await assert.rejects(assets.verifiedAsset({...identity(bytes),byte_length:32*1024*1024+1},{fetch}),/identity/);
  assert.equal(calls,0);
});

test('source preview preserves finite poses, exact bone counts and ordered observed pips',()=>{
  const motion={frame_count:2,raw_sample_count:65,bones:['root','child'],links:[[0,1]]};
  const data={xyz:[[[0,0,0],[0,0,1]],[[1,0,0],[1,0,1]]],frame_relative_pips:[0,64]};
  assert.equal(assets.validatePreview(data,motion),data);
  for(const broken of [ {...data,frame_relative_pips:[0,65]}, {...data,frame_relative_pips:[0,0]},
    {...data,id:'replace-the-verified-motion'},
    {...data,xyz:[data.xyz[0],[data.xyz[1][0]]]},
    {...data,xyz:[data.xyz[0],[[NaN,0,0],[1,0,1]]]} ])
    assert.throws(()=>assets.validatePreview(broken,motion),/preview/i);
});
