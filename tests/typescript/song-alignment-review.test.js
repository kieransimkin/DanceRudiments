import test from 'node:test';
import assert from 'node:assert/strict';
import '../../tools/song_loop_viewer/alignment-review.js';

const review=globalThis.DanceRudimentsTimingReview;
function evidence(){
  return {report_sha256:'a'.repeat(64),report_content_sha256:'b'.repeat(64),report:{
    format:'stemlab.motion-alignment.v1',schema_version:1,
    motion_source:{sha256:'c'.repeat(64),valid_segments_seconds:[[1,4],[6,9]]},
    audio_source:{sha256:'d'.repeat(64),valid_segments_seconds:[[0,20]]},
    candidates:[{candidate_id:'timing-1',method:'piecewise_event_match',score_uncalibrated:.8,
      mapping_segments:[
        {motion_seconds_range:[1,4],audio_seconds_range:[2,8],anchors:[
          {motion_seconds:1,audio_seconds:2},{motion_seconds:2,audio_seconds:3},
          {motion_seconds:4,audio_seconds:8}]},
        {motion_seconds_range:[6,9],audio_seconds_range:[10,16],anchors:[
          {motion_seconds:6,audio_seconds:10},{motion_seconds:9,audio_seconds:16}]}]}]}};
}

test('timing evidence requires both exact source identities',()=>{
  const entry=evidence();
  assert.deepEqual(review.matchingReviews([entry],{source_sha256:'d'.repeat(64)},
    {source_capture_sha256:'c'.repeat(64)}),[entry]);
  assert.equal(review.matchingReviews([entry],{source_sha256:'e'.repeat(64)},
    {source_capture_sha256:'c'.repeat(64)}).length,0);
});

test('variable timing maps only covered source spans without bridging gaps',()=>{
  const parts=review.shiftedSegments(evidence(),0);
  assert.equal(review.inverseTime(parts,5.5),3);
  assert.equal(review.inverseTime(parts,13),7.5);
  assert.equal(review.inverseTime(parts,9),null);
  assert.equal(review.inverseTime(parts,1),null);
  assert.equal(review.inverseTime(parts,17),null);
});

test('phase edits preserve original evidence and reject uncovered source times',()=>{
  const entry=evidence(),original=JSON.stringify(entry);
  const parts=review.shiftedSegments(entry,0,.125);
  assert.equal(parts[0].anchors[0].audio_seconds,2.125);
  assert.equal(JSON.stringify(entry),original);
  assert.throws(()=>review.shiftedSegments(entry,0,-3),/coverage gap/);
  assert.throws(()=>review.shiftedSegments(entry,0,31),/30 seconds/);
  assert.throws(()=>review.shiftedSegments(entry,0,NaN),/30 seconds/);
  entry.report.candidates[0].mapping_segments[0].anchors[1].motion_seconds=.5;
  assert.throws(()=>review.shiftedSegments(entry,0),/increase/);
});

test('review mapping respects half-open loops and inclusive complete-action samples',()=>{
  const loop={raw_sample_count:256,estimated_bpm:120,source_clock_start_seconds:0,loopable:true};
  assert.equal(review.phaseForSource(loop,0),0);
  assert.equal(review.phaseForSource(loop,1),.5);
  assert.equal(review.phaseForSource(loop,2),null);
  assert.equal(review.phaseForSource(loop,-.01),null);
  const action={...loop,source_clock_start_seconds:3,loopable:false};
  assert.equal(review.phaseForSource(action,3+255/128),255/256);
  assert.equal(review.phaseForSource(action,3+255.5/128),null);
});

test('timing review does not infer beat one, meter, skin or loop approval',()=>{
  const entry=evidence(),revision=review.makeRevision(entry,0,{reviewer:'Test reviewer'});
  assert.equal(revision.report_sha256,entry.report_sha256);
  assert.equal(revision.mapping_status,'user_confirmed');
  assert.equal(revision.beat_one_status,'unconfirmed');
  assert.equal(revision.meter_status,'unconfirmed');
  assert.equal(revision.loop_seams_verified,false);
  assert.equal(revision.retargeting_verified,false);
  const explicit=review.makeRevision(entry,0,{reviewer:'Test reviewer',beatOne:2.125,meter:[3,4],offset:.125});
  assert.equal(explicit.beat_one_status,'user_confirmed');
  assert.deepEqual(explicit.meter,[3,4]);
  assert.throws(()=>review.makeRevision(entry,0,{reviewer:''}),/reviewer name/);
  assert.throws(()=>review.makeRevision(entry,0,{reviewer:'Test',beatOne:21}),/audio source/);
});

test('manual source-clock anchors and phase edits produce bounded review revisions',()=>{
  const entry=evidence(),manual=[{motion_seconds:1,audio_seconds:3},{motion_seconds:2,audio_seconds:5},{motion_seconds:4,audio_seconds:8}];
  const revision=review.makeRevision(entry,0,{reviewer:'Test reviewer',manualAnchors:manual,offset:.25});
  assert.equal(review.inverseTime(revision.mapping_segments,5.25),2);
  assert.equal(revision.mapping_segments[0].anchor_kind,'user_phase_correction');
  assert.equal(manual[0].audio_seconds,3);
  assert.throws(()=>review.makeRevision(entry,0,{reviewer:'Test',manualAnchors:[
    {motion_seconds:3,audio_seconds:5},{motion_seconds:7,audio_seconds:8}]}),/coverage gap/);
  assert.throws(()=>review.makeRevision(entry,0,{reviewer:'Test',manualAnchors:[
    {motion_seconds:1,audio_seconds:5},{motion_seconds:2,audio_seconds:4}]}),/increase/);
});

test('reopening a timing review validates source identity and continues the revision chain',()=>{
  const entry=evidence(),prior=review.makeRevision(entry,0,{reviewer:'Test reviewer'});
  assert.deepEqual(review.validateSavedRevision(entry,prior),prior);
  const next=review.makeRevision(entry,0,{reviewer:'Test reviewer',offset:.1,
    previousRevision:prior,previousRevisionSha256:'f'.repeat(64)});
  assert.equal(next.revision,2);assert.equal(next.previous_revision_sha256,'f'.repeat(64));
  assert.throws(()=>review.makeRevision(entry,0,{reviewer:'Test',previousRevision:prior}),/identity is missing/);
  assert.throws(()=>review.validateSavedRevision(entry,{...prior,motion_source_sha256:'f'.repeat(64)}),/different evidence/);
  assert.throws(()=>review.validateSavedRevision(entry,{...prior,loop_seams_verified:true}),/seams or geometry/);
});
