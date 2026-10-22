/**
 * Local, read-only StemLab motion analysis review for the Kandi Boom demo.
 * No inference, retargeting, audio clock replacement or motion serialization.
 * Source evidence remains an unapproved kinematic hypothesis.
 */

const HASH = /^[a-f0-9]{64}$/;
const MAX_REPORT_BYTES = 2 * 1024 * 1024;
const MAX_MARKERS = 2048;
const MAX_LOOPS = 32;
const BPS = 64; // The reviewed Kandi captures use exactly 64 time-only pips/second.

const STYLE = `
.rhythm-review{margin-top:20px;padding-top:18px;border-top:1px solid var(--line)}
.rhythm-review .section-label{margin:0 0 10px}
.rhythm-summary,.rhythm-caution{font-size:10px;line-height:1.55;color:var(--muted);margin:8px 0}
.rhythm-caution{font-size:9px;margin-top:12px}
.rhythm-file-label{display:flex;flex-direction:column;gap:7px;font-size:10px;font-weight:600}
.rhythm-file-label input{width:100%;font-size:9px;background:#fff;border:1px solid var(--line);border-radius:6px;padding:8px}
.rhythm-file-label input:disabled{opacity:.5}
.rhythm-error{color:#9b4a34;font-size:10px;overflow-wrap:anywhere;line-height:1.5}
.rhythm-loops{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}
.rhythm-loops button{font-size:9px;text-align:left;border:1px solid #ccd6c5;border-radius:6px;padding:7px 9px;background:#fcfcf5;max-width:100%}
.rhythm-loops button[aria-pressed=true]{background:#d8e9d2;border-color:#77986e}
.timeline{position:relative}
.rhythm-markers{position:absolute;left:0;right:0;bottom:1px;height:12px;pointer-events:none;overflow:hidden}
.rhythm-markers span{position:absolute;width:1px;transform:translateX(-.5px);bottom:0;pointer-events:none}
.rhythm-beat{height:6px;background:#547e67;opacity:.8}
.rhythm-accent{height:3px;background:#be8167;opacity:.7}
.rhythm-loop-start,.rhythm-loop-end{height:12px;background:#344f36;width:2px!important}
`;

function required(condition, reason) {
  if (!condition) throw Error(`Invalid StemLab motion analysis: ${reason}`);
}
function finite(value) { return typeof value === 'number' && Number.isFinite(value); }

/** Endpoints in the report are half-open [start_seconds,end_seconds).
 * Snap upward onto actual source pips; never claim a sampled pose before an
 * inferred source boundary. Recording content and absolute time are untouched.
 */
export function sourceLoopPips(loop, scene) {
  const first = Math.ceil(loop.start_seconds * BPS - 1e-8) + 0;
  const endExclusive = Math.ceil(loop.end_seconds * BPS - 1e-8) + 0;
  required(Number.isSafeInteger(first) && Number.isSafeInteger(endExclusive), 'loop pip range');
  required(first >= scene.startPip && endExclusive <= scene.endPip + 1 && endExclusive > first + 1,
    'loop pips fall outside the complete source action');
  return {first, endExclusive};
}

/** The live loader has already independently verified the native package.
 * This checks that a local JSON report names THAT package, every clip, its
 * original action, profile and coordinate system (not merely a character).
 */
export function validateMotionAnalysis(report, scene, clips) {
  required(report && typeof report === 'object' && !Array.isArray(report), 'root must be an object');
  required(report.format === 'stemlab.rig-motion-analysis' && report.schema_version === 1, 'schema 1');
  required(report.source_kind === 'motion_package', 'must analyse the complete motion package');
  required(HASH.test(report.source_file_sha256) && report.source_file_sha256 === scene.manifestSha256,
    'source package manifest SHA-256 differs from the displayed source');
  required(report.source_manifest_sha256 === scene.manifestSha256, 'source manifest identity');
  required(report.source_package_id === scene.packageId, 'motion package ID');
  required(report.source_original_action_id === scene.originalClipId, 'original action identity');
  required(report.profile_sha256 === scene.expectedProfile.fingerprint &&
    report.type_uri === scene.expectedProfile.type_uri, 'exact typed source rig identity');
  required(report.source_start_pip === scene.startPip && report.source_sample_count === scene.sampleCount,
    'full captured source action pip bounds');
  required(scene.timingKind === 'time-only' && scene.musicTimingVerified === false &&
    scene.secondsPerPip === 1 / BPS, 'requires the 64-pip-per-second time-only transport');
  required(report.source_timing_kind === 'time-only; no verified musical tempo or downbeat',
    'source is not verified musical timing');
  required(Array.isArray(clips) && clips.length === scene.clipIds.length &&
    Array.isArray(report.source_clip_ids) && Array.isArray(report.source_clip_sha256) &&
    report.source_clip_ids.length === clips.length && report.source_clip_sha256.length === clips.length,
    'all source motion chunks must be accounted for');
  for (let i = 0; i < clips.length; i++) {
    required(clips[i]?.id === scene.clipIds[i] && report.source_clip_ids[i] === clips[i].id &&
      HASH.test(clips[i].sha256) && report.source_clip_sha256[i] === clips[i].sha256,
      `source chunk ${i + 1} changed`);
  }
  required(Array.isArray(report.source_range_seconds) && report.source_range_seconds.length === 2 &&
    report.source_range_seconds.every(finite) && report.source_range_seconds[0] < report.source_range_seconds[1] &&
    report.source_range_seconds[0] >= scene.startPip / BPS - 1e-6 &&
    report.source_range_seconds[1] <= scene.endPip / BPS + 1e-6,
    'source time interval');
  required(Number.isSafeInteger(report.source_calibration_omitted_pips) &&
    report.source_calibration_omitted_pips >= 0 && report.source_calibration_omitted_pips <= BPS,
    'calibration exclusion');
  required(Array.isArray(report.motion_accents) && report.motion_accents.length <= MAX_MARKERS,
    'bounded motion accents');
  const accents = report.motion_accents.map((accent, index) => {
    required(accent && finite(accent.seconds) && finite(accent.strength) &&
      accent.strength >= 0 && accent.strength <= 1 &&
      accent.seconds >= report.source_range_seconds[0] && accent.seconds <= report.source_range_seconds[1],
    `accent ${index + 1}`);
    return {seconds: accent.seconds, strength: accent.strength};
  });
  const tempo = report.recommended_tempo;
  required(tempo === null || tempo && finite(tempo.bpm) && tempo.bpm >= 30 && tempo.bpm <= 300,
    'estimated BPM must be finite and plausible');
  const map = report.estimated_beat_map;
  required((map === null) === (tempo === null), 'tempo and beat-map hypotheses must agree');
  let beats = [];
  if (map !== null) {
    required(map.format === 'dancerudiments.beat-map' && map.schema_version === 1 &&
      map.pips_per_beat === 64 && map.bpm_status === 'estimated' &&
      map.phase_status === 'estimated' && map.extrapolate === false &&
      map.interpolation === 'linear', 'beat map is an unverified hypothesis');
    required(Array.isArray(map.anchors) && map.anchors.length >= 2 && map.anchors.length <= MAX_MARKERS,
      'bounded beat map anchors');
    let priorSeconds = -Infinity, priorBeat = -Infinity;
    beats = map.anchors.map((point, index) => {
      required(point && finite(point.seconds) && Number.isSafeInteger(point.beat) &&
        point.seconds > priorSeconds && point.beat > priorBeat &&
        point.seconds >= report.source_range_seconds[0] - 1e-6 &&
        point.seconds <= report.source_range_seconds[1] + 1e-6,
        `beat ${index + 1} is not in the source time interval`);
      priorSeconds = point.seconds; priorBeat = point.beat;
      return point.seconds;
    });
  }
  required(Array.isArray(report.loop_candidates) && report.loop_candidates.length <= MAX_LOOPS,
    'bounded candidate loops');
  const loops = report.loop_candidates.map((loop, i) => {
    required(loop && finite(loop.start_seconds) && finite(loop.end_seconds) &&
      loop.start_seconds >= report.source_range_seconds[0] &&
      loop.end_seconds <= report.source_range_seconds[1] &&
      loop.end_seconds > loop.start_seconds &&
      loop.requires_review === true && loop.repaired === false &&
      ['estimated_motion_beat_grid', 'pose_recurrence_only'].includes(loop.alignment) &&
      finite(loop.score) && loop.score >= 0 && loop.score <= 1 &&
      (loop.beats === null || Number.isSafeInteger(loop.beats) && loop.beats > 0),
      `loop ${i + 1} must be unapproved, finite and source-bounded`);
    const {first, endExclusive} = sourceLoopPips(loop, scene);
    return {first, endExclusive, seconds: loop.end_seconds - loop.start_seconds,
      beats: loop.beats, alignment: loop.alignment, score: loop.score};
  });
  return {bpm: tempo?.bpm ?? null, beats, accents, loops};
}

export function createRhythmReview({sidebar, timeline, onSeek, onPreview}) {
  const style = document.createElement('style'); style.textContent = STYLE; document.head.append(style);
  const section = document.createElement('section'); section.className = 'rhythm-review';
  section.setAttribute('aria-label', 'Motion beat and loop estimates');
  const heading = document.createElement('div'); heading.className = 'section-label';
  heading.textContent = 'MOTION RHYTHM · UNVERIFIED'; section.append(heading);
  const summary = document.createElement('p'); summary.className = 'rhythm-summary';
  summary.textContent = 'Load a performance, then import its local StemLab analysis JSON.';
  section.append(summary);
  const fileLabel = document.createElement('label'); fileLabel.className = 'rhythm-file-label';
  fileLabel.textContent = 'Import analysis JSON';
  const input = document.createElement('input'); input.type = 'file'; input.accept = '.json,application/json';
  input.disabled = true; input.setAttribute('aria-label', 'Choose StemLab motion analysis JSON');
  fileLabel.append(input); section.append(fileLabel);
  const error = document.createElement('p'); error.className = 'rhythm-error';
  error.setAttribute('role', 'alert'); error.hidden = true; section.append(error);
  const list = document.createElement('div'); list.className = 'rhythm-loops';
  list.setAttribute('aria-label', 'Suggested loop regions'); section.append(list);
  const caution = document.createElement('p'); caution.className = 'rhythm-caution';
  caution.textContent = 'Motion beats are inferred, not music beat 1. Loop previews jump at the seam; foot planting, retargeting and skin continuity are unverified.';
  section.append(caution); sidebar.append(section);
  const markers = document.createElement('div'); markers.className = 'rhythm-markers';
  markers.setAttribute('aria-hidden', 'true'); timeline.append(markers);
  let scene = null, clips = null, parsed = null, active = null, serial = 0;
  const button = (name, fn, pressed) => {
    const el = document.createElement('button'); el.type = 'button'; el.textContent = name;
    el.setAttribute('aria-pressed', String(pressed)); el.addEventListener('click', fn); return el;
  };
  function draw() {
    list.replaceChildren(); markers.replaceChildren();
    if (!parsed || !scene) return;
    const length = scene.endPip - scene.startPip;
    const mark = (seconds, css) => {
      const pip = seconds * BPS;
      if (pip < scene.startPip || pip > scene.endPip || length <= 0) return;
      const el = document.createElement('span'); el.className = css;
      el.style.left = `${100 * (pip - scene.startPip) / length}%`;
      markers.append(el);
    };
    for (const beat of parsed.beats) mark(beat, 'rhythm-beat');
    for (const accent of parsed.accents) mark(accent.seconds, 'rhythm-accent');
    if (active) {
      mark(active.first / BPS, 'rhythm-loop-start');
      mark(active.endExclusive / BPS, 'rhythm-loop-end');
    }
    list.append(button('Full performance', () => {
      active = null; draw();
    }, active === null));
    parsed.loops.forEach((loop, i) => {
      const beats = loop.beats === null ? 'pose repeat' : `${loop.beats} estimated beats`;
      const desc = `Loop ${i + 1} · ${loop.seconds.toFixed(2)}s · ${beats} · score ${loop.score.toFixed(2)}`;
      list.append(button(desc, () => {
        active = loop; draw(); onSeek(loop.first); onPreview();
      }, active === loop));
    });
  }
  function reset() {
    serial++; scene = null; clips = null; parsed = null; active = null;
    input.disabled = true; input.value = ''; error.hidden = true;
    summary.textContent = 'Load a performance, then import its local StemLab analysis JSON.';
    draw();
  }
  function attach(target, manifestClips) {
    reset(); scene = target; clips = manifestClips;
    input.disabled = false;
    summary.textContent = 'Choose the StemLab JSON for this exact recorded action; files stay in your browser.';
  }
  function currentLoop() { return active; }
  function clearLoop() { if (active) { active = null; draw(); } }
  input.addEventListener('change', async () => {
    const file = input.files?.[0]; if (!file || !scene) return;
    const token = ++serial;
    error.hidden = true;
    try {
      required(file.size > 0 && file.size <= MAX_REPORT_BYTES, 'JSON exceeds the 2 MiB safety limit');
      const data = JSON.parse(await file.text());
      if (token !== serial || !scene) return;
      const result = validateMotionAnalysis(data, scene, clips);
      parsed = result; active = null;
      summary.textContent = result.bpm === null
        ? `${result.accents.length} motion accents; no defensible tempo estimate; ${result.loops.length} loop candidates.`
        : `≈${result.bpm.toFixed(1)} movement BPM · ${result.beats.length} estimated beats · ${result.loops.length} candidate loops.`;
      draw();
    } catch (cause) {
      if (token !== serial) return;
      parsed = null; active = null; draw();
      error.textContent = cause instanceof Error ? cause.message : String(cause); error.hidden = false;
      summary.textContent = 'Analysis rejected. Select the JSON for this exact motion-package recording.';
    } finally { input.value = ''; }
  });
  function diagnostics() { return {loaded: parsed !== null, bpm: parsed?.bpm ?? null,
    beatCount: parsed?.beats.length ?? 0, loopCount: parsed?.loops.length ?? 0,
    activeLoop: active ? {first: active.first, endExclusive: active.endExclusive} : null}; }
  return {attach, reset, currentLoop, clearLoop, diagnostics};
}
