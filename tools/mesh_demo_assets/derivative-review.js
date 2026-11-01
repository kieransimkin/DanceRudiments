/** Explicit local review of a separately compiled, numerically checked loop.
 * Original packages, Kandi calibration and source recordings are never changed.
 */
const HASH = /^[a-f0-9]{64}$/;
export const MAX_DERIVATIVE_BYTES = 64 * 1024 * 1024;
const MAX_REPAIR_BYTES = 2 * 1024 * 1024;
const finite = x => typeof x === 'number' && Number.isFinite(x);
function requireValue(condition, reason) {
  if (!condition) throw Error(`Invalid finished motion: ${reason}`);
}
function same(left, right) {
  if (left === right) return true;
  if (left === null || right === null || typeof left !== 'object' || typeof right !== 'object') return false;
  if (Array.isArray(left) || Array.isArray(right))
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((v,i) => same(v,right[i]));
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length && keys.every(k => Object.hasOwn(right,k) && same(left[k],right[k]));
}

export async function validateFinishedMotion(bytes, repair, scene) {
  requireValue(bytes instanceof Uint8Array && bytes.length > 0 && bytes.length <= MAX_DERIVATIVE_BYTES,
    'local motion exceeds 64 MiB');
  requireValue(repair?.format === 'dancerudiments.loop-repair' && repair.schema_version === 1
    && repair.method === 'bounded-local-pose-and-tangent-v1',
    'a matching loop-repair report is required');
  requireValue(repair.accepted === true && repair.status === 'numerically_closed_review_candidate'
    && repair.requires_review === true && repair.loop_seam_approved === false
    && repair.target_mesh_verified === false && repair.audio_beat_alignment_verified === false
    && Array.isArray(repair.rejection_reasons) && repair.rejection_reasons.length === 0,
    'the correction must pass its numeric gate and still require target review');
  requireValue(HASH.test(repair.compiled_motion_sha256), 'report has no compiled-motion byte identity');
  const hash = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  const actual = Array.from(hash, b => b.toString(16).padStart(2, '0')).join('');
  requireValue(actual === repair.compiled_motion_sha256, 'motion bytes do not match the repair report');
  const motion = JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(bytes));
  const recording = motion?.recording, p = recording?.provenance, embedded = p?.source_provenance?.repair;
  requireValue(p?.source_provenance?.producer === 'dancerudiments.offline-loop-repair'
    && p.source_provenance.loop_policy === 'closed_endpoint_capture_for_half_open_compilation'
    && p.repair_method === repair.method, 'unrecognized correction provenance');
  requireValue(motion?.format === 'dancerudiments.rig-motion' && motion.schema_version === 1
    && motion.profile_sha256 === scene.expectedProfile.fingerprint
    && motion.type_uri === scene.expectedProfile.type_uri
    && repair.source_profile_sha256 === scene.expectedProfile.fingerprint,
    'exact active source rig/profile differs');
  requireValue(HASH.test(scene.sourceSha256) && repair.original_source_sha256 === scene.sourceSha256
    && p?.original_source_sha256 === scene.sourceSha256, 'original source recording differs');
  requireValue(p?.motion_kind === 'repaired_loop_candidate' && p.numerical_repeat_seam_verified === true
    && p.repeat_seam_verified === false && p.musical_timing_verified === false && p.target_mesh_verified === false,
    'recording must retain separate numerical and visual/musical states');
  requireValue(HASH.test(repair.repair_id) && p.repair_id === repair.repair_id, 'repair identity differs');
  requireValue(HASH.test(repair.source_capture_sha256)
    && p.original_capture_sha256 === repair.source_capture_sha256, 'original capture identity differs');
  requireValue(HASH.test(repair.corrected_capture_sha256)
    && p.corrected_capture_sha256 === repair.corrected_capture_sha256
    && p.source_capture_sha256 === repair.corrected_capture_sha256, 'corrected capture identity differs');
  for (const key of ['repair_id','source_capture_sha256','source_profile_sha256','method',
                     'source_start_seconds','source_end_seconds','period_seconds','sample_count',
                     'options','after','corrections','activity_retention','contacts','translation_scale'])
    requireValue(same(embedded?.[key], repair[key]), `embedded correction evidence differs at ${key}`);
  const first = repair.source_start_seconds, end = repair.source_end_seconds;
  requireValue(finite(first) && finite(end) && first >= scene.startPip/64 && end > first
    && end <= scene.sourceDurationSeconds + 1e-8 && finite(repair.period_seconds)
    && Math.abs(end-first-repair.period_seconds) < 1e-7
    && same(p.repair_source_bounds_seconds, [first,end]), 'original source window is inconsistent');
  const count = recording?.samples?.length, clock = recording?.clock;
  requireValue(Number.isSafeInteger(count) && count >= 64 && count % 64 === 0 && repair.sample_count === count+1
    && clock?.start_pip === 0 && finite(clock.bpm) && clock.bpm >= 30 && clock.bpm <= 300
    && clock.bpm_status === 'estimated' && clock.phase_status === 'estimated'
    && p.suggested_loop_period_pips === count,
    'half-open 64-pip derivative bounds or estimated clock differ');
  const o = repair.options, after = repair.after, changes = repair.corrections;
  const scale = repair.translation_scale ?? 1;
  requireValue(o && after && changes && o.sample_count === repair.sample_count
    && finite(scale) && scale > 0
    && finite(o.closure_tolerance) && o.closure_tolerance > 0 && o.closure_tolerance <= 1e-4
    && finite(o.tangent_tolerance) && o.tangent_tolerance > 0 && o.tangent_tolerance <= 1e-3,
    'unbounded numeric closure tolerances');
  for (const [measurement, limit] of [
    [after.max_rotation_seam_radians, o.closure_tolerance],
    [after.max_translation_seam/scale, o.closure_tolerance],
    [after.max_scalar_seam_fraction, o.closure_tolerance],
    [repair.period_seconds*after.max_rotation_velocity_jump_radians_per_second, o.tangent_tolerance],
    [repair.period_seconds*after.max_translation_velocity_jump/scale, o.tangent_tolerance],
    [repair.period_seconds*after.max_scalar_velocity_jump_fraction_per_second, o.tangent_tolerance],
    [changes.max_rotation_radians,o.max_rotation_correction_radians],
    [changes.max_translation_fraction,o.max_translation_correction_fraction],
    [changes.max_scalar_fraction,o.max_scalar_correction_fraction],
    [changes.rms_fraction,o.max_correction_rms_fraction],
  ]) requireValue(finite(measurement) && measurement >= 0 && finite(limit) && limit > 0
    && measurement <= limit+1e-12, 'a reported numerical correction gate fails');
  requireValue(after.discrete_seam_matches === true && finite(repair.activity_retention)
    && finite(o.min_activity_retention) && finite(o.max_activity_increase)
    && repair.activity_retention >= o.min_activity_retention
    && repair.activity_retention <= o.max_activity_increase, 'motion activity/discrete seam gate fails');
  requireValue(Number.isSafeInteger(repair.contacts?.provided_count) && repair.contacts.provided_count >= 0
    && (repair.contacts.provided_count === 0 || repair.contacts.constraints_satisfied === true),
    'supplied foot constraints did not pass');
  const compiled = repair.compiled_verification;
  requireValue(compiled?.format === 'dancerudiments.compiled-loop-check' && compiled.schema_version === 1
    && compiled.method === 'all_decoded_samples_and_half_open_wrap_v1' && compiled.passed === true
    && compiled.loop_seam_approved === false && HASH.test(compiled.compiled_motion_fingerprint)
    && compiled.corrected_capture_sha256 === repair.corrected_capture_sha256
    && Array.isArray(compiled.rejection_reasons) && compiled.rejection_reasons.length === 0,
    'compiled rows and repeat boundary have not passed their separate numerical check');
  for (const [value, limit] of [
    [compiled.max_normalized_scalar_sample_error,2e-10],
    [compiled.max_rotation_sample_error_radians,1e-8],
    [repair.period_seconds*compiled.after?.max_rotation_velocity_jump_radians_per_second,o.tangent_tolerance],
    [repair.period_seconds*compiled.after?.max_translation_velocity_jump/scale,o.tangent_tolerance],
    [repair.period_seconds*compiled.after?.max_scalar_velocity_jump_fraction_per_second,o.tangent_tolerance],
  ]) requireValue(finite(value) && value>=0 && value<=limit+1e-12, 'compiled sample or wrap-tangent check fails');
  requireValue(compiled.after?.discrete_seam_matches === true, 'compiled discrete repeat boundary differs');
  if (repair.contacts.provided_count > 0) {
    requireValue(Array.isArray(compiled.contacts) && compiled.contacts.length === repair.contacts.provided_count,
      'compiled contact evidence is incomplete');
    for (const contact of compiled.contacts) for (const [value,limit] of [
      [contact.max_slip_fraction,o.max_contact_slip_fraction],
      [contact.max_speed_fraction_per_second,o.max_contact_speed_fraction_per_second],
    ]) requireValue(finite(value) && value>=0 && finite(limit) && limit>0 && value<=limit+1e-12,
      'compiled contact slip/speed limit fails');
  }
  return {motion, repair, first:0, last:count-1, periodPips:count, pipSeconds:60/clock.bpm/64,
    sourceFirstPip:Math.ceil(first*64-1e-8), sourceEndPip:Math.min(scene.endPip,Math.ceil(end*64-1e-8)-1),
    sourceStartSeconds:first, sourceEndSeconds:end};
}

export function createDerivativeReview({sidebar, onLoad, onMode, onRepeat, onClear}) {
  const section = document.createElement('section'); section.className = 'rhythm-review';
  section.setAttribute('aria-label','Finished loop target review');
  const heading = document.createElement('div'); heading.className = 'section-label';
  heading.textContent = 'FINISHED LOOP · KANDI REVIEW'; section.append(heading);
  const summary = document.createElement('p'); summary.className = 'rhythm-summary'; section.append(summary);
  function file(label, aria) {
    const wrap = document.createElement('label'); wrap.className = 'rhythm-file-label'; wrap.textContent = label;
    const input = document.createElement('input'); input.type='file'; input.accept='.json,application/json';
    input.setAttribute('aria-label',aria); wrap.append(input); section.append(wrap); return input;
  }
  const motionInput = file('Finished motion JSON','Choose finished rig motion JSON');
  const reportInput = file('Matching repair report','Choose matching loop repair report');
  const buttons = document.createElement('div'); buttons.className='rhythm-loops'; section.append(buttons);
  function button(label, action) { const b=document.createElement('button'); b.type='button'; b.textContent=label;
    b.addEventListener('click',action); buttons.append(b); return b; }
  const error = document.createElement('p'); error.className='rhythm-error'; error.setAttribute('role','alert');
  error.hidden=true; section.append(error);
  let attached=false, loaded=false, mode='finished', repeat=false, serial=0;
  const load = button('Load finished clip', async () => {
    if (!attached) return;
    const token=++serial; error.hidden=true;
    try {
      const a=motionInput.files?.[0], b=reportInput.files?.[0];
      requireValue(a && b && a.size>0 && a.size<=MAX_DERIVATIVE_BYTES && b.size>0 && b.size<=MAX_REPAIR_BYTES,
        'select both the motion and its matching report');
      const bytes=new Uint8Array(await a.arrayBuffer()), report=JSON.parse(await b.text());
      if (token!==serial || !attached) return;
      const info=await onLoad(bytes,report);
      if (token!==serial || !attached || !info) return;
      loaded=true; mode='finished'; repeat=false; repeatInput.checked=false;
      summary.textContent=`${info.sourceStartSeconds.toFixed(2)}–${info.sourceEndSeconds.toFixed(2)}s of the original. Numerical checks passed; inspect Kandi's feet and repeat boundary.`;
      draw();
    } catch(cause) {
      if (token!==serial) return;
      error.textContent=cause instanceof Error ? cause.message : String(cause); error.hidden=false;
    }
  });
  const original=button('Compare original',()=>{if(loaded){onMode('original');mode='original';draw();}});
  const finished=button('Finished clip',()=>{if(loaded){onMode('finished');mode='finished';draw();}});
  const clear=button('Clear clip',()=>{serial++;onClear();loaded=false;repeat=false;repeatInput.checked=false;draw();
    summary.textContent='Original performance restored. Select another local correction to review.';});
  const repeatLabel=document.createElement('label'); repeatLabel.className='rhythm-summary';
  const repeatInput=document.createElement('input'); repeatInput.type='checkbox';
  repeatInput.setAttribute('aria-label','Repeat finished loop for visual review');
  repeatInput.addEventListener('change',()=>{repeat=Boolean(repeatInput.checked);onRepeat(repeat);});
  repeatLabel.append(repeatInput,document.createTextNode(' Repeat for visual seam review')); section.append(repeatLabel);
  const note=document.createElement('p'); note.className='rhythm-caution';
  note.textContent='Files stay in this browser. This is a separately corrected clip; target skin, ground contact and musical alignment still need review.';
  section.append(note);sidebar.append(section);
  function draw(){motionInput.disabled=reportInput.disabled=load.disabled=!attached;
    original.disabled=finished.disabled=clear.disabled=!loaded;repeatInput.disabled=!loaded;
    original.setAttribute('aria-pressed',String(loaded&&mode==='original'));
    finished.setAttribute('aria-pressed',String(loaded&&mode==='finished'));}
  function reset(){serial++;attached=false;loaded=false;repeat=false;mode='finished';
    motionInput.value=reportInput.value='';repeatInput.checked=false;error.hidden=true;
    summary.textContent='Load Kandi Boom, then select a finished clip and its repair report.';draw();}
  function attach(){reset();attached=true;draw();}
  function diagnostics(){return {loaded,mode:loaded?mode:null,repeat:loaded&&repeat,targetVisualReview:'unverified'};}
  reset();return {attach,reset,diagnostics};
}
