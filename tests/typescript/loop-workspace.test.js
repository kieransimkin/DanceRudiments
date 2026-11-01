import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {workspaceToken,validateWorkspaceSession,forwardTime,loopPlayback,audioSecondsToPip,
  parseManualAnchors,createWorkspaceClient,MAX_LOOP_BEATS} from '../../tools/mesh_demo_assets/loop-workspace.js';

const hash = n => n.repeat(64);
const token='0123456789abcdefghijklmnopqrstuvwxyzABCDEFG';
const segment={motion_seconds_range:[1,4],audio_seconds_range:[10,15],anchors:[
  {motion_seconds:1,audio_seconds:10},{motion_seconds:2,audio_seconds:11},{motion_seconds:4,audio_seconds:15}]};
const selection={bounds:{start_seconds:1.5,end_seconds:3},beat_count:4,sample_count:256};

function fixture(){
  const target={id:'kandi-boom',asset_sha256:hash('a'),rig_sha256:hash('b'),calibration_sha256:hash('c')};
  const source={original_source_sha256:hash('d'),capture_file_sha256:hash('e'),capture_sha256:hash('f'),profile_sha256:hash('1')};
  const descriptor=(id,sha256)=>({url:`/api/files/${id}`,sha256,byte_length:10});
  const config={scenes:[{id:'review',sourceSha256:source.original_source_sha256,expectedProfile:{fingerprint:source.profile_sha256}}],
    reviewTarget:target,character:{fbxAssetSha256:target.asset_sha256,assets:{rig:{sha256:target.rig_sha256}}}};
  const doc={format:'dancerudiments.loop-review-workspace.v1',schema_version:1,revision:1,scene_id:'review',target,
    selection:{...selection,format:'dancerudiments.loop-selection.v1',schema_version:1,selection_id:hash('2'),source,
      files:{motion:{sha256:hash('3')},repair:{sha256:hash('4')}}},
    files:{motion:descriptor('motion',hash('3')),repair:descriptor('repair',hash('4')),audio:descriptor('audio',hash('5'))},
    alignment:{report_sha256:hash('6'),report_content_sha256:hash('7'),report:{format:'stemlab.motion-alignment.v1',
      motion_source:{sha256:source.capture_file_sha256},audio_source:{sha256:hash('5')}}}};
  return {config,doc};
}

test('workspace capability is explicit, fragment-only, and restricted to loopback HTTP',()=>{
  assert.equal(workspaceToken(new URL('https://example.org/meshes/')),null);
  assert.equal(workspaceToken(new URL(`http://127.0.0.1:9123/meshes/#review=${token}`)),token);
  assert.equal(workspaceToken(new URL(`http://[::1]:9123/meshes/#review=${token}`)),token);
  assert.throws(()=>workspaceToken(new URL(`https://example.org/#review=${token}`)),/loopback/);
  assert.throws(()=>workspaceToken(new URL('http://127.0.0.1/#review=short')),/invalid/);
});

test('workspace requires exact original source, target calibration and finished bytes',()=>{
  const {config,doc}=fixture();assert.equal(validateWorkspaceSession(doc,config),doc);
  for(const mutate of [
    d=>{d.selection.source.original_source_sha256=hash('a');},
    d=>{d.selection.source.profile_sha256=hash('a');},
    d=>{d.target={...d.target,calibration_sha256:hash('f')};},
    d=>{d.files.motion.sha256=hash('a');},
    d=>{d.alignment.report.audio_source.sha256=hash('a');},
    d=>{d.files.audio.url='https://external.example/private';},
    d=>{d.files.audio.url='/api/files/../audio';},
    d=>{d.files.motion.byte_length=65*1024*1024;},
  ]){const value=structuredClone(doc);mutate(value);assert.throws(()=>validateWorkspaceSession(value,config));}
});

test('browser beat bounds match the backend one-to-thirty-two beat selection contract',()=>{
  const {config,doc}=fixture();
  assert.equal(MAX_LOOP_BEATS,32);
  for(const beats of [1,32]){
    const value=structuredClone(doc);value.selection.beat_count=beats;value.selection.sample_count=beats*64;
    assert.equal(validateWorkspaceSession(value,config),value);
  }
  for(const beats of [0,1.5,33,64]){
    const value=structuredClone(doc);value.selection.beat_count=beats;value.selection.sample_count=beats*64;
    assert.throws(()=>validateWorkspaceSession(value,config),/beat count/);
  }
});

test('native pip selection follows a variable audio mapping and has an exclusive repeat endpoint',()=>{
  const playback=loopPlayback(selection,[segment]);
  assert.deepEqual(playback.audio_seconds_range,[10.5,13]);
  assert.equal(forwardTime([segment],2.5),12);
  assert.equal(audioSecondsToPip(playback,10.5),0);
  assert.equal(audioSecondsToPip(playback,11),85);
  assert.equal(audioSecondsToPip(playback,12),170);
  assert.equal(audioSecondsToPip(playback,13),null);
  assert.equal(audioSecondsToPip(playback,13,{repeat:true}),0);
  assert.equal(audioSecondsToPip(playback,15.5,{repeat:true}),0);
  assert.equal(audioSecondsToPip(playback,10.49,{repeat:true}),null);
});

test('loop playback never connects disconnected segments or extrapolates',()=>{
  const next={motion_seconds_range:[5,6],audio_seconds_range:[16,17],anchors:[
    {motion_seconds:5,audio_seconds:16},{motion_seconds:6,audio_seconds:17}]};
  assert.equal(forwardTime([segment,next],4.5),null);
  assert.throws(()=>loopPlayback({...selection,bounds:{start_seconds:3,end_seconds:5.5}},[segment,next]),/without a gap/);
  assert.throws(()=>audioSecondsToPip(loopPlayback(selection,[segment]),NaN),/finite/);
});

test('manual anchor input retains actual source clocks and rejects malformed pairs',()=>{
  assert.equal(parseManualAnchors('   '),null);
  assert.deepEqual(parseManualAnchors('1.25, 8.5\n2.75 10.2'),[
    {motion_seconds:1.25,audio_seconds:8.5},{motion_seconds:2.75,audio_seconds:10.2}]);
  assert.throws(()=>parseManualAnchors('1,2'),/at least two/);
  assert.throws(()=>parseManualAnchors('1,2,3\n4,5'),/Each anchor/);
  assert.throws(()=>parseManualAnchors('1,Infinity\n4,5'),/Each anchor/);
});

test('workspace fetches carry capability only in a header and reject changed asset bytes',async()=>{
  const bytes=Buffer.from('original recording'),sha256=createHash('sha256').update(bytes).digest('hex'),calls=[];
  const client=createWorkspaceClient(token,{fetch:async(path,init)=>{calls.push({path,init});return new Response(bytes);}});
  const file={url:'/api/files/motion',sha256,byte_length:bytes.length};
  assert.deepEqual(Buffer.from(await client.file(file,100)),bytes);
  assert.equal(calls[0].init.headers['X-Loop-Review-Token'],token);
  assert.equal(calls[0].init.credentials,'same-origin');assert.equal(calls[0].init.redirect,'error');
  assert.equal(calls[0].path.includes(token),false);
  await assert.rejects(client.file({...file,sha256:hash('f')},100),/saved identity/);
  await assert.rejects(client.json('https://example.org/api/session'),/route/);
});

test('workspace optimistic conflicts are surfaced and streaming output limits remain enforced',async()=>{
  const client=createWorkspaceClient(token,{fetch:async()=>new Response(JSON.stringify({error:'Revision changed'}),{status:409})});
  await assert.rejects(client.json('/api/finish',{expected_revision:2}),error=>error.status===409&&error.message==='Revision changed');
  const oversized=createWorkspaceClient(token,{fetch:async()=>new Response(new Uint8Array(101))});
  await assert.rejects(oversized.file({url:'/api/files/audio',sha256:hash('a'),byte_length:100},100),/size limit/);
});
