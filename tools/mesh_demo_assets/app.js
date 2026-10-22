import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {createKandiBoomCharacter} from './kandi-boom.js';
import {PipTransport} from './transport.js';

// The builder checks these targets against the reviewed source-rig pins. They
// are independent of the package manifest fetched when the user loads a scene.
const config = __MESH_DEMO_CONFIG__;
const $ = id => document.getElementById(id);
const scenes = new Map(config.scenes.map(scene => [scene.id, scene]));
const stats = {pendingRequests: 0, activeNativeHandles: 0, disposedNativeHandles: 0,
  disposedGeometries: 0, nativeSampleCalls: 0};
let selected = config.scenes[0], session, generation = 0, renderer, controls, camera, world;
let animationFrame, pageClosed = false, initError;
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
function metadata() {
  const text = copy[selected.id];
  $('scene-select').value = selected.id;
  document.querySelectorAll('[data-scene]').forEach(button => {
    const active = button.dataset.scene === selected.id;
    button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active));
  });
  $('performance-title').textContent = text.title;
  $('performance-description').textContent = text.description;
  $('source-code').textContent = text.code;
  $('source-duration').textContent = `${selected.sourceDurationSeconds.toFixed(2)} seconds`;
  $('stage-caption').textContent = text.caption;
  $('timing-label').textContent = `Original ${selected.sourceFps.toFixed(2).replace(/\.00$/, '')} fps capture. Musical tempo and beat alignment are unverified. The calibration first frame is retained.`;
  $('source-link').href = selected.sourceUrl; $('source-link').title = selected.sourceTitle;
  $('licence-link').href = selected.noticePath;
  $('attribution').textContent = `${config.character.name} · ${config.character.series}. ${selected.attribution} BVH conversion: Bruce Hahne / cgspeed.`;
  $('load-scene').replaceChildren(document.createTextNode(`Load & play ${sceneName(selected)} `));
  const arrow = document.createElement('span'); arrow.setAttribute('aria-hidden', 'true'); arrow.textContent = '↗'; $('load-scene').append(arrow);
  const characterBytes = Object.values(config.character.assets).reduce((total, item) => total + item.byte_length, 0);
  $('load-size').textContent = `${(selected.compressedClipBytes / 1024 / 1024).toFixed(2)} MiB motion · ${(characterBytes / 1024 / 1024).toFixed(1)} MiB Kandi target · loaded on request`;
  $('duration').textContent = timeLabel((selected.endPip - selected.startPip) / 64);
  $('seek').min = String(selected.startPip); $('seek').max = String(selected.endPip);
  $('seek').value = String(selected.startPip); $('seek').style.setProperty('--progress', '0%');
}
function updateTransport() {
  const ready = Boolean(session?.ready), playing = Boolean(session?.transport?.playing);
  $('play-toggle').disabled = !ready; $('restart').disabled = !ready; $('seek').disabled = !ready;
  $('unload-scene').disabled = !session;
  $('play-toggle').setAttribute('aria-label', playing ? 'Pause' : 'Play');
  $('play-icon').innerHTML = playing ? '<path d="M6 5h4v14H6zm8 0h4v14h-4z"/>' : '<path d="m8 5 11 7-11 7z"/>';
  if (ready) {
    const pip = session.transport.pip(), scene = session.scene;
    $('seek').value = String(pip);
    $('seek').style.setProperty('--progress', `${100 * (pip - scene.startPip) / Math.max(1, scene.endPip - scene.startPip)}%`);
    $('elapsed').textContent = timeLabel((pip - scene.startPip) / 64);
    $('pip-readout').textContent = `pip ${pip.toLocaleString()} / ${scene.endPip.toLocaleString()}`;
    $('timing-status').textContent = session.transport.speed === 1 ? 'Source time · 1×' : `Source time · ${session.transport.speed}× preview`;
    status(session.pending ? 'Loading motion…' : playing ? 'Performing' : pip === scene.endPip ? 'Performance complete' : 'Paused', playing);
  }
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
  try { return await fetch(url, {...options, credentials: 'omit'}); }
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
  const previous = session; session = null;
  if (previous) {
    previous.closed = true; previous.controller.abort(); previous.transport?.pause();
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
  if (!current(owner) || !owner.active) return;
  const pip = owner.desiredPip, motion = owner.active.motion;
  if (pip < motion.startPip || pip >= motion.startPip + motion.sampleCount || owner.lastPip === pip) return;
  const physical = motion.sample(pip); // Native C++/WASM sampling, then channel-unit decoding.
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
    owner.loader = runtime.createMotionPackageLoader({
      manifestUrl: new URL(owner.scene.manifestPath, location.href), packageId: owner.scene.packageId,
      manifestSha256: owner.scene.manifestSha256,
      expectedProfile: {typeUri: expected.type_uri, sha256: expected.fingerprint, dimensions: expected.dimensions},
      fetch: trackedFetch,
      nativeFactory: async (recording, options) => {
        const native = await adapter(recording, options); let alive = true;
        stats.activeNativeHandles++;
        return {sample(pip) {
          const row = native.sample(pip); stats.nativeSampleCalls++;
          owner.nativePip = pip; owner.normalizedSample = Array.from(row); return row;
        }, dispose() {
          if (!alive) return; alive = false; native.dispose(); stats.activeNativeHandles--; stats.disposedNativeHandles++;
        }};
      },
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
    owner.transport.setSpeed(Number($('speed').value));
    // Establish source root-motion zero at the retained calibration frame, then
    // frame the real Kandi skin using a moving pose before returning to start.
    await sampleAt(owner, owner.scene.startPip);
    if (!current(owner)) return;
    await sampleAt(owner, Math.min(owner.scene.startPip + 64, owner.scene.endPip));
    if (!current(owner)) return;
    owner.character.frameOnFloor();
    await sampleAt(owner, owner.scene.startPip);
    if (!current(owner)) return;
    owner.followPosition = owner.character.rootBone.getWorldPosition(new THREE.Vector3());
    resetCamera(); owner.ready = true;
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) owner.transport.play();
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
  if (!session?.ready) return;
  const transport = session.transport;
  if (transport.playing) transport.pause();
  else { if (transport.pip() === transport.last) transport.seek(transport.first); transport.play(); }
  updateTransport();
}
function seek(pip) {
  if (!session?.ready) return;
  session.transport.seek(pip);
  const owner = session; sampleAt(owner, pip).catch(error => fail(error, owner)); updateTransport();
}
function frame() {
  if (pageClosed) return;
  const owner = session;
  if (owner?.ready) {
    const pip = owner.transport.pip();
    try { void sampleAt(owner, pip).catch(error => fail(error, owner)); }
    catch (error) { fail(error, owner); }
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
  if (!session?.ready) return; seek(session.scene.startPip); session?.transport.play(); updateTransport();
});
$('seek').addEventListener('input', event => seek(Number(event.target.value)));
$('speed').addEventListener('change', event => { session?.transport?.setSpeed(Number(event.target.value)); updateTransport(); });
$('reset-view').addEventListener('click', resetCamera);
$('stage').addEventListener('keydown', event => { if (event.code === 'Space') { event.preventDefault(); togglePlay(); } });
document.addEventListener('visibilitychange', () => {
  if (document.hidden && session?.ready) { session.transport.pause(); updateTransport(); }
});
window.meshDemo = Object.freeze({
  debugSnapshot() {
    const owner = session, character = owner?.character;
    return {
      ready: Boolean(owner?.ready), sceneId: owner?.scene.id ?? null, selectedSceneId: selected.id,
      loadedChunkId: owner?.active?.id ?? null, currentPip: owner?.nativePip ?? null,
      playing: Boolean(owner?.transport?.playing), nativeNormalizedSample: owner?.normalizedSample?.slice() ?? null,
      physicalSample: owner?.physicalSample?.slice() ?? null,
      skinnedMeshCount: character?.stats.skinnedMeshCount ?? 0, vertexCount: character?.stats.vertexCount ?? 0,
      boneCount: character?.stats.boneCount ?? 0, weightedVertexCount: character?.stats.weightedVertexCount ?? 0,
      blendedVertexCount: character?.stats.blendedVertexCount ?? 0,
      representativeDeformedVertices: character?.representativeVertices() ?? [],
      jointNames: character?.sourceJointNames ?? [],
      jointWorldMatrices: character?.sourceJointWorldMatrices() ?? [],
      rigTransforms: character?.targetBones.map(bone => ({name: bone.name, position: bone.position.toArray(), quaternion: bone.quaternion.toArray(), matrixWorld: bone.matrixWorld.toArray()})) ?? [],
      characterName: character ? config.character.name : null, targetRigFingerprint: character ? config.character.rigFingerprint : null,
      runtimeInfluenceLimit: character?.stats.runtimeInfluenceLimit ?? null,
      activeNativeHandles: stats.activeNativeHandles, disposedNativeHandles: stats.disposedNativeHandles,
      disposedGeometries: stats.disposedGeometries, pendingRequests: stats.pendingRequests + (owner?.pending ? 1 : 0),
      nativeSampleCalls: stats.nativeSampleCalls, loadedCacheIds: owner?.active ? [owner.active.id] : [],
      disposed: !owner, error: $('error').hidden ? null : $('error').textContent,
      build: config.build,
    };
  },
});
metadata(); $('build-version').textContent = `DanceRudiments ${config.build.version} · ${config.build.commit.slice(0, 7)}`;
let disposeStage;
try { disposeStage = initializeStage(); animationFrame = requestAnimationFrame(frame); }
catch (error) { initError = Error(`This preview needs WebGL 2. ${error.message}`); showError(initError); status('3D rendering unavailable'); }
window.addEventListener('pagehide', () => {
  pageClosed = true; cancelAnimationFrame(animationFrame); unload(); disposeStage?.();
}, {once: true});
