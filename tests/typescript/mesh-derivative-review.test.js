/** Synthetic source/correction identities; the optional browser gate uses Kandi. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {validateFinishedMotion,createDerivativeReview} from '../../tools/mesh_demo_assets/derivative-review.js';
import {PipTransport} from '../../tools/mesh_demo_assets/transport.js';
const H=x=>x.repeat(64),hash=x=>createHash('sha256').update(x).digest('hex');

function fixture(){
  const after={max_rotation_seam_radians:0,max_rotation_velocity_jump_radians_per_second:0,
    max_translation_seam:0,max_translation_velocity_jump:0,max_scalar_seam_fraction:0,
    max_scalar_velocity_jump_fraction_per_second:0,discrete_seam_matches:true};
  const scene={expectedProfile:{fingerprint:H('a'),type_uri:'syn://type/danceflow/motion/skeletal/source/test'},
    sourceSha256:H('b'),startPip:0,endPip:639,sourceDurationSeconds:10};
  const repair={format:'dancerudiments.loop-repair',schema_version:1,
    method:'bounded-local-pose-and-tangent-v1',accepted:true,status:'numerically_closed_review_candidate',
    source_capture_sha256:H('c'),source_profile_sha256:H('a'),repair_id:H('d'),
    corrected_capture_sha256:H('e'),source_start_seconds:2,source_end_seconds:3,period_seconds:1,
    sample_count:65,translation_scale:10,rejection_reasons:[],requires_review:true,
    loop_seam_approved:false,target_mesh_verified:false,audio_beat_alignment_verified:false,
    options:{sample_count:65,closure_tolerance:1e-7,tangent_tolerance:1e-6,max_rotation_correction_radians:.45,
      max_translation_correction_fraction:.15,max_scalar_correction_fraction:.08,
      max_correction_rms_fraction:.12,min_activity_retention:.65,max_activity_increase:1.6},
    after,corrections:{max_rotation_radians:.01,max_translation_fraction:.01,
      max_scalar_fraction:0,rms_fraction:.01},activity_retention:.99,contacts:{provided_count:0},
    compiled_verification:{format:'dancerudiments.compiled-loop-check',schema_version:1,
      method:'all_decoded_samples_and_half_open_wrap_v1',passed:true,rejection_reasons:[],
      loop_seam_approved:false,compiled_motion_fingerprint:H('f'),corrected_capture_sha256:H('e'),
      max_normalized_scalar_sample_error:0,max_rotation_sample_error_radians:0,after:structuredClone(after)},
    original_source_sha256:H('b')};
  const motion={format:'dancerudiments.rig-motion',schema_version:1,profile_sha256:H('a'),
    type_uri:scene.expectedProfile.type_uri,recording:{samples:Array.from({length:64},()=>[0]),
    clock:{start_pip:0,bpm:60,bpm_status:'estimated',phase_status:'estimated'},
    provenance:{motion_kind:'repaired_loop_candidate',original_source_sha256:H('b'),
      original_capture_sha256:H('c'),source_capture_sha256:H('e'),corrected_capture_sha256:H('e'),
      repair_id:H('d'),repair_method:repair.method,numerical_repeat_seam_verified:true,repeat_seam_verified:false,
      musical_timing_verified:false,target_mesh_verified:false,suggested_loop_period_pips:64,
      repair_source_bounds_seconds:[2,3],source_provenance:{repair:structuredClone(repair),
        producer:'dancerudiments.offline-loop-repair',loop_policy:'closed_endpoint_capture_for_half_open_compilation'}}}};
  function bytes(){const out=Buffer.from(JSON.stringify(motion));repair.compiled_motion_sha256=hash(out);return out;}
  return {scene,repair,motion,bytes};
}

test('finished clip identity yields exact half-open native and original comparison windows',async()=>{
  const f=fixture(),info=await validateFinishedMotion(f.bytes(),f.repair,f.scene);
  assert.deepEqual([info.first,info.last,info.periodPips,info.pipSeconds],[0,63,64,1/64]);
  assert.deepEqual([info.sourceFirstPip,info.sourceEndPip],[128,191]);
});

test('wrong source/profile, changed bytes, capture identity and approved claims are rejected',async()=>{
  for(const change of [
    f=>{f.scene.sourceSha256=H('f');},
    f=>{f.scene.expectedProfile.fingerprint=H('f');},
    f=>{f.repair.compiled_motion_sha256=H('f');},
    f=>{f.repair.source_capture_sha256=H('f');},
    f=>{f.repair.corrected_capture_sha256=H('f');},
    f=>{f.repair.target_mesh_verified=true;},
    f=>{f.repair.loop_seam_approved=true;},
  ]){
    const f=fixture(),bytes=f.bytes();change(f);
    await assert.rejects(validateFinishedMotion(bytes,f.repair,f.scene),/Invalid finished motion/);
  }
});

test('numeric report must match encoded correction provenance and rechecked compiled rows',async()=>{
  for(const change of [
    f=>{f.repair.options.max_rotation_correction_radians=.001;},
    f=>{f.repair.after.max_translation_seam=1;},
    f=>{f.repair.source_end_seconds=11;},
    f=>{delete f.repair.compiled_verification;},
    f=>{f.repair.compiled_verification.passed=false;},
    f=>{f.repair.compiled_verification.after.max_translation_velocity_jump=1;},
    f=>{f.repair.compiled_verification.max_rotation_sample_error_radians=.01;},
    f=>{f.repair.compiled_verification.corrected_capture_sha256=H('f');},
    f=>{f.motion.recording.samples.pop();},
    f=>{f.motion.recording.clock.phase_status='supplied';},
  ]){
    const f=fixture();change(f);
    await assert.rejects(validateFinishedMotion(f.bytes(),f.repair,f.scene),/Invalid finished motion/);
  }
});

test('finished beat clock preserves N half-open poses and stops at the exclusive boundary',()=>{
  let now=0;const transport=new PipTransport(0,256,()=>now,128);
  transport.play();now=1999;assert.equal(transport.pip(),255);assert.equal(transport.playing,true);
  now=2000;assert.equal(transport.pip(),256);assert.equal(transport.playing,false);
  // The caller maps the exclusive stop to the final pose, and only an explicit
  // repeat control seeks to zero. The native handle never accepts pip 256.
  transport.seek(0);transport.setSpeed(.5);transport.play();now=3000;assert.equal(transport.pip(),64);
  assert.throws(()=>new PipTransport(0,10,()=>now,NaN),/clock rate/);
});

test('explicit local review exposes compare, repeat and clear without claiming visual approval',async()=>{
  const prior=globalThis.document;
  class Element{
    constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.attributes={};}
    append(...children){this.children.push(...children);}
    setAttribute(key,value){this.attributes[key]=value;}
    addEventListener(key,handler){this.listeners[key]=handler;}
  }
  globalThis.document={createElement:tag=>new Element(tag),createTextNode:text=>({text})};
  try{
    const sidebar=new Element('aside'),modes=[],repeats=[];let clears=0,loads=0;
    const review=createDerivativeReview({sidebar,onLoad:async()=>{loads++;return {sourceStartSeconds:2,sourceEndSeconds:3};},
      onMode:mode=>modes.push(mode),onRepeat:value=>repeats.push(value),onClear:()=>clears++});
    const section=sidebar.children[0],inputs=section.children.filter(x=>x.tag==='label').map(x=>x.children[0]);
    const buttons=section.children.find(x=>x.className==='rhythm-loops').children;
    assert.equal(inputs[0].disabled,true);review.attach();assert.equal(inputs[0].disabled,false);
    inputs[0].files=[{size:2,arrayBuffer:async()=>new Uint8Array([123,125]).buffer}];
    inputs[1].files=[{size:2,text:async()=>'{}'}];
    await buttons[0].listeners.click();assert.equal(loads,1);
    assert.deepEqual(review.diagnostics(),{loaded:true,mode:'finished',repeat:false,targetVisualReview:'unverified'});
    buttons[1].listeners.click();assert.deepEqual(modes,['original']);
    inputs[2].checked=true;inputs[2].listeners.change();assert.deepEqual(repeats,[true]);
    buttons[3].listeners.click();assert.equal(clears,1);assert.equal(review.diagnostics().loaded,false);
    review.reset();assert.equal(inputs[0].disabled,true);
  }finally{globalThis.document=prior;}
});
