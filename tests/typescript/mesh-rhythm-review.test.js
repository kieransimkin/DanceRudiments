/** Synthetic, offline evidence tests; no third-party dance/model downloads. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceLoopPips, validateMotionAnalysis} from '../../tools/mesh_demo_assets/rhythm-review.js';

const H = value => value.repeat(64);
const scene = {
  id: 'boxbot', startPip: 0, endPip: 256, sampleCount: 257,
  secondsPerPip: 1 / 64, timingKind: 'time-only', musicTimingVerified: false,
  manifestSha256: H('a'), packageId: 'salsa', originalClipId: H('b'),
  clipIds: ['part_1', 'part_2'],
  expectedProfile: {fingerprint: H('c'), type_uri: 'syn://type/danceflow/motion/skeletal/source/human'},
};
const clips = [
  {id: 'part_1', sha256: H('d')},
  {id: 'part_2', sha256: H('e')},
];
const report = () => ({
  format: 'stemlab.rig-motion-analysis', schema_version: 1, source_kind: 'motion_package',
  source_file_sha256: H('a'), source_manifest_sha256: H('a'),
  source_package_id: 'salsa', source_original_action_id: H('b'),
  profile_sha256: H('c'), type_uri: scene.expectedProfile.type_uri,
  source_start_pip: 0, source_sample_count: 257,
  source_clip_ids: ['part_1', 'part_2'], source_clip_sha256: [H('d'), H('e')],
  source_timing_kind: 'time-only; no verified musical tempo or downbeat',
  source_calibration_omitted_pips: 1,
  source_range_seconds: [1 / 64, 4],
  motion_accents: [{seconds: 0.5, strength: 0.75}, {seconds: 1.0, strength: 0.5}],
  recommended_tempo: {bpm: 120},
  estimated_beat_map: {format: 'dancerudiments.beat-map', schema_version: 1,
    pips_per_beat: 64, interpolation: 'linear', bpm_status: 'estimated',
    phase_status: 'estimated', extrapolate: false,
    anchors: [{seconds: .5, beat: 0}, {seconds: 1.0, beat: 1}]},
  loop_candidates: [{start_seconds: .503, end_seconds: 2.5, alignment: 'estimated_motion_beat_grid',
    beats: 4, score: 0.8, requires_review: true, repaired: false},
  {start_seconds: 1, end_seconds: 3.0, alignment: 'pose_recurrence_only',
    beats: null, score: 0.7, requires_review: true, repaired: false}],
});

test('authentic complete source action produces bounded preview regions and beat markers', () => {
  const r = validateMotionAnalysis(report(), scene, clips);
  assert.equal(r.bpm, 120);
  assert.deepEqual(r.beats, [0.5, 1.0]);
  assert.equal(r.accents.length, 2);
  assert.deepEqual(r.loops.map(l => [l.first, l.endExclusive]), [[33, 160], [64, 192]]);
  assert.equal(r.loops[1].alignment, 'pose_recurrence_only');
});

test('time-only unquantized pose recurrence can be displayed without claiming BPM', () => {
  const data = report(); data.recommended_tempo = null; data.estimated_beat_map = null;
  const x = validateMotionAnalysis(data, scene, clips);
  assert.equal(x.bpm, null); assert.equal(x.beats.length, 0);
  assert.equal(x.loops.length, 2);
});

test('refuse the wrong package, retarget profile, action, chunk or musical clock', () => {
  for (const [key, value] of [
    ['source_manifest_sha256', H('f')], ['source_original_action_id', H('f')],
    ['profile_sha256', H('f')], ['source_file_sha256', H('f')],
    ['source_start_pip', 1], ['source_sample_count', 250],
    ['source_timing_kind', 'musically verified'],
  ]) {
    const data = report(); data[key] = value;
    assert.throws(() => validateMotionAnalysis(data, scene, clips), /Invalid StemLab motion analysis/);
  }
  const data = report(); data.source_clip_sha256[1] = H('f');
  assert.throws(() => validateMotionAnalysis(data, scene, clips), /source chunk 2/);
});

test('refuse inferred time as confirmed music and unsafe seams', () => {
  for (const mutate of [
    x => { x.estimated_beat_map.phase_status = 'supplied'; },
    x => { x.estimated_beat_map.bpm_status = 'confirmed'; },
    x => { x.estimated_beat_map.extrapolate = true; },
    x => { x.estimated_beat_map.anchors[1].seconds = 0.4; },
    x => { x.loop_candidates[0].repaired = true; },
    x => { x.loop_candidates[0].requires_review = false; },
    x => { x.loop_candidates[0].end_seconds = 8; },
    x => { x.loop_candidates[0].start_seconds = -1; },
    x => { x.motion_accents[0].strength = 2; },
  ]) {
    const data = report(); mutate(data);
    assert.throws(() => validateMotionAnalysis(data, scene, clips));
  }
});

test('half-open source boundaries never sample outside candidate interval or clip bounds', () => {
  assert.deepEqual(sourceLoopPips({start_seconds: 0.01, end_seconds: 3.999}, scene),
    {first: 1, endExclusive: 256});
  assert.deepEqual(sourceLoopPips({start_seconds: 0, end_seconds: 4}, scene),
    {first: 0, endExclusive: 256});
  assert.throws(() => sourceLoopPips({start_seconds: 4, end_seconds: 5}, scene));
});

test('local UI import shows markers, previews selected loops and clears state on unload', async () => {
  const {createRhythmReview} = await import('../../tools/mesh_demo_assets/rhythm-review.js');
  const prior = globalThis.document;
  class FakeElement {
    constructor(tag) {
      this.tag = tag; this.children = []; this.listeners = {}; this.style = {};
      this.attributes = {}; this.hidden = false; this.disabled = false; this.value = '';
    }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = [...children]; }
    setAttribute(key, value) { this.attributes[key] = value; }
    addEventListener(key, handler) { this.listeners[key] = handler; }
  }
  globalThis.document = {
    head: new FakeElement('head'), createElement: tag => new FakeElement(tag),
  };
  try {
    const sidebar = new FakeElement('aside'), timeline = new FakeElement('div');
    let seeked = null, previews = 0;
    const review = createRhythmReview({sidebar, timeline,
      onSeek: pip => {seeked = pip;}, onPreview: () => {previews++;}});
    const section = sidebar.children[0];
    const input = section.children.find(item => item.tag === 'label').children[0];
    const buttons = section.children.find(item => item.tag === 'div' && item.className === 'rhythm-loops');
    assert.equal(input.disabled, true);
    review.attach(scene, clips);
    assert.equal(input.disabled, false);
    input.files = [{size: 500, text: async () => JSON.stringify(report())}];
    await input.listeners.change();
    assert.deepEqual(review.diagnostics(), {loaded: true, bpm: 120, beatCount: 2,
      loopCount: 2, activeLoop: null});
    assert.equal(buttons.children.length, 3);
    assert.equal(timeline.children[0].children.length, 4);
    buttons.children[1].listeners.click();
    assert.equal(seeked, 33);
    assert.equal(previews, 1);
    assert.deepEqual([review.currentLoop().first, review.currentLoop().endExclusive,
      review.currentLoop().beats, review.currentLoop().alignment, review.currentLoop().score],
      [33, 160, 4, 'estimated_motion_beat_grid', 0.8]);
    assert.ok(Math.abs(review.currentLoop().seconds - 1.997) < 1e-9);
    review.reset();
    assert.deepEqual(review.diagnostics(), {loaded: false, bpm: null, beatCount: 0,
      loopCount: 0, activeLoop: null});
    assert.equal(input.disabled, true);
    assert.equal(timeline.children[0].children.length, 0);
  } finally {globalThis.document = prior;}
});
