import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {createKandiBoomCharacter} from './kandi-boom.js';
import {PipTransport} from './transport.js';
import {createRhythmReview} from './rhythm-review.js';
import {createDerivativeReview, validateFinishedMotion} from './derivative-review.js';
import {createLoopWorkspace} from './loop-workspace.js';

// The builder checks these targets against the reviewed source-rig pins. They
// are independent of the package manifest fetched when the user loads a scene.
const config = __MESH_DEMO_CONFIG__;
const $ = id => document.getElementById(id);
const scenes = new Map(config.scenes.map(scene => [scene.id, scene]));
const stats = {pendingRequests: 0, activeNativeHandles: 0, disposedNativeHandles: 0,
  disposedGeometries: 0, nativeSampleCalls: 0};
let selected = config.scenes[0], session, generation = 0, renderer, controls, camera, world;
let animationFrame, pageClosed = false, initError;
let loopWorkspace = null;
const sceneName = () => config.character.name;
const copy = {
  boxbot: {title: 'Kandi Boom takes the salsa floor.', description: 'Kandi Boom retargets a complete captured salsa performance while keeping the original source timing.', code: 'CMU 60_01', caption: '01 / KANDI BOOM / SALSA'},
  prism: {title: 'Kandi Boom turns through ballet.', description: 'Kandi Boom retargets a captured sequence of arabesques, turning jumps and deep back bends.', code: 'CMU 05_18', caption: '02 / KANDI BOOM / BALLET'},
};
function timeLabel(seconds) {
  const minutes = Math.floor(seconds / 60), remaining = Math.max(0, seconds - minutes * 60);
  return `${minutes}:${remaining.toFixed(2).padStart(5, '0')}`;
}
function showError(error) {
  $('error').textContent = error instanceof Error ? error.message : String(error);
  $('error').hidden = false;
}
function status(text, live = false) {
  $('status').textContent = text; $('status-dot').classList.toggle('live', live);
}
// Keep the existing numeric options and source-time sampler; label the three
// standard musical rate interpretations without claiming source BPM is known.
for (const [value, label] of [
  ['0.5', 'Half time · 0.5×'],
  ['1', 'Original time · 1×'],
  ['2', 'Double time · 2×'],
]) {
  const option = Array.from($('speed').options).find(item => item.value === value);
  if (option) option.textContent = label;
}
function metadata() {
  const text = copy[selected.id] ?? {title:selected.title || 'Review an imported Action on Kandi.',
    description:selected.description || 'Inspect the selected original motion and its separately corrected loop.',
    code:selected.sourceTitle || selected.id,caption:'LOCAL MOTION REVIEW · KANDI BOOM'};
  $('scene-select').value = selected.id;
  document.querySelectorAll('[data-scene]').forEach(button => {
    button.hidden = !scenes.has(button.dataset.scene);
    const active = button.dataset.scene === selected.id;
    button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active));
  });
  $('performance-title').textContent = text.title;
  $('performance-description').textContent = text.description;
  $('source-code').textContent = text.code;
  $('source-duration').textContent = `${selected.sourceDurationSeconds.toFixed(2)} seconds`;
  $('stage-caption').textContent = text.caption;
  $('timing-label').textContent = `Original ${selected.sourceFps.toFixed(2).replace(/\.00$/, '')} fps capture. ${selected.calibrationLabel || 'Musical tempo and beat alignment are unverified. The calibration first frame is retained.'}`;
  $('source-link').href = selected.sourceUrl; $('source-link').title = selected.sourceTitle;
  $('licence-link').href = selected.noticePath;
  $('attribution').textContent = `${config.character.name} · ${config.character.series}. ${selected.attribution}${copy[selected.id] ? ' BVH conversion: Bruce Hahne / cgspeed.' : ''}`;
  $('load-scene').replaceChildren(document.createTextNode(`${config.reviewWorkspace?'Load':'Load & play'} ${sceneName(selected)} `));
  const arrow = document.createElement('span'); arrow.setAttribute('aria-hidden', 'true'); arrow.textContent = '↗'; $('load-scene').append(arrow);
  const characterBytes = Object.values(config.character.assets).reduce((total, item) => total + item.byte_length, 0);
  $('load-size').textContent = `${(selected.compressedClipBytes / 1024 / 1024).toFixed(2)} MiB motion · ${(characterBytes / 1024 / 1024).toFixed(1)} MiB Kandi target · loaded on request`;
  $('duration').textContent = timeLabel((selected.endPip - selected.startPip) / 64);
  $('seek').min = String(selected.startPip); $('seek').max = String(selected.endPip);
  $('seek').value = String(selected.startPip); $('seek').style.setProperty('--progress', '0%');
}
function updateTransport() {
  const ready = Boolean(session?.ready), playing = Boolean(session?.transport?.playing);
  const audioDriven = Boolean(loopWorkspace?.active()||session?.audition);
  $('play-toggle').disabled = !ready || audioDriven; $('restart').disabled = !ready || audioDriven;
  $('seek').disabled = !ready || audioDriven; $('speed').disabled = audioDriven;
  $('unload-scene').disabled = !session;
  $('play-toggle').setAttribute('aria-label', playing ? 'Pause' : 'Play');
  $('play-icon').innerHTML = playing ? '<path d="M6 5h4v14H6zm8 0h4v14h-4z"/>' : '<path d="m8 5 11 7-11 7z"/>';
  if (ready) {
    const range = playbackRange(session), pip = Math.min(range.last, session.transport.pip());
    $('seek').min = String(range.first); $('seek').max = String(range.last);
    $('seek').value = String(pip);
    $('seek').style.setProperty('--progress', `${100 * (pip - range.first) / Math.max(1, range.last - range.first)}%`);
    $('elapsed').textContent = timeLabel((pip - range.first) / session.transport.pipsPerSecond);
    $('duration').textContent = timeLabel((range.last - range.first) / session.transport.pipsPerSecond);
    $('pip-readout').textContent = `pip ${pip.toLocaleString()} / ${range.last.toLocaleString()}`;
    const rateLabel = session.transport.timeMode === 'half' ? 'Half-time source motion · 0.5×'
      : session.transport.timeMode === 'double' ? 'Double-time source motion · 2×'
      : session.transport.timeMode === 'normal' ? 'Original source motion · 1×'
      : `Source-motion preview · ${session.transport.speed}×`;
    $('timing-status').textContent = audioDriven ? 'Master audio clock · use the loop review controls'
      : session.derivative
      ? `${session.derivativeMode === 'finished' ? 'Finished clip · numerical checks passed' : 'Original window comparison'} · ${session.transport.speed}× · visual / musical review pending`
      : rhythmReview.currentLoop() ? `Unverified loop · ${rateLabel}` : rateLabel;
    status(session.pending ? 'Loading motion…' : session.audition ? 'Song clock' : playing ? 'Performing' : pip === range.last ? 'Performance complete' : 'Paused', playing||Boolean(session.audition));
  }
}
function playbackRange(owner) {
  if (owner.derivative) return owner.derivativeMode === 'finished'
    ? {first: owner.derivative.info.first, last: owner.derivative.info.last}
    : {first: owner.derivative.info.sourceFirstPip, last: owner.derivative.info.sourceEndPip};
  return {first: owner.scene.startPip, last: owner.scene.endPip};
}
function resetCamera() {
  if (!camera || !controls) return;
  const focus = session?.followPosition ?? new THREE.Vector3();
  camera.position.set(3.3 + focus.x, 2.7, 5.4 + focus.z);
  controls.target.set(focus.x, 1.2, focus.z); controls.update();
}
function initializeStage() {
  renderer = new THREE.WebGLRenderer({canvas: $('stage'), antialias: true, alpha: true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.25;
  world = new THREE.Scene(); world.fog = new THREE.Fog('#e8ece2', 13, 32);
  camera = new THREE.PerspectiveCamera(35, 1, .05, 80);
  controls = new OrbitControls(camera, $('stage'));
  controls.enableDamping = true; controls.dampingFactor = .07; controls.enablePan = true;
  controls.minDistance = 3.2; controls.maxDistance = 12; controls.maxPolarAngle = Math.PI * .49;
  world.add(new THREE.HemisphereLight('#fffdf1', '#9cae8b', 2.4));
  const sun = new THREE.DirectionalLight('#fff9e7', 3.1); sun.position.set(3, 8, 4); sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024); sun.shadow.camera.left = -8; sun.shadow.camera.right = 8;
  sun.shadow.camera.top = 8; sun.shadow.camera.bottom = -8; sun.shadow.normalBias = .015;
  world.add(sun); world.add(sun.target);
  const rim = new THREE.DirectionalLight('#c8dfef', 1.3); rim.position.set(-4, 4, -4); world.add(rim);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({color: '#e7ecdf', roughness: 1}));
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; ground.position.y = -.015; world.add(ground);
  const grid = new THREE.GridHelper(32, 64, '#cdd7c0', '#dbe2d1'); grid.material.transparent = true; grid.material.opacity = .34; grid.position.y = -.009; world.add(grid);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(1.8, .006, 4, 96), new THREE.MeshBasicMaterial({color: '#b4c5a3', transparent: true, opacity: .48}));
  ring.rotation.x = -Math.PI / 2; ring.position.y = -.006; world.add(ring);
  resetCamera();
  const resize = new ResizeObserver(() => {
    const width = $('viewport').clientWidth, height = $('viewport').clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix();
  });
  resize.observe($('viewport'));
  return () => {
    resize.disconnect(); controls.dispose();
    world.traverse(object => { object.geometry?.dispose(); if (Array.isArray(object.material)) object.material.forEach(m => m.dispose()); else object.material?.dispose(); });
    sun.shadow.map?.dispose(); renderer.dispose(); renderer.forceContextLoss();
  };
}
async function trackedFetch(url, options = {}) {
  stats.pendingRequests++;
  try { return await fetch(url, {...options, credentials: config.reviewWorkspace || config.collectionAudition ? 'same-origin' : 'omit'}); }
  finally { stats.pendingRequests--; }
}
async function verifiedAsset(path, sha256, limit, signal) {
  const response = await trackedFetch(new URL(path, location.href), {signal});
  if (!response.ok) throw Error(`Asset request failed: HTTP ${response.status}`);
  const chunks = [], reader = response.body?.getReader(); let length = 0;
  if (!reader) throw Error('Streaming asset reads are unavailable');
  try {
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      if (signal.aborted) throw new DOMException('Scene load cancelled', 'AbortError');
      length += value.byteLength; if (length > limit) throw Error('Scene asset exceeds its size limit'); chunks.push(value);
    }
  } catch (error) { await reader.cancel().catch(() => {}); throw error; }
  finally { reader.releaseLock(); }
  const bytes = new Uint8Array(length); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  const actual = Array.from(digest, value => value.toString(16).padStart(2, '0')).join('');
  if (actual !== sha256) throw Error('Scene asset SHA-256 mismatch');
  return bytes;
}
function releaseChunk(owner) {
  owner.chunkGeneration++;
  if (owner.pending) { owner.pending.controller.abort(); owner.loader?.unload(owner.pending.id); owner.pending = null; }
  if (owner.active) { owner.loader?.unload(owner.active.id); owner.active = null; }
}
function unload({clearError = true} = {}) {
  generation++;
  loopWorkspace?.detached();
  rhythmReview.reset();
  derivativeReview.reset();
  const previous = session; session = null;
  if (previous) {
    previous.closed = true; previous.controller.abort(); previous.transport?.pause();
    previous.derivativeGeneration++; previous.derivative?.loaded.dispose(); previous.derivative = null;
    previous.auditionGeneration=(previous.auditionGeneration||0)+1;previous.audition?.dispose();previous.audition=null;
    releaseChunk(previous); previous.loader?.dispose(); previous.character?.dispose();
    previous.loader = previous.character = previous.module = null;
  }
  if (clearError) $('error').hidden = true;
  $('empty-state').hidden = false; $('loading-state').hidden = true;
  $('elapsed').textContent = '0:00.00'; $('pip-readout').textContent = '64 integer pips / second';
  $('timing-status').textContent = 'Source-time preview'; $('mesh-label').textContent = 'Weighted mesh';
  $('resource-note').textContent = previous ? 'Kandi geometry, textures, motion cache and native handles released.' : 'Kandi and motion data stay unloaded until you choose a performance.';
  metadata(); updateTransport(); status(previous ? 'Kandi Boom unloaded' : 'Ready when you are'); resetCamera();
}
function current(owner) { return !owner.closed && session === owner && !owner.controller.signal.aborted; }
function applyPose(owner) {
  if (!current(owner)) return;
  const pip = owner.desiredPip, motion = owner.audition?.motion ?? (owner.derivativeMode === 'finished'
    ? owner.derivative?.loaded.motion : owner.active?.motion);
  if (!motion) return;
  if (pip < motion.startPip || pip >= motion.startPip + motion.sampleCount || owner.lastPip === pip) return;
  const physical = motion.sample(pip); // Native C++/WASM sampling, then channel-unit decoding.
  if (!owner.character.isCalibrated()) {
    if (owner.calibrationPose) {
      if (owner.calibrationPose.profile_sha256 !== owner.scene.expectedProfile.fingerprint ||
          !/^[a-f0-9]{64}$/.test(owner.calibrationPose.source_capture_sha256 || '') ||
          !Number.isFinite(owner.calibrationPose.source_time_seconds))
        throw Error('Explicit source calibration identity differs from the selected profile');
      owner.character.calibrateChannels(motion.profile, owner.calibrationPose.values);
    } else {
      if (pip !== (owner.scene.calibrationPip ?? owner.scene.startPip) || owner.scene.calibrationFrameCount !== 1)
        throw Error('Kandi Boom must be calibrated from its declared source calibration pose');
      owner.character.calibrateChannels(motion.profile, physical);
    }
  }
  owner.character.applyChannels(motion.profile, physical); owner.physicalSample = Array.from(physical);
  owner.lastPip = pip;
  if (owner.followPosition) {
    const root = owner.character.rootBone.getWorldPosition(new THREE.Vector3());
    const delta = new THREE.Vector3(root.x - owner.followPosition.x, 0, root.z - owner.followPosition.z);
    camera.position.add(delta); controls.target.add(delta); owner.followPosition.copy(root);
  }
}
function sampleAt(owner, pip) {
  if (!current(owner)) return Promise.resolve();
  if (owner.derivativeMode === 'finished') {
    const range = playbackRange(owner);
    if (!Number.isSafeInteger(pip) || pip < range.first || pip > range.last)
      return Promise.reject(Error('Host clock pip is outside the finished clip'));
    owner.desiredPip = pip; applyPose(owner); return Promise.resolve();
  }
  if (!Number.isSafeInteger(pip) || pip < owner.scene.startPip || pip > owner.scene.endPip)
    return Promise.reject(Error('Host clock pip is outside the complete performance'));
  owner.desiredPip = pip;
  const descriptor = owner.chunks.find(item => pip >= item.start_pip && pip < item.start_pip + item.sample_count);
  if (!descriptor) return Promise.reject(Error('Selected performance has a missing chunk'));
  if (owner.active?.id === descriptor.id) { applyPose(owner); return Promise.resolve(); }
  if (owner.pending?.id === descriptor.id) return owner.pending.promise;
  releaseChunk(owner);
  const token = owner.chunkGeneration, controller = new AbortController();
  const pending = {id: descriptor.id, controller, promise: null}; owner.pending = pending;
  pending.promise = owner.loader.load(descriptor.id, {signal: controller.signal}).then(motion => {
    if (!current(owner) || token !== owner.chunkGeneration) return;
    owner.pending = null; owner.active = {id: descriptor.id, motion}; applyPose(owner);
  }).catch(error => {
    if (!current(owner) || token !== owner.chunkGeneration || error.name === 'AbortError') return;
    owner.pending = null; throw error;
  });
  return pending.promise;
}
function fail(error, owner) {
  if (owner && !current(owner)) return;
  unload({clearError: false}); showError(error); status('Unable to load this performance');
}
async function loadSelected() {
  if (initError) { showError(initError); return; }
  unload();
  const owner = {scene: selected, controller: new AbortController(), closed: false, ready: false,
    token: generation, chunkGeneration: 0, desiredPip: selected.startPip, lastPip: null,
    derivativeGeneration: 0, derivative: null, derivativeMode: null,
    normalizedSample: null, physicalSample: null, nativePip: null};
  session = owner; const signal = owner.controller.signal;
  $('empty-state').hidden = true; $('loading-state').hidden = false; $('error').hidden = true;
  $('loading-message').textContent = `Loading ${sceneName(selected)}’s performance…`;
  status('Loading selected scene…'); updateTransport();
  try {
    const target = config.character.assets;
    const [runtime, wasm, rigBytes, targetRigBytes, fbx, albedo, normal, roughness, metallic] = await Promise.all([
      import('../../bindings/typescript/motion-packages.ts'),
      verifiedAsset('recording.wasm', config.recordingWasm.sha256, config.recordingWasm.byte_length, signal),
      verifiedAsset(owner.scene.rigPath, owner.scene.sceneRigSha256, 1024 * 1024, signal),
      verifiedAsset(target.rig.path, target.rig.sha256, target.rig.byte_length, signal),
      verifiedAsset(target.fbx.path, target.fbx.sha256, target.fbx.byte_length, signal),
      verifiedAsset(target.albedo.path, target.albedo.sha256, target.albedo.byte_length, signal),
      verifiedAsset(target.normal.path, target.normal.sha256, target.normal.byte_length, signal),
      verifiedAsset(target.roughness.path, target.roughness.sha256, target.roughness.byte_length, signal),
      verifiedAsset(target.metallic.path, target.metallic.sha256, target.metallic.byte_length, signal),
    ]);
    if (!current(owner)) return;
    const rig = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(rigBytes));
    owner.calibrationPose = rig.calibrationPose ?? null;
    const targetRig = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(targetRigBytes));
    const expected = owner.scene.expectedProfile;
    if (rig.sceneId !== owner.scene.id || rig.quaternionOrder !== 'wxyz' ||
        rig.expectedProfile?.type_uri !== expected.type_uri || rig.expectedProfile?.fingerprint !== expected.fingerprint ||
        JSON.stringify(rig.expectedProfile?.dimensions) !== JSON.stringify(expected.dimensions)) throw Error('Saved source-motion rig identity mismatch');
    if (targetRig.type_uri !== config.character.typeUri || targetRig.fingerprint_sha256 !== config.character.rigFingerprint ||
        targetRig.fbx_asset_sha256 !== config.character.fbxAssetSha256) throw Error('Kandi Boom target-rig identity mismatch');
    owner.module = await WebAssembly.compile(wasm);
    if (!current(owner)) return;
    const adapter = runtime.createRecordingWasmAdapter(owner.module);
    owner.runtime = runtime;
    owner.nativeFactory = async (recording, options) => {
      const native = await adapter(recording, options); let alive = true;
      stats.activeNativeHandles++;
      return {sample(pip) {
        const row = native.sample(pip); stats.nativeSampleCalls++;
        owner.nativePip = pip; owner.normalizedSample = Array.from(row); return row;
      }, dispose() {
        if (!alive) return; alive = false; native.dispose(); stats.activeNativeHandles--; stats.disposedNativeHandles++;
      }};
    };
    owner.loader = runtime.createMotionPackageLoader({
      manifestUrl: new URL(owner.scene.manifestPath, location.href), packageId: owner.scene.packageId,
      manifestSha256: owner.scene.manifestSha256,
      expectedProfile: {typeUri: expected.type_uri, sha256: expected.fingerprint, dimensions: expected.dimensions},
      fetch: trackedFetch,
      nativeFactory: owner.nativeFactory,
    });
    const manifest = await owner.loader.catalogue({signal});
    if (!current(owner)) return;
    owner.chunks = owner.scene.clipIds.map(id => manifest.clips.find(clip => clip.id === id)).sort((a, b) => (a?.start_pip ?? 0) - (b?.start_pip ?? 0));
    let boundary = owner.scene.startPip;
    for (const [index, chunk] of owner.chunks.entries()) {
      if (!chunk || chunk.start_pip !== boundary || chunk.metadata?.original_clip_id !== owner.scene.originalClipId ||
          chunk.metadata?.chunk_index !== index || chunk.metadata?.chunk_count !== owner.chunks.length ||
          chunk.metadata?.timing_kind !== 'time-only') throw Error('Scene requires its complete, contiguous time-only performance');
      boundary += chunk.sample_count;
    }
    if (boundary !== owner.scene.endPip + 1) throw Error('Scene performance bounds do not match the saved selection');
    owner.character = await createKandiBoomCharacter(rig, targetRig, {fbx, albedo, normal, roughness, metallic},
      {onGeometryDisposed: () => stats.disposedGeometries++});
    if (!current(owner)) { owner.character.dispose(); return; }
    world.add(owner.character.group);
    owner.transport = new PipTransport(owner.scene.startPip, owner.scene.endPip);
    owner.originalTransport = owner.transport;
    owner.transport.setSpeed(Number($('speed').value));
    // Establish source root-motion zero at the retained calibration frame, then
    // frame the real Kandi skin using a moving pose before returning to start.
    await sampleAt(owner, owner.calibrationPose ? owner.scene.startPip : (owner.scene.calibrationPip ?? owner.scene.startPip));
    if (!current(owner)) return;
    await sampleAt(owner, Math.min(owner.scene.startPip + 64, owner.scene.endPip));
    if (!current(owner)) return;
    owner.character.frameOnFloor();
    await sampleAt(owner, owner.scene.startPip);
    if (!current(owner)) return;
    owner.followPosition = owner.character.rootBone.getWorldPosition(new THREE.Vector3());
    owner.verifiedProfile = owner.active.motion.profile;
    resetCamera(); owner.ready = true;
    rhythmReview.attach(owner.scene, owner.chunks);
    derivativeReview.attach();
    if (!loopWorkspace && !matchMedia('(prefers-reduced-motion: reduce)').matches) owner.transport.play();
    $('loading-state').hidden = true; $('mesh-label').textContent = `${owner.character.stats.vertexCount.toLocaleString()} Kandi vertices`;
    $('resource-note').textContent = 'One selected motion chunk in memory. Switching performances unloads Kandi and the previous recording.';
    updateTransport();
  } catch (error) {
    if (!current(owner) || error.name === 'AbortError') return;
    fail(error, owner);
  }
}
function choose(id) {
  if (!scenes.has(id) || id === selected.id) return;
  unload(); selected = scenes.get(id); metadata();
  status('Ready when you are');
}
function togglePlay() {
  if (loopWorkspace?.active()) return;
  if (!session?.ready) return;
  const transport = session.transport;
  if (transport.playing) transport.pause();
  else { if (transport.pip() === transport.last) transport.seek(rhythmReview.currentLoop()?.first ?? playbackRange(session).first); transport.play(); }
  updateTransport();
}
function seek(pip) {
  if (!session?.ready) return;
  session.transport.seek(pip);
  const owner = session; sampleAt(owner, pip).catch(error => fail(error, owner)); updateTransport();
}
const rhythmReview = createRhythmReview({
  sidebar: document.querySelector('.sidebar'),
  timeline: document.querySelector('.timeline'),
  onSeek: seek,
  onPreview: () => { if (session?.ready) { session.transport.play(); updateTransport(); } },
});
function selectDerivativeMode(owner, mode) {
  if (!current(owner) || !owner.derivative) return;
  owner.transport.pause(); owner.derivativeMode = mode;
  owner.transport = owner.derivative.transports[mode];
  owner.transport.pause(); owner.transport.setSpeed(Number($('speed').value));
  owner.transport.seek(playbackRange(owner).first); owner.lastPip = null;
  const pip = playbackRange(owner).first;
  sampleAt(owner, pip).catch(error => fail(error, owner)); updateTransport();
}
function clearDerivative(owner) {
  if (!current(owner)) return;
  owner.derivativeGeneration++;
  const previous = owner.derivative;
  if (!previous) return;
  owner.transport.pause(); previous.loaded.dispose(); owner.derivative = null; owner.derivativeMode = null;
  owner.transport = owner.originalTransport; owner.transport.pause();
  owner.transport.setSpeed(Number($('speed').value)); owner.transport.seek(previous.originalPip);
  owner.lastPip = null; rhythmReview.attach(owner.scene, owner.chunks);
  sampleAt(owner, previous.originalPip).catch(error => fail(error, owner)); updateTransport();
  $('resource-note').textContent = 'Original performance restored. The finished recording handle has been released.';
}
const derivativeReview = createDerivativeReview({
  sidebar: document.querySelector('.sidebar'),
  onLoad: loadFinishedMotion,
  onMode(mode) { if (session?.derivative) selectDerivativeMode(session, mode); },
  onRepeat(value) { if (session?.derivative) session.derivative.repeat = value; },
  onClear() { if (session) clearDerivative(session); },
});
async function loadFinishedMotion(bytes, report) {
    const owner = session;
    if (!owner?.ready || !owner.verifiedProfile) throw Error('Load the matching Kandi performance first');
    const token = ++owner.derivativeGeneration;
    const info = await validateFinishedMotion(bytes, report, owner.scene);
    if (!current(owner) || token !== owner.derivativeGeneration) return null;
    const loaded = await owner.runtime.createStandaloneRigMotion(bytes, {
      profile: owner.verifiedProfile, profileSha256: owner.scene.expectedProfile.fingerprint,
      nativeFactory: owner.nativeFactory, signal: owner.controller.signal,
    });
    if (!current(owner) || token !== owner.derivativeGeneration) { loaded.dispose(); return null; }
    owner.transport.pause();
    const originalPip = owner.derivative?.originalPip ?? owner.originalTransport.pip();
    owner.derivative?.loaded.dispose();
    // The final clock pip is an exclusive stop marker, never a sampled pose.
    // This preserves all N half-open samples and a period of N pips on repeat.
    owner.derivative = {loaded, info, originalPip, repeat: false, repeatCount: 0, transports: {
      finished: new PipTransport(info.first, info.last + 1, () => performance.now(), 1 / info.pipSeconds),
      original: new PipTransport(info.sourceFirstPip, info.sourceEndPip + 1),
    }};
    rhythmReview.reset(); selectDerivativeMode(owner, 'finished');
    $('resource-note').textContent = 'Original source and separate finished clip retained. Both use the same native sampler and calibrated Kandi skin.';
    return info;
}
loopWorkspace = createLoopWorkspace({sidebar:document.querySelector('.sidebar'),config,host:{
  async prepare(document) {
    if (!scenes.has(document.scene_id)) throw Error('This workspace has no matching source scene');
    if (selected.id !== document.scene_id) choose(document.scene_id);
    if (!session?.ready) await loadSelected();
    if (!session?.ready) throw Error('The source rig and Kandi assets could not be loaded');
    session.transport.pause();updateTransport();
  },
  loadFinished:loadFinishedMotion,
  mode(value) { if(session?.derivative) selectDerivativeMode(session,value); },
  pause() { session?.transport?.pause();updateTransport(); },
  audioPose(value) {
    const owner=session;if(!owner?.ready||!owner.derivative)return;
    owner.transport.pause();owner.character.group.visible=Boolean(value);
    if(!value)return;
    const range=playbackRange(owner),pip=owner.derivativeMode==='finished'?value.pip:
      Math.max(range.first,Math.min(range.last,Math.floor(value.source_seconds*64)));
    if(pip<range.first||pip>range.last)return;
    owner.transport.seek(pip);void sampleAt(owner,pip).catch(error=>fail(error,owner));
  },
}});
if(loopWorkspace)document.querySelectorAll('.rhythm-review').forEach(panel=>{panel.hidden=true;});
function frame() {
  if (pageClosed) return;
  const owner = session;
  if (owner?.ready) {
    if(!owner.audition&&!loopWorkspace?.frame()) {
      const wasPlaying = owner.transport.playing;
      let pip = owner.transport.pip();
      const loop = rhythmReview.currentLoop();
      if (owner.derivative) {
        const range = playbackRange(owner);
        if (pip > range.last && owner.derivative.repeat && wasPlaying) {
          owner.derivative.repeatCount++;
          owner.transport.seek(range.first); owner.transport.play(); pip = range.first;
        } else pip = Math.min(pip, range.last);
      } else if (loop && pip >= Math.min(loop.endExclusive, owner.scene.endPip)) {
        owner.transport.seek(loop.first);
        pip = loop.first;
      }
      try { void sampleAt(owner, pip).catch(error => fail(error, owner)); }
      catch (error) { fail(error, owner); }
    }
    updateTransport();
  }
  controls?.update(); if (renderer && world && camera) renderer.render(world, camera);
  animationFrame = requestAnimationFrame(frame);
}
$('scene-select').addEventListener('change', event => choose(event.target.value));
document.querySelectorAll('[data-scene]').forEach(button => button.addEventListener('click', () => choose(button.dataset.scene)));
$('load-scene').addEventListener('click', () => { void loadSelected(); });
$('unload-scene').addEventListener('click', () => unload());
$('cancel-load').addEventListener('click', () => unload());
$('play-toggle').addEventListener('click', togglePlay);
$('restart').addEventListener('click', () => {
  if (!session?.ready) return; seek(rhythmReview.currentLoop()?.first ?? playbackRange(session).first); session?.transport.play(); updateTransport();
});
$('seek').addEventListener('input', event => { rhythmReview.clearLoop(); seek(Number(event.target.value)); });
$('speed').addEventListener('change', event => { session?.transport?.setSpeed(Number(event.target.value)); updateTransport(); });
$('reset-view').addEventListener('click', resetCamera);
$('stage').addEventListener('keydown', event => { if (event.code === 'Space') { event.preventDefault(); togglePlay(); } });
document.addEventListener('visibilitychange', () => {
  if (document.hidden && session?.ready) { session.transport.pause(); loopWorkspace?.pause(); updateTransport(); }
});
window.meshDemo = Object.freeze({
  debugSnapshot() {
    const owner = session, character = owner?.character;
    const characterDiagnostics = character?.diagnostics() ?? null;
    return {
      ready: Boolean(owner?.ready), sceneId: owner?.scene.id ?? null, selectedSceneId: selected.id,
      loadedChunkId: owner?.active?.id ?? null, currentPip: owner?.nativePip ?? null,
      playing: Boolean(owner?.transport?.playing), nativeNormalizedSample: owner?.normalizedSample?.slice() ?? null,
      physicalSample: owner?.physicalSample?.slice() ?? null,
      skinnedMeshCount: character?.stats.skinnedMeshCount ?? 0, vertexCount: character?.stats.vertexCount ?? 0,
      characterVisible: Boolean(character?.group.visible),
      boneCount: character?.stats.boneCount ?? 0, weightedVertexCount: character?.stats.weightedVertexCount ?? 0,
      blendedVertexCount: character?.stats.blendedVertexCount ?? 0,
      representativeDeformedVertices: character?.representativeVertices() ?? [],
      jointNames: character?.sourceJointNames ?? [],
      jointWorldMatrices: character?.sourceJointWorldMatrices() ?? [],
      rigTransforms: character?.targetBones.map(bone => ({name: bone.name, position: bone.position.toArray(), quaternion: bone.quaternion.toArray(), matrixWorld: bone.matrixWorld.toArray()})) ?? [],
      characterName: character ? config.character.name : null, targetRigFingerprint: character ? config.character.rigFingerprint : null,
      runtimeInfluenceLimit: character?.stats.runtimeInfluenceLimit ?? null, characterDiagnostics,
      activeNativeHandles: stats.activeNativeHandles, disposedNativeHandles: stats.disposedNativeHandles,
      disposedGeometries: stats.disposedGeometries, pendingRequests: stats.pendingRequests + (owner?.pending ? 1 : 0),
      nativeSampleCalls: stats.nativeSampleCalls, loadedCacheIds: owner?.active ? [owner.active.id] : [],
      rhythmAnalysis: rhythmReview.diagnostics(),
      finishedMotionReview: derivativeReview.diagnostics(),
      loopWorkspace:loopWorkspace?.diagnostics()??null,
      finishedMotion: owner?.derivative ? {repairId: owner.derivative.info.repair.repair_id,
        profileSha256: owner.derivative.loaded.motion.profileSha256,
        startPip: owner.derivative.loaded.motion.startPip, sampleCount: owner.derivative.loaded.motion.sampleCount,
        repeatCount: owner.derivative.repeatCount,
        numericalChecksPassed: true, visualReviewVerified: false} : null,
      auditionMotion:owner?.audition?{profileSha256:owner.audition.motion.profileSha256,
        startPip:owner.audition.motion.startPip,sampleCount:owner.audition.motion.sampleCount}:null,
      disposed: !owner, error: $('error').hidden ? null : $('error').textContent,
      build: config.build,
    };
  },
});
// Read-only, opt-in host clock adapter. Every pose still comes from the shared
// native recording sampler; no review/export or musical approval is granted.
if(config.collectionAudition){
  window.meshAudition=Object.freeze({
    async prepare(sceneId){
      if(!scenes.has(sceneId))throw Error('Unknown prepared source scene');
      if(selected.id!==sceneId)choose(sceneId);
      if(!session?.ready)await loadSelected();
      if(!session?.ready||session.scene.id!==sceneId)throw Error('Source scene did not load');
      session.transport.pause();updateTransport();
    },
    async loadMotion(input,expectedHash,expectedProfile){
      const owner=session;
      if(!owner?.ready||owner.scene.expectedProfile.fingerprint!==expectedProfile)throw Error('Audition source profile differs');
      if(!ArrayBuffer.isView(input)||input.byteLength<1||input.byteLength>32*1024*1024||!/^[a-f0-9]{64}$/.test(expectedHash))throw Error('Invalid audition motion bytes');
      const token=owner.auditionGeneration=(owner.auditionGeneration||0)+1;
      const bytes=new Uint8Array(input.buffer,input.byteOffset,input.byteLength);
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
      if(hash!==expectedHash)throw Error('Audition motion hash differs');
      if(!current(owner)||owner.auditionGeneration!==token)throw Error('Audition source changed');
      const loaded=await owner.runtime.createStandaloneRigMotion(bytes,{profile:owner.verifiedProfile,
        profileSha256:expectedProfile,nativeFactory:owner.nativeFactory,signal:owner.controller.signal});
      if(!current(owner)||owner.auditionGeneration!==token){loaded.dispose();throw Error('Audition source changed');}
      owner.audition?.dispose();owner.audition=loaded;owner.lastPip=null;owner.transport.pause();
      status('Audio-driven loop audition',true);
      return {startPip:loaded.motion.startPip,sampleCount:loaded.motion.sampleCount,profileSha256:loaded.motion.profileSha256};
    },
    pose(fraction){
      const owner=session;if(!owner?.ready||!owner.audition)return;
      owner.character.group.visible=Number.isFinite(fraction)&&fraction>=0&&fraction<=1;
      if(!owner.character.group.visible)return;
      const motion=owner.audition.motion;
      owner.desiredPip=motion.startPip+Math.min(motion.sampleCount-1,Math.floor(fraction*motion.sampleCount));
      applyPose(owner);
    },
    original(){const owner=session;if(!owner?.ready)return;owner.audition?.dispose();owner.audition=null;owner.lastPip=null;owner.transport.seek(owner.scene.startPip);owner.transport.play();status('Original source time · musical mapping unverified',true);},
    unload(){unload();},
  });
  document.title='Collection mesh audition · DanceRudiments';
  const layout=document.createElement('style');layout.textContent='body{margin:0;overflow:hidden}.topbar,.intro,.sidebar,.transport,.about-strip,footer{display:none!important}main{max-width:none;margin:0;padding:0}.workspace{display:block}.viewport{height:100vh;min-height:300px;aspect-ratio:auto;border-radius:0}';document.head.append(layout);
}
if(config.scenes.some(scene=>!copy[scene.id])){
  $('scene-select').replaceChildren(...config.scenes.map(scene=>{
    const option=document.createElement('option');option.value=scene.id;option.textContent=scene.title||scene.id;return option;
  }));
}
if(config.reviewWorkspace){
  document.querySelector('.sidebar>.section-label').hidden=true;
  $('scene-cards').hidden=true;
  document.title='Local loop review · DanceRudiments';
  document.querySelector('meta[name="description"]').content='Review one imported Action on Kandi Boom, finish a selected loop, and save timing and visual decisions.';
  const emphasis=document.createElement('em');emphasis.textContent='Finish its loop.';
  $('page-title').replaceChildren('Review one Action.',document.createElement('br'),emphasis);
  document.querySelector('.intro-copy').textContent='Audition the original motion and corrected phrase on Kandi Boom. Set the timing to your exact audio, then save your review.';
  const mark=document.createElement('span');document.querySelector('.eyebrow').replaceChildren(mark,' LOCAL LOOP REVIEW. KANDI BOOM.');
  document.querySelector('.wordmark-light').textContent='Loop Review';
  document.querySelector('.wordmark').href='#page-title';
  document.querySelector('.back-link').textContent='Local review session';document.querySelector('.back-link').href='#page-title';
  document.querySelector('.source-note strong').textContent='Exact source. Separate decisions.';
  document.querySelector('.about-strip p').textContent='Kandi Boom uses the declared source rig and calibration. The original motion, corrected loop and saved review remain separately identified.';
  const credits=$('licence-link');credits.textContent='Source credits and terms ↗';
  document.querySelector('.about-strip p:last-child').replaceChildren('Local source and exact audio master',document.createElement('br'),credits);
}
metadata(); $('build-version').textContent = `DanceRudiments ${config.build.version} · ${config.build.commit.slice(0, 7)}`;
let disposeStage;
try { disposeStage = initializeStage(); animationFrame = requestAnimationFrame(frame); }
catch (error) { initError = Error(`This preview needs WebGL 2. ${error.message}`); showError(initError); status('3D rendering unavailable'); }
window.addEventListener('pagehide', () => {
  pageClosed = true; cancelAnimationFrame(animationFrame); loopWorkspace?.dispose(); unload(); disposeStage?.();
}, {once: true});
