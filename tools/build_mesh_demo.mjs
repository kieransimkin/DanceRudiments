#!/usr/bin/env node
/** Build the separate, lazy-loading character route with pinned local assets. */
import {build} from 'esbuild';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {readFile, writeFile, mkdir, mkdtemp, rename, rm, lstat, realpath, readdir, copyFile} from 'node:fs/promises';
import {dirname, resolve, join, relative, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseArgs} from 'node:util';

const ROOT = fileURLToPath(new URL('../', import.meta.url));
const ASSETS = join(ROOT, 'tools/mesh_demo_assets');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const jsonBytes = value => JSON.stringify(value, null, 2) + '\n';
const hashPattern = /^[0-9a-f]{64}$/;
function safePath(path) {
  if (typeof path !== 'string' || !/^[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/.test(path) ||
      path.split('/').some(part => part === '.' || part === '..')) throw Error('Unsafe scene asset path');
  return path;
}
async function boundedFile(path, max = 64 * 1024 * 1024) {
  const info = await lstat(path);
  if (info.isSymbolicLink() || !info.isFile() || info.size < 1 || info.size > max)
    throw Error(`Invalid or oversized build input: ${path}`);
  return readFile(path);
}
async function preflight(parent) {
  await mkdir(parent, {recursive: true});
  const dir = await mkdtemp(join(parent, '.mesh-demo-probe-'));
  try {
    const before = join(dir, 'before'), after = join(dir, 'after');
    await writeFile(before, 'mesh-demo-build');
    if ((await readFile(before, 'utf8')) !== 'mesh-demo-build') throw Error('Temporary output probe failed');
    await rename(before, after); await rm(after);
  } finally { await rm(dir, {recursive: true}); }
}
function sameTarget(a, b) {
  return a?.type_uri === b?.type_uri && a?.fingerprint === b?.fingerprint &&
    JSON.stringify(a?.dimensions) === JSON.stringify(b?.dimensions);
}
async function listFiles(root, base = '') {
  const files = [];
  for (const entry of (await readdir(join(root, base), {withFileTypes: true})).sort((a,b) => a.name.localeCompare(b.name))) {
    const name = base ? `${base}/${entry.name}` : entry.name;
    if (entry.isSymbolicLink()) throw Error('Build output must not contain symlinks');
    if (entry.isDirectory()) files.push(...await listFiles(root, name));
    else if (entry.isFile()) files.push(name);
  }
  return files;
}

export async function buildMeshDemo({assetsDir = join(ROOT, '.cache/mesh-demo-assets'),
  outputDir = join(ROOT, 'dist/pages/meshes'), version, commit} = {}) {
  const sourceRoot = await realpath(resolve(assetsDir)), output = resolve(outputDir);
  if (output === ROOT || output === sourceRoot || sourceRoot.startsWith(output + sep) ||
      output === resolve('/') || output === dirname(ROOT)) throw Error('Unsafe mesh output directory');
  const pkg = JSON.parse(await readFile(join(ROOT, 'package.json'), 'utf8'));
  version ??= pkg.version;
  commit ??= execFileSync('git', ['rev-parse', 'HEAD'], {cwd: ROOT, encoding: 'utf8'}).trim();
  if (!/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[A-Za-z0-9.-]+)?(?:\+[A-Za-z0-9.-]+)?$/.test(version) ||
      !/^[0-9a-f]{40}$/.test(commit)) throw Error('A semantic version and full source commit are required');
  const dependencyVersions = {};
  for (const [name, expected] of Object.entries({three: '0.186.1', esbuild: '0.28.2'})) {
    const actual = JSON.parse(await readFile(join(ROOT, 'node_modules', name, 'package.json'), 'utf8')).version;
    if (actual !== expected || pkg.devDependencies?.[name] !== expected)
      throw Error(`Mesh renderer requires the reviewed exact ${name}@${expected} build dependency`);
    dependencyVersions[name] = actual;
  }
  await preflight(dirname(output));
  let existed = false;
  try {
    const info = await lstat(output);
    if (info.isSymbolicLink() || !info.isDirectory()) throw Error('Output is not an owned mesh demo directory');
    const receipt = JSON.parse(await readFile(join(output, 'build.json'), 'utf8'));
    if (receipt.format !== 'dancerudiments.mesh-demo-build') throw Error('Refusing to replace an unrelated output directory');
    existed = true;
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  const pinBytes = await boundedFile(join(ROOT, 'tools/mesh_demo_sources.json'), 2 * 1024 * 1024);
  const pins = JSON.parse(pinBytes.toString('utf8'));
  const catalogueBytes = await boundedFile(join(sourceRoot, 'catalogue.json'), 2 * 1024 * 1024);
  const catalogue = JSON.parse(catalogueBytes.toString('utf8'));
  if (pins.format !== 'dancerudiments.mesh-demo-sources' || catalogue.format !== 'dancerudiments.mesh-demo-catalogue' ||
      catalogue.schema_version !== 1 || !Array.isArray(catalogue.scenes) || catalogue.scenes.length !== 2 ||
      !Array.isArray(pins.scenes) || pins.scenes.length !== 2) throw Error('Expected the reviewed two-scene asset catalogue');
  const sceneIds = new Set(), files = new Map([['catalogue.json', catalogueBytes]]), assetHashes = {};
  async function asset(path, expectedHash, byteLength, limit) {
    safePath(path);
    const absolute = join(sourceRoot, path), real = await realpath(absolute);
    if (!real.startsWith(sourceRoot + sep)) throw Error('Scene asset resolves outside its source root');
    const bytes = await boundedFile(absolute, limit);
    if (byteLength !== undefined && bytes.length !== byteLength) throw Error(`Scene asset length mismatch: ${path}`);
    if (expectedHash !== undefined && (!hashPattern.test(expectedHash) || sha(bytes) !== expectedHash)) throw Error(`Scene asset SHA-256 mismatch: ${path}`);
    files.set(path, bytes); assetHashes[path] = {sha256: sha(bytes), byte_length: bytes.length}; return bytes;
  }
  for (const scene of catalogue.scenes) {
    const pin = pins.scenes.find(item => item.id === scene.id);
    if (!pin || sceneIds.has(scene.id) || !['boxbot', 'prism'].includes(scene.id) ||
        scene.characterKind !== pin.characterKind || scene.packageId !== pin.packageId ||
        !sameTarget(scene.expectedProfile, pin.expectedProfile) || scene.sceneRigSha256 !== pin.sceneRigSha256 ||
        scene.manifestPath !== `motions/${scene.id}/manifest.json` || scene.rigPath !== `motions/${scene.id}/scene-rig.json` ||
        scene.timingKind !== 'time-only' || scene.musicTimingVerified !== false || scene.secondsPerPip !== 1 / 64 ||
        scene.sourceSha256 !== pin.source.sha256 || scene.originalClipId !== pin.source.sha256 ||
        !Number.isSafeInteger(scene.startPip) || !Number.isSafeInteger(scene.endPip) || scene.endPip < scene.startPip ||
        scene.sampleCount !== scene.endPip - scene.startPip + 1 || !Array.isArray(scene.clipIds) || !scene.clipIds.length)
      throw Error('Prepared scene differs from the independent, reviewed source-rig selection');
    sceneIds.add(scene.id);
    // Targets embedded in the frontend are sourced explicitly from the checked-in
    // scene pins, never assigned from a fetched package manifest at runtime.
    scene.expectedProfile = structuredClone(pin.expectedProfile);
    const manifest = JSON.parse((await asset(scene.manifestPath, scene.manifestSha256, undefined, 8 * 1024 * 1024)).toString('utf8'));
    if (manifest.id !== pin.packageId || manifest.type_uri !== pin.expectedProfile.type_uri ||
        manifest.profile_sha256 !== pin.expectedProfile.fingerprint ||
        JSON.stringify(manifest.dimensions) !== JSON.stringify(pin.expectedProfile.dimensions) ||
        !Array.isArray(manifest.clips) || manifest.clips.length !== scene.clipIds.length)
      throw Error('Prepared package does not match the independent scene target');
    const base = `motions/${scene.id}/`;
    const profile = await asset(base + safePath(manifest.profile.path), pin.expectedProfile.fingerprint, manifest.profile.byte_length);
    const profileDocument = JSON.parse(profile.toString('ascii'));
    if (profileDocument.channels?.some((channel, i) => channel.number !== i + 1 || channel.name !== pin.expectedProfile.dimensions[i]))
      throw Error('Prepared profile channel numbers changed');
    const rig = JSON.parse((await asset(scene.rigPath, pin.sceneRigSha256, undefined, 1024 * 1024)).toString('utf8'));
    if (rig.sceneId !== scene.id || !sameTarget(rig.expectedProfile, pin.expectedProfile) || rig.quaternionOrder !== 'wxyz')
      throw Error('Prepared rest rig identity mismatch');
    let boundary = scene.startPip;
    for (const [index, id] of scene.clipIds.entries()) {
      const clip = manifest.clips.find(item => item.id === id);
      if (!clip || clip.start_pip !== boundary || clip.metadata?.chunk_index !== index ||
          clip.metadata?.chunk_count !== scene.clipIds.length || clip.metadata?.original_clip_id !== scene.originalClipId ||
          clip.metadata?.timing_kind !== 'time-only') throw Error('The showcase requires each complete contiguous performance');
      boundary += clip.sample_count;
      await asset(base + safePath(clip.path), clip.sha256, clip.byte_length);
    }
    if (boundary !== scene.endPip + 1) throw Error('Complete performance pip bounds changed');
    for (const name of ['README.md', 'LICENSE.txt', 'THIRD_PARTY_NOTICES.md', 'SOURCES.json']) await asset(base + name);
    if (scene.noticePath !== base + 'THIRD_PARTY_NOTICES.md' || scene.licensePath !== base + 'LICENSE.txt') throw Error('Scene notice links changed');
    if (scene.browserReferencePath) {
      if (scene.browserReferencePath !== base + 'browser-reference.json') throw Error('Unexpected browser evidence path');
      await asset(scene.browserReferencePath, scene.browserReferenceSha256, undefined, 1024 * 1024);
    }
  }
  // Reuse the existing source-verifying WASM packaging operation. No new sampler.
  execFileSync(process.execPath, [join(ROOT, 'tools/package_recording_runtime.mjs')], {cwd: ROOT, stdio: 'pipe'});
  const wasm = await boundedFile(join(ROOT, 'dist/recording/recording.wasm'), 1024 * 1024);
  const runtimeReceipt = JSON.parse(await readFile(join(ROOT, 'dist/recording/recording.wasm.json'), 'utf8'));
  if (sha(wasm) !== runtimeReceipt.wasm_sha256 || !WebAssembly.validate(wasm)) throw Error('Native recording WASM integrity mismatch');
  const buildInfo = {version, commit, renderer: dependencyVersions, sourcePlanSha256: sha(pinBytes),
    preparedCatalogueSha256: sha(catalogueBytes), nativeRuntime: runtimeReceipt};
  const config = {scenes: catalogue.scenes, recordingWasm: {sha256: sha(wasm), byte_length: wasm.length}, build: buildInfo};
  const temporary = await mkdtemp(join(dirname(output), '.mesh-demo-build-'));
  const stage = join(temporary, 'meshes'); await mkdir(stage);
  let backup;
  try {
    for (const [path, bytes] of files) { await mkdir(dirname(join(stage, path)), {recursive: true}); await writeFile(join(stage, path), bytes); }
    await writeFile(join(stage, 'recording.wasm'), wasm);
    await writeFile(join(stage, 'recording.wasm.json'), jsonBytes(runtimeReceipt));
    await copyFile(join(ASSETS, 'index.html'), join(stage, 'index.html'));
    await copyFile(join(ASSETS, 'style.css'), join(stage, 'style.css'));
    await copyFile(join(ROOT, 'node_modules/three/LICENSE'), join(stage, 'THREE-LICENSE.txt'));
    await copyFile(join(ROOT, 'LICENSE'), join(stage, 'RUNTIME-LICENSE.txt'));
    const bundle = await build({absWorkingDir: ROOT, entryPoints: [join(ASSETS, 'app.js')], outdir: stage,
      bundle: true, splitting: true, format: 'esm', platform: 'browser', target: ['es2022'], charset: 'utf8',
      minify: true, legalComments: 'linked', entryNames: 'app', chunkNames: 'chunks/[name]-[hash]',
      sourcemap: false, metafile: true, define: {__MESH_DEMO_CONFIG__: JSON.stringify(config)}, logLevel: 'silent'});
    if (Object.values(bundle.metafile.outputs).some(file => file.imports.some(item => item.external)))
      throw Error('Mesh demo must bundle every renderer/runtime import locally');
    const outputs = {};
    for (const name of await listFiles(stage)) {
      const bytes = await readFile(join(stage, name)); outputs[name] = {sha256: sha(bytes), byte_length: bytes.length};
    }
    const receipt = {format: 'dancerudiments.mesh-demo-build', schema_version: 1, ...buildInfo,
      sceneIds: [...sceneIds], assets: assetHashes, files: outputs,
      sourceTiming: 'time-only; 64 integer pips per second; no inferred music BPM/phase',
      originalCharacters: ['boxbot', 'prism'], eagerMotionLoads: 0};
    await writeFile(join(stage, 'build.json'), jsonBytes(receipt));
    if (existed) { backup = join(temporary, 'previous'); await rename(output, backup); }
    try { await rename(stage, output); }
    catch (error) { if (backup) await rename(backup, output); throw error; }
    return {output_dir: output, scene_count: sceneIds.size, file_count: Object.keys(outputs).length + 1,
      byte_length: Object.values(outputs).reduce((total, file) => total + file.byte_length, 0) + Buffer.byteLength(jsonBytes(receipt)),
      version, commit, assets: [...sceneIds].map(id => ({id, clip_bytes: catalogue.scenes.find(scene => scene.id === id).compressedClipBytes}))};
  } finally { await rm(temporary, {recursive: true}); }
}

async function main() {
  const {values} = parseArgs({options: {'assets-dir': {type: 'string'}, 'output-dir': {type: 'string'},
    version: {type: 'string'}, commit: {type: 'string'}, help: {type: 'boolean'}}, strict: true});
  if (values.help) { console.log('node tools/build_mesh_demo.mjs [--assets-dir .cache/mesh-demo-assets] [--output-dir dist/pages/meshes] [--version X.Y.Z] [--commit FULL_SHA]'); return; }
  console.log(JSON.stringify(await buildMeshDemo({assetsDir: values['assets-dir'], outputDir: values['output-dir'],
    version: values.version, commit: values.commit}), null, 2));
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
