#!/usr/bin/env python3
"""Apply the final Kandi Boom production-gallery integration to DanceRudiments.

Run from the DanceRudiments repository root. The patcher is intentionally
pattern-strict: if another change touched the same integration seams it stops
instead of guessing or overwriting unrelated work.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path.cwd().resolve()
BUNDLE = Path(__file__).resolve().parent
PAYLOAD = BUNDLE / 'payload'
TOUCHED = [
    'tools/build_mesh_demo.mjs',
    'tools/mesh_demo_assets/app.js',
    'tools/mesh_demo_assets/index.html',
    'tools/mesh_demo_assets/style.css',
    'tools/test_mesh_demo_browser.py',
    'tools/package_release_pages.py',
    'tests/python/test_release_pages.py',
    'README.md',
    'docs/mesh-demos.md',
    'docs/release-demo.md',
    'docs/kandi-boom-integration.md',
    '.github/workflows/demo-release.yml',
    '.github/workflows/kandi-boom-validation.yml',
    'CMakeLists.txt',
    'bindings/csharp/DanceRudiments/DanceRudiments.csproj',
    'package.json',
    'package-lock.json',
    'pyproject.toml',
]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)


def require_repo() -> None:
    try:
        top = Path(run('git', 'rev-parse', '--show-toplevel').stdout.strip()).resolve()
    except Exception as exc:
        raise SystemExit(f'Not inside a git repository: {exc}')
    if top != ROOT or not (ROOT / 'tools/mesh_demo_assets/app.js').is_file():
        raise SystemExit('Run this script from the DanceRudiments repository root')
    dirty = []
    for name in TOUCHED:
        unstaged = run('git', 'diff', '--quiet', '--', name, check=False).returncode
        staged = run('git', 'diff', '--cached', '--quiet', '--', name, check=False).returncode
        if unstaged or staged:
            dirty.append(name)
    for name in ('tools/mesh_demo_assets/kandi-boom.js', 'tests/typescript/kandi-boom.test.js'):
        path = ROOT / name
        if path.exists() and run('git', 'ls-files', '--error-unmatch', name, check=False).returncode != 0:
            dirty.append(name)
    if dirty:
        raise SystemExit('Refusing to overwrite locally modified integration files:\n  ' + '\n  '.join(dirty))


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def write(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8', newline='\n')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one patch anchor, found {count}')
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str, flags: int = 0) -> str:
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one regex patch anchor, found {count}')
    return new


def patch_builder() -> None:
    path = 'tools/build_mesh_demo.mjs'
    text = read(path)
    text = replace_once(text,
        "const ASSETS = join(ROOT, 'tools/mesh_demo_assets');\n",
        "const ASSETS = join(ROOT, 'tools/mesh_demo_assets');\nconst KANDI = join(ROOT, 'harness/kandi-boom');\n",
        path + ' Kandi root')
    anchor = "  const sceneIds = new Set(), files = new Map([['catalogue.json', catalogueBytes]]), assetHashes = {};\n"
    addition = anchor + """  // Kandi Boom is the single production target character. The motion-scene IDs\n  // remain historical source-package keys and are not treated as character identities.\n  const targetRigBytes = await boundedFile(join(KANDI, 'source-rig.json'), 2 * 1024 * 1024);\n  const targetRig = JSON.parse(targetRigBytes.toString('utf8'));\n  const targetAudit = JSON.parse((await boundedFile(join(KANDI, 'rig-audit.json'), 2 * 1024 * 1024)).toString('utf8'));\n  if (targetRig.type_uri !== 'syn://type/danceflow/motion/rig/custom/kandi-boom' ||\n      targetRig.fingerprint_sha256 !== targetAudit.deep_validation?.source_rig_fingerprint_sha256 ||\n      targetRig.fbx_asset_sha256 !== targetAudit.assets?.['kandi-boom.fbx']?.sha256 ||\n      targetAudit.deep_validation?.skin?.unweighted_vertex_count !== 0)\n    throw Error('Kandi Boom target rig/audit identity changed');\n  const characterRoot = 'characters/kandi-boom';\n  const characterSources = {\n    fbx: ['kandi-boom.fbx', 'assets/kandi-boom.fbx'],\n    albedo: ['albedo.png', 'assets/albedo.png'],\n    normal: ['normal.png', 'assets/normal.png'],\n    roughness: ['roughness.png', 'assets/roughness.png'],\n    metallic: ['metallic.png', 'assets/metallic.png'],\n  };\n  const characterAssets = {};\n  for (const [key, [name, source]] of Object.entries(characterSources)) {\n    const audited = targetAudit.assets?.[name];\n    if (!audited || !hashPattern.test(audited.sha256) || !Number.isSafeInteger(audited.bytes))\n      throw Error(`Kandi Boom audit is missing ${name}`);\n    const bytes = await boundedFile(join(KANDI, source));\n    if (bytes.length !== audited.bytes || sha(bytes) !== audited.sha256) throw Error(`Kandi Boom asset drift: ${name}`);\n    const target = `${characterRoot}/${name}`;\n    files.set(target, bytes); assetHashes[target] = {sha256: audited.sha256, byte_length: bytes.length};\n    characterAssets[key] = {path: target, sha256: audited.sha256, byte_length: bytes.length};\n  }\n  const targetRigPath = `${characterRoot}/source-rig.json`;\n  files.set(targetRigPath, targetRigBytes);\n  assetHashes[targetRigPath] = {sha256: sha(targetRigBytes), byte_length: targetRigBytes.length};\n  characterAssets.rig = {path: targetRigPath, ...assetHashes[targetRigPath]};\n  const character = {id: 'kandi-boom', name: 'Kandi Boom', series: 'Bass Ben & Friends',\n    typeUri: targetRig.type_uri, rigFingerprint: targetRig.fingerprint_sha256,\n    fbxAssetSha256: targetRig.fbx_asset_sha256, assets: characterAssets,\n    sourceInfluenceStats: {\n      maxInfluencesPerVertex: targetAudit.deep_validation.skin.max_influences_per_vertex,\n      verticesWithOverFourInfluences: targetAudit.deep_validation.skin.vertices_with_over_four_influences,\n      maxDiscardedWeightAtFour: targetAudit.deep_validation.skin.max_discarded_weight_if_four_influences,\n      runtimeInfluenceLimit: 4,\n    }};\n"""
    text = replace_once(text, anchor, addition, path + ' character asset bundle')
    text = replace_once(text,
        "  const config = {scenes: catalogue.scenes, recordingWasm: {sha256: sha(wasm), byte_length: wasm.length}, build: buildInfo};\n",
        "  const config = {scenes: catalogue.scenes, character, recordingWasm: {sha256: sha(wasm), byte_length: wasm.length}, build: buildInfo};\n",
        path + ' config character')
    text = replace_once(text,
        "      originalCharacters: ['boxbot', 'prism'], eagerMotionLoads: 0};\n",
        "      targetCharacter: {id: character.id, name: character.name, series: character.series, typeUri: character.typeUri,\n        rigFingerprint: character.rigFingerprint, fbxAssetSha256: character.fbxAssetSha256,\n        runtimeInfluenceLimit: character.sourceInfluenceStats.runtimeInfluenceLimit},\n      sourceMotionSlots: ['boxbot', 'prism'], eagerMotionLoads: 0};\n",
        path + ' receipt character')
    write(path, text)


def patch_app() -> None:
    path = 'tools/mesh_demo_assets/app.js'
    text = read(path)
    text = replace_once(text,
        "import {createSkinnedCharacter} from './character.js';\n",
        "import {createKandiBoomCharacter} from './kandi-boom.js';\n",
        path + ' target import')
    text = replace_once(text,
        "const sceneName = scene => scene.id === 'boxbot' ? 'Boxbot' : 'Prism';\nconst copy = {\n  boxbot: {title: 'A salsa, with circuits.', description: 'An angular little robot with a surprisingly human sense of movement.', code: 'CMU 60_01', caption: '01 / BOXBOT'},\n  prism: {title: 'A study in turning.', description: 'A faceted dancer explores arabesques, turning jumps and deep back bends.', code: 'CMU 05_18', caption: '02 / PRISM'},\n};\n",
        "const sceneName = () => config.character.name;\nconst copy = {\n  boxbot: {title: 'Kandi Boom takes the salsa floor.', description: 'Kandi Boom retargets a complete captured salsa performance while keeping the original source timing.', code: 'CMU 60_01', caption: '01 / KANDI BOOM / SALSA'},\n  prism: {title: 'Kandi Boom turns through ballet.', description: 'Kandi Boom retargets a captured sequence of arabesques, turning jumps and deep back bends.', code: 'CMU 05_18', caption: '02 / KANDI BOOM / BALLET'},\n};\n",
        path + ' visible scene copy')
    text = replace_once(text,
        "  $('attribution').textContent = `${selected.attribution} BVH conversion: Bruce Hahne / cgspeed. Original character geometry: DanceRudiments.`;\n  $('load-scene').replaceChildren(document.createTextNode(`Load & play ${sceneName(selected)} `));\n  const arrow = document.createElement('span'); arrow.setAttribute('aria-hidden', 'true'); arrow.textContent = '↗'; $('load-scene').append(arrow);\n  $('load-size').textContent = `${(selected.compressedClipBytes / 1024 / 1024).toFixed(2)} MiB motion · loaded on request`;\n",
        "  $('attribution').textContent = `${config.character.name} · ${config.character.series}. ${selected.attribution} BVH conversion: Bruce Hahne / cgspeed.`;\n  $('load-scene').replaceChildren(document.createTextNode(`Load & play ${sceneName(selected)} `));\n  const arrow = document.createElement('span'); arrow.setAttribute('aria-hidden', 'true'); arrow.textContent = '↗'; $('load-scene').append(arrow);\n  const characterBytes = Object.values(config.character.assets).reduce((total, item) => total + item.byte_length, 0);\n  $('load-size').textContent = `${(selected.compressedClipBytes / 1024 / 1024).toFixed(2)} MiB motion · ${(characterBytes / 1024 / 1024).toFixed(1)} MiB Kandi target · loaded on request`;\n",
        path + ' attribution/load size')
    text = replace_once(text,
        "  $('resource-note').textContent = previous ? 'Character geometry, motion cache and native handles released.' : 'Motion data stays unloaded until you choose a performance.';\n  metadata(); updateTransport(); status(previous ? 'Character unloaded' : 'Ready when you are'); resetCamera();\n",
        "  $('resource-note').textContent = previous ? 'Kandi geometry, textures, motion cache and native handles released.' : 'Kandi and motion data stay unloaded until you choose a performance.';\n  metadata(); updateTransport(); status(previous ? 'Kandi Boom unloaded' : 'Ready when you are'); resetCamera();\n",
        path + ' unload copy')
    text = replace_once(text,
        "    const root = owner.character.bones[0].getWorldPosition(new THREE.Vector3());\n",
        "    const root = owner.character.rootBone.getWorldPosition(new THREE.Vector3());\n",
        path + ' camera root')
    old_load = """    const [runtime, wasm, rigBytes] = await Promise.all([\n      import('../../bindings/typescript/motion-packages.ts'),\n      verifiedAsset('recording.wasm', config.recordingWasm.sha256, config.recordingWasm.byte_length, signal),\n      verifiedAsset(owner.scene.rigPath, owner.scene.sceneRigSha256, 1024 * 1024, signal),\n    ]);\n    if (!current(owner)) return;\n    const rig = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(rigBytes));\n    const expected = owner.scene.expectedProfile;\n    if (rig.sceneId !== owner.scene.id || rig.quaternionOrder !== 'wxyz' ||\n        rig.expectedProfile?.type_uri !== expected.type_uri || rig.expectedProfile?.fingerprint !== expected.fingerprint ||\n        JSON.stringify(rig.expectedProfile?.dimensions) !== JSON.stringify(expected.dimensions)) throw Error('Saved scene rig identity mismatch');\n"""
    new_load = """    const target = config.character.assets;\n    const [runtime, wasm, rigBytes, targetRigBytes, fbx, albedo, normal, roughness, metallic] = await Promise.all([\n      import('../../bindings/typescript/motion-packages.ts'),\n      verifiedAsset('recording.wasm', config.recordingWasm.sha256, config.recordingWasm.byte_length, signal),\n      verifiedAsset(owner.scene.rigPath, owner.scene.sceneRigSha256, 1024 * 1024, signal),\n      verifiedAsset(target.rig.path, target.rig.sha256, target.rig.byte_length, signal),\n      verifiedAsset(target.fbx.path, target.fbx.sha256, target.fbx.byte_length, signal),\n      verifiedAsset(target.albedo.path, target.albedo.sha256, target.albedo.byte_length, signal),\n      verifiedAsset(target.normal.path, target.normal.sha256, target.normal.byte_length, signal),\n      verifiedAsset(target.roughness.path, target.roughness.sha256, target.roughness.byte_length, signal),\n      verifiedAsset(target.metallic.path, target.metallic.sha256, target.metallic.byte_length, signal),\n    ]);\n    if (!current(owner)) return;\n    const rig = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(rigBytes));\n    const targetRig = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(targetRigBytes));\n    const expected = owner.scene.expectedProfile;\n    if (rig.sceneId !== owner.scene.id || rig.quaternionOrder !== 'wxyz' ||\n        rig.expectedProfile?.type_uri !== expected.type_uri || rig.expectedProfile?.fingerprint !== expected.fingerprint ||\n        JSON.stringify(rig.expectedProfile?.dimensions) !== JSON.stringify(expected.dimensions)) throw Error('Saved source-motion rig identity mismatch');\n    if (targetRig.type_uri !== config.character.typeUri || targetRig.fingerprint_sha256 !== config.character.rigFingerprint ||\n        targetRig.fbx_asset_sha256 !== config.character.fbxAssetSha256) throw Error('Kandi Boom target-rig identity mismatch');\n"""
    text = replace_once(text, old_load, new_load, path + ' target asset loading')
    old_create = """    owner.character = createSkinnedCharacter(rig, owner.scene.characterKind, {onGeometryDisposed: () => stats.disposedGeometries++});\n    world.add(owner.character.group);\n    owner.transport = new PipTransport(owner.scene.startPip, owner.scene.endPip);\n    owner.transport.setSpeed(Number($('speed').value));\n    // Fix the presentation floor from an actual moving pose, rather than the\n    // converter's calibration T-pose. Keep vertical root motion thereafter.\n    await sampleAt(owner, Math.min(owner.scene.startPip + 64, owner.scene.endPip));\n    if (!current(owner)) return;\n    owner.character.frameOnFloor();\n    await sampleAt(owner, owner.scene.startPip);\n    if (!current(owner)) return;\n    owner.followPosition = owner.character.bones[0].getWorldPosition(new THREE.Vector3());\n    resetCamera(); owner.ready = true;\n    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) owner.transport.play();\n    $('loading-state').hidden = true; $('mesh-label').textContent = `${owner.character.stats.vertexCount.toLocaleString()} vertices`;\n    $('resource-note').textContent = 'One selected motion chunk in memory. Switching characters unloads its geometry and recording.';\n"""
    new_create = """    owner.character = await createKandiBoomCharacter(rig, targetRig, {fbx, albedo, normal, roughness, metallic},\n      {onGeometryDisposed: () => stats.disposedGeometries++});\n    if (!current(owner)) { owner.character.dispose(); return; }\n    world.add(owner.character.group);\n    owner.transport = new PipTransport(owner.scene.startPip, owner.scene.endPip);\n    owner.transport.setSpeed(Number($('speed').value));\n    // Establish source root-motion zero at the retained calibration frame, then\n    // frame the real Kandi skin using a moving pose before returning to start.\n    await sampleAt(owner, owner.scene.startPip);\n    if (!current(owner)) return;\n    await sampleAt(owner, Math.min(owner.scene.startPip + 64, owner.scene.endPip));\n    if (!current(owner)) return;\n    owner.character.frameOnFloor();\n    await sampleAt(owner, owner.scene.startPip);\n    if (!current(owner)) return;\n    owner.followPosition = owner.character.rootBone.getWorldPosition(new THREE.Vector3());\n    resetCamera(); owner.ready = true;\n    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) owner.transport.play();\n    $('loading-state').hidden = true; $('mesh-label').textContent = `${owner.character.stats.vertexCount.toLocaleString()} Kandi vertices`;\n    $('resource-note').textContent = 'One selected motion chunk in memory. Switching performances unloads Kandi and the previous recording.';\n"""
    text = replace_once(text, old_create, new_create, path + ' target creation')
    old_debug = """  debugSnapshot() {\n    const owner = session, character = owner?.character;\n    const presentationInverse = character ? character.group.matrixWorld.clone().invert() : null;\n    return {\n"""
    new_debug = """  debugSnapshot() {\n    const owner = session, character = owner?.character;\n    return {\n"""
    text = replace_once(text, old_debug, new_debug, path + ' debug header')
    text = replace_once(text,
        "      jointNames: character?.bones.map(bone => bone.name) ?? [],\n      jointWorldMatrices: character?.bones.map(bone => new THREE.Matrix4().multiplyMatrices(presentationInverse, bone.matrixWorld).transpose().toArray()) ?? [],\n      rigTransforms: character?.bones.map(bone => ({name: bone.name, position: bone.position.toArray(), quaternion: bone.quaternion.toArray(), matrixWorld: bone.matrixWorld.toArray()})) ?? [],\n",
        "      jointNames: character?.sourceJointNames ?? [],\n      jointWorldMatrices: character?.sourceJointWorldMatrices() ?? [],\n      rigTransforms: character?.targetBones.map(bone => ({name: bone.name, position: bone.position.toArray(), quaternion: bone.quaternion.toArray(), matrixWorld: bone.matrixWorld.toArray()})) ?? [],\n      characterName: character ? config.character.name : null, targetRigFingerprint: character ? config.character.rigFingerprint : null,\n      runtimeInfluenceLimit: character?.stats.runtimeInfluenceLimit ?? null,\n",
        path + ' debug source/target split')
    if 'createSkinnedCharacter' in text:
        raise SystemExit(path + ': procedural production character import survived patch')
    write(path, text)


def patch_html() -> None:
    path = 'tools/mesh_demo_assets/index.html'
    text = read(path)
    replacements = [
        ('Two original low-poly skinned characters perform real captured dances, played by DanceRudiments native motion recordings.',
         'Kandi Boom performs two real captured dances through DanceRudiments native motion recordings and explicit rig retargeting.'),
        ('CAPTURED MOVEMENT. NEW CHARACTERS.', 'CAPTURED MOVEMENT. KANDI BOOM.'),
        ('A little character.<br>A lot of <em>motion.</em>', 'One real character.<br>Two captured <em>performances.</em>'),
        ('Meet two original low-poly dancers, brought to life by real motion capture. Choose a character, load a performance, and explore every step.',
         'Meet Kandi Boom from Bass Ben &amp; Friends, driven by two real motion-capture performances. Choose a performance and explore every step.'),
        ('Load &amp; play Boxbot', 'Load &amp; play Kandi Boom'),
        ('01 / BOXBOT', '01 / KANDI BOOM / SALSA'),
        ('CHOOSE YOUR CHARACTER', 'CHOOSE A PERFORMANCE'),
        ('<span class="character-icon robot-icon" aria-hidden="true"><svg viewBox="0 0 80 80"><path d="M39 12V6" stroke="#254f51" stroke-width="3"/><rect x="21" y="13" width="37" height="29" rx="4" fill="#e8bc4e"/><rect x="26" y="23" width="27" height="10" rx="2" fill="#254f51"/><path d="M32 27v3m15-3v3" stroke="#bcffee" stroke-width="3"/><rect x="20" y="46" width="40" height="26" rx="4" fill="#254f51"/><rect x="28" y="51" width="24" height="7" rx="2" fill="#e8bc4e"/><path d="M13 49v18m54-18v18" stroke="#e8bc4e" stroke-width="8" stroke-linecap="square"/></svg></span><span class="scene-card-text"><strong>Boxbot</strong><span>Salsa / CMU 60_01</span></span>',
         '<span class="character-icon kandi-icon" aria-hidden="true"><strong>KB</strong></span><span class="scene-card-text"><strong>Kandi Boom</strong><span>Salsa / CMU 60_01</span></span>'),
        ('<span class="character-icon prism-icon" aria-hidden="true"><svg viewBox="0 0 80 80"><path d="m40 6 7 11-7 9-8-9z" fill="#d96c58"/><path d="m40 18 17 12-6 22H30l-7-22z" fill="#f1b594"/><path d="m40 18 1 34H30l-7-22z" fill="#dc7c67"/><path d="m29 32 22-1-4 7H32z" fill="#382d49"/><path d="m30 52-12 15 22 10 24-10-13-15z" fill="#d96c58"/><path d="m40 55 8 9-8 8-8-8z" fill="#f8d8b4"/></svg></span><span class="scene-card-text"><strong>Prism</strong><span>Ballet / CMU 05_18</span></span>',
         '<span class="character-icon kandi-icon" aria-hidden="true"><strong>KB</strong></span><span class="scene-card-text"><strong>Kandi Boom</strong><span>Ballet / CMU 05_18</span></span>'),
        ('<option value="boxbot">Boxbot · salsa</option><option value="prism">Prism · ballet</option>',
         '<option value="boxbot">Kandi Boom · salsa</option><option value="prism">Kandi Boom · ballet</option>'),
        ('A salsa, with circuits.', 'Kandi Boom takes the salsa floor.'),
        ('An angular little robot with a surprisingly human sense of movement.', 'The real Kandi Boom FBX retargets the complete captured salsa performance.'),
        ('Small meshes. Full performances.', 'Kandi Boom. Full performances.'),
        ('Original geometry is skinned to each capture’s exact source rig. The numbered channels come from DanceRudiments recordings.',
         'Kandi Boom’s real FBX is retargeted from each capture’s exact source rig. The numbered channels still come from DanceRudiments recordings.'),
        ('Motion data: Carnegie Mellon University · NSF EIA-0196217. BVH conversion: Bruce Hahne / cgspeed.',
         'Kandi Boom · Bass Ben &amp; Friends. Motion data: Carnegie Mellon University · NSF EIA-0196217. BVH conversion: Bruce Hahne / cgspeed.'),
    ]
    for old, new in replacements:
        text = replace_once(text, old, new, path + ' visible copy')
    if '>Boxbot<' in text or '>Prism<' in text:
        raise SystemExit(path + ': visible procedural character names survived patch')
    write(path, text)


def patch_css() -> None:
    path = 'tools/mesh_demo_assets/style.css'
    text = read(path)
    anchor = '.prism-icon{background:#f1e2d9}'
    replacement = anchor + '.kandi-icon{display:grid;place-items:center;background:#eadcf0;color:#6d4878;font-size:15px;letter-spacing:-.5px}.kandi-icon strong{font-weight:800}'
    text = replace_once(text, anchor, replacement, path + ' Kandi card style')
    write(path, text)


def patch_browser_test() -> None:
    path = 'tools/test_mesh_demo_browser.py'
    text = read(path)
    anchor = "        raise ValueError('Expected the built two-scene mesh gallery')\n"
    addition = anchor + "    target = build.get('targetCharacter', {})\n    if (target.get('id') != 'kandi-boom' or target.get('name') != 'Kandi Boom'\n            or target.get('runtimeInfluenceLimit') != 4 or not re.fullmatch(r'[0-9a-f]{64}', target.get('rigFingerprint', ''))):\n        raise ValueError('Expected the hash-pinned Kandi Boom production target')\n    gallery_html = (mesh / 'index.html').read_text(encoding='utf-8')\n    if 'Kandi Boom' not in gallery_html or '>Boxbot<' in gallery_html or '>Prism<' in gallery_html:\n        raise ValueError('Gallery still exposes a procedural fixture as a character')\n"
    text = replace_once(text, anchor, addition, path + ' target receipt')
    text = replace_once(text, "                  scenes=scenes, checks=checks, screenshots=[],\n                  source_timing='time-only; musical BPM and phase unverified',\n                  rendering='Chromium WebGL 2; ANGLE SwiftShader software renderer')\n", "                  scenes=scenes, checks=checks, screenshots=[],\n                  target_character=dict(id=target['id'], name=target['name'],\n                      rig_fingerprint=target['rigFingerprint'], fbx_asset_sha256=target['fbxAssetSha256'],\n                      runtime_influence_limit=target['runtimeInfluenceLimit']),\n                  source_timing='time-only; musical BPM and phase unverified',\n                  rendering='Chromium WebGL 2; ANGLE SwiftShader software renderer')\n", path + ' target browser report')
    text = replace_once(text,
        "            check(not any('/motions/' in value or value.endswith('.wasm') for value in requests),\n                  'Initial navigation fetches no rig, profile, recording or WASM payload')\n",
        "            check(not any('/motions/' in value or '/characters/' in value or value.endswith('.wasm') for value in requests),\n                  'Initial navigation fetches no Kandi target, rig, profile, recording or WASM payload')\n",
        path + ' lazy target')
    anchor2 = "                check(state['skinnedMeshCount'] >= 1 and state['vertexCount'] > 0\n                      and state['weightedVertexCount'] == state['vertexCount'] and state['blendedVertexCount'] > 0,\n                      f'{sid}: actual skinned geometry contains vertices with multiple bone weights')\n"
    addition2 = anchor2 + "                check(state['characterName'] == 'Kandi Boom' and state['targetRigFingerprint'] == target['rigFingerprint']\n                      and state['runtimeInfluenceLimit'] == 4,\n                      f'{sid}: the rendered target is the verified Kandi Boom rig')\n                check(any('/characters/kandi-boom/kandi-boom.fbx' in value for value in requests[request_start:]),\n                      f'{sid}: explicit load fetches the canonical Kandi Boom FBX')\n"
    text = replace_once(text, anchor2, addition2, path + ' target browser identity')
    text = text.replace('Switching characters disposes the previous native handle and skin geometry',
                        'Switching performances disposes the previous native handle and Kandi skin geometry')
    write(path, text)



def patch_release_pages() -> None:
    path = 'tools/package_release_pages.py'
    text = read(path)
    old = """    if (build.get('format') != 'dancerudiments.mesh-demo-build' or build.get('schema_version') != 1
            or build.get('version') != version or build.get('commit') != commit
            or build.get('sceneIds') != ['boxbot', 'prism']
            or catalogue.get('format') != 'dancerudiments.mesh-demo-catalogue'
            or catalogue.get('schema_version') != 1 or not isinstance(catalogue_scenes, list)
            or len(catalogue_scenes) != 2
            or {item.get('id') for item in catalogue_scenes if isinstance(item, dict)} != SCENE_IDS):
        raise ValueError('Expected both named mesh scenes built for this exact release')
"""
    new = """    target = build.get('targetCharacter', {})
    if (build.get('format') != 'dancerudiments.mesh-demo-build' or build.get('schema_version') != 1
            or build.get('version') != version or build.get('commit') != commit
            or build.get('sceneIds') != ['boxbot', 'prism']
            or build.get('sourceMotionSlots') != ['boxbot', 'prism']
            or target.get('id') != 'kandi-boom' or target.get('name') != 'Kandi Boom'
            or target.get('runtimeInfluenceLimit') != 4
            or not re.fullmatch(r'[0-9a-f]{64}', target.get('rigFingerprint', ''))
            or not re.fullmatch(r'[0-9a-f]{64}', target.get('fbxAssetSha256', ''))
            or catalogue.get('format') != 'dancerudiments.mesh-demo-catalogue'
            or catalogue.get('schema_version') != 1 or not isinstance(catalogue_scenes, list)
            or len(catalogue_scenes) != 2
            or {item.get('id') for item in catalogue_scenes if isinstance(item, dict)} != SCENE_IDS):
        raise ValueError('Expected both source-motion slots targeting Kandi Boom for this exact release')
"""
    text = replace_once(text, old, new, path + ' Kandi release identity')
    anchor = """    if (qa.get('format') != QA_FORMAT or qa.get('schema_version') != 1
            or qa.get('status') != 'PASS' or qa.get('scope') != 'complete-site'
            or qa.get('version') != version or qa.get('source_commit') != commit):
        raise ValueError('A passing mesh browser report for this exact release is required')
"""
    addition = anchor + """    expected_target = dict(id=target['id'], name=target['name'], rig_fingerprint=target['rigFingerprint'],
                           fbx_asset_sha256=target['fbxAssetSha256'], runtime_influence_limit=target['runtimeInfluenceLimit'])
    if qa.get('target_character') != expected_target:
        raise ValueError('Browser verification target differs from the sealed Kandi Boom build identity')
"""
    text = replace_once(text, anchor, addition, path + ' browser target identity')
    text = text.replace('Browser verification must cover the distinct boxbot and prism mesh scenes',
                        'Browser verification must cover the distinct boxbot and prism source-motion slots')
    write(path, text)


def patch_release_pages_tests() -> None:
    path = 'tests/python/test_release_pages.py'
    text = read(path)
    text = replace_once(text,
        """        (mesh / 'build.json').write_text(json.dumps(dict(format='dancerudiments.mesh-demo-build',
            schema_version=1, version=VERSION, commit=COMMIT, sceneIds=['boxbot', 'prism'])))
""",
        """        (mesh / 'build.json').write_text(json.dumps(dict(format='dancerudiments.mesh-demo-build',
            schema_version=1, version=VERSION, commit=COMMIT, sceneIds=['boxbot', 'prism'],
            sourceMotionSlots=['boxbot', 'prism'], targetCharacter=dict(id='kandi-boom', name='Kandi Boom',
                rigFingerprint='1'*64, fbxAssetSha256='2'*64, runtimeInfluenceLimit=4))))
""",
        path + ' build fixture target')
    text = replace_once(text,
        """            status='PASS', scope='complete-site', version=VERSION, source_commit=COMMIT,
            scenes=[dict(id='boxbot'), dict(id='prism')], tested_assets=[
""",
        """            status='PASS', scope='complete-site', version=VERSION, source_commit=COMMIT,
            target_character=dict(id='kandi-boom', name='Kandi Boom', rig_fingerprint='1'*64,
                                  fbx_asset_sha256='2'*64, runtime_influence_limit=4),
            scenes=[dict(id='boxbot'), dict(id='prism')], tested_assets=[
""",
        path + ' report fixture target')
    marker = """    def test_both_actual_scene_ids_must_be_distinct_and_verified(self):
"""
    target_test = """    def test_browser_target_must_match_the_sealed_kandi_identity(self):
        report = json.loads(self.report.read_text())
        report['target_character']['rig_fingerprint'] = '3' * 64
        self.report.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'target differs'):
            self.seal()
        self.assertFalse(self.output.exists())

"""
    text = replace_once(text, marker, target_test + marker, path + ' target mismatch regression')
    write(path, text)

def patch_readme() -> None:
    path = 'README.md'
    text = read(path)
    pattern = r"## 3D dance examples\n.*?\n\nDanceRudiments is a C\+\+17 library"
    section = """## 3D dance examples\n\nThe release build includes a separate **`meshes/` gallery** beside the pattern\nvisualizer. The production character is **Kandi Boom** from *Bass Ben & Friends*,\nusing the real checked-in FBX, 24-bone rig and PBR textures. Two pinned optional\nsource-motion packages can drive her through an explicit source-rig → Kandi\nretarget adapter:\n\n| Character | Movement | Source recording |\n| --- | --- | --- |\n| Kandi Boom | Salsa | CMU 60_01, with the reviewed 60 fps source timing restored |\n| Kandi Boom | Ballet sequence: attitude, arabesque, turning jump and back bend | CMU 05_18 |\n\nThe source recordings preserve their own skeleton profiles, original timing and\ncalibration frames. They have no verified musical beat/downbeat annotations and\nare not presented as beat-matched to a song. Loading a performance fetches only\nits optional motion package plus the hash-pinned Kandi target assets; switching\nperformances unloads the previous recording and target scene. Play, pause, seek,\nrestart and preview speed continue to use the existing native C++/WASM sampler.\n\nKandi's canonical FBX contains vertices with more than four source influences.\nThe source remains untouched and fully audited; the WebGL renderer uses an\nexplicit, normalised four-weight runtime approximation and records that limit in\nthe build/browser evidence. The target is a custom Kandi rig, not a Rigify rig.\n\nThe release workflow browser-tests both performances on the real Kandi mesh,\nattaches gallery/complete-site archives and deploys the existing visualizer and\ngallery together when Pages is enabled. See [building and validating the Kandi\nBoom motion demo](docs/mesh-demos.md) and the [release workflow guide](docs/release-demo.md).\n\nDanceRudiments is a C++17 library"""
    text = regex_once(text, pattern, section, path + ' 3D section', flags=re.S)
    write(path, text)



def patch_release_docs() -> None:
    path = 'docs/release-demo.md'
    text = read(path)
    text = replace_once(text,
        """The root remains the existing native pattern visualizer. A link in its header
opens `meshes/`, where two original low-poly skinned characters perform different
recorded dances. The standalone HTML download remains self-contained; the mesh
gallery is a separate HTTP-served bundle with locally bundled JavaScript, WASM,
rig profiles and selectively loaded motion files.
""",
        """The root remains the existing native pattern visualizer. A link in its header
opens `meshes/`, where **Kandi Boom** from *Bass Ben & Friends* performs either
of two pinned source-motion recordings. The standalone HTML download remains
self-contained; the gallery is a separate HTTP-served bundle with locally
bundled JavaScript, WASM, the hash-pinned Kandi FBX/PBR target, source rig
profiles and selectively loaded motion files.
""",
        path + ' website description')
    text = replace_once(text,
        """The mesh stage then builds only the two pinned dance sources selected in
`tools/mesh_demo_sources.json`. This is an explicit workflow download, bounded
to those two hashed files. It uses the optional package loader and the existing
native recording WASM sampler. Browser QA checks:

- Both weighted triangle skins and their changing deformed vertices.
""",
        """The mesh stage then builds only the two pinned dance sources selected in
`tools/mesh_demo_sources.json`. This is an explicit workflow download, bounded
to those two hashed files. It independently verifies Kandi Boom's canonical FBX,
target-rig fingerprint and PBR maps, then uses the optional package loader and
the existing native recording WASM sampler. The legacy `boxbot` and `prism`
scene IDs are source-package slot identities only; both render the same verified
Kandi target. Browser QA checks:

- Kandi Boom's real weighted triangle skin and changing deformed vertices under both source performances.
""",
        path + ' build gates target')
    text = replace_once(text,
        """and commit, `scope: complete-site`, and successful coverage of both `boxbot`
and `prism`. Changed, missing, unchecked or symlinked assets fail sealing. A
local `--gallery-only` receipt cannot seal a release site.
""",
        """and commit, `scope: complete-site`, the exact Kandi target fingerprint/FBX
hash, and successful coverage of both internal source-motion slots (`boxbot` and
`prism`). Changed, missing, unchecked or symlinked assets fail sealing. A local
`--gallery-only` receipt cannot seal a release site.
""",
        path + ' seal identity')
    write(path, text)

def patch_workflow() -> None:
    path = '.github/workflows/demo-release.yml'
    text = read(path)
    text = replace_once(text,
        '      - name: Build two pinned, independently loaded mesh dances\n',
        '      - name: Build two pinned motions for the Kandi Boom gallery\n',
        path + ' step title')
    write(path, text)



def patch_kandi_workflow() -> None:
    path = '.github/workflows/kandi-boom-validation.yml'
    text = read(path)
    marker = "      - 'tests/python/test_kandi_boom_*'\n"
    additions = marker + "      - 'tools/build_mesh_demo.mjs'\n      - 'tools/mesh_demo_assets/**'\n      - 'tools/test_mesh_demo_browser.py'\n      - 'tests/typescript/kandi-boom.test.js'\n"
    if text.count(marker) != 2:
        raise SystemExit(path + ': expected the Kandi Python-test path in push and PR filters')
    text = text.replace(marker, additions)
    anchor = "      - name: Install browser test dependency\n"
    step = "      - name: Verify production Kandi gallery wiring\n        run: |\n          node --check tools/mesh_demo_assets/kandi-boom.js\n          node --check tools/mesh_demo_assets/app.js\n          node --check tools/build_mesh_demo.mjs\n          node --test tests/typescript/kandi-boom.test.js\n"
    text = replace_once(text, anchor, step + anchor, path + ' production wiring check')
    write(path, text)

def bump_versions() -> None:
    specs = {
        'CMakeLists.txt': [('project(DanceRudiments VERSION 0.4.3', 'project(DanceRudiments VERSION 0.4.4')],
        'bindings/csharp/DanceRudiments/DanceRudiments.csproj': [('<Version>0.4.3</Version>', '<Version>0.4.4</Version>')],
        'package.json': [('"version": "0.4.3"', '"version": "0.4.4"')],
        'pyproject.toml': [('version = "0.4.3"', 'version = "0.4.4"')],
    }
    for path, replacements in specs.items():
        text = read(path)
        for old, new in replacements:
            text = replace_once(text, old, new, path + ' version')
        write(path, text)
    path = 'package-lock.json'
    text = read(path)
    if text.count('"version": "0.4.3"') != 2:
        raise SystemExit(path + ': expected two root package version fields at 0.4.3')
    text = text.replace('"version": "0.4.3"', '"version": "0.4.4"', 2)
    write(path, text)


def copy_payload() -> None:
    for relative in [
        'tools/mesh_demo_assets/kandi-boom.js',
        'docs/mesh-demos.md',
    'docs/release-demo.md',
        'docs/kandi-boom-integration.md',
        'tests/typescript/kandi-boom.test.js',
    ]:
        source = PAYLOAD / relative
        if not source.is_file():
            raise SystemExit(f'Bundle payload missing: {relative}')
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def smoke_checks() -> None:
    for path in ('tools/mesh_demo_assets/kandi-boom.js', 'tools/mesh_demo_assets/app.js', 'tools/build_mesh_demo.mjs'):
        result = run('node', '--check', path, check=False)
        if result.returncode:
            raise SystemExit(f'JavaScript parse check failed for {path}:\n{result.stderr}')
    result = run(sys.executable, '-m', 'py_compile', 'tools/test_mesh_demo_browser.py', check=False)
    if result.returncode:
        raise SystemExit('Python parse check failed for tools/test_mesh_demo_browser.py:\n' + result.stderr)
    package = json.loads(read('package.json'))
    lock = json.loads(read('package-lock.json'))
    if package['version'] != '0.4.4' or lock['version'] != '0.4.4' or lock['packages']['']['version'] != '0.4.4':
        raise SystemExit('Version files did not converge on 0.4.4')
    app, html, builder = read('tools/mesh_demo_assets/app.js'), read('tools/mesh_demo_assets/index.html'), read('tools/build_mesh_demo.mjs')
    if 'createKandiBoomCharacter' not in app or 'createSkinnedCharacter' in app:
        raise SystemExit('Production app is not wired exclusively to Kandi Boom')
    if '>Boxbot<' in html or '>Prism<' in html or 'targetCharacter' not in builder:
        raise SystemExit('Production gallery still exposes the procedural fixture path')


def main() -> None:
    require_repo()
    all_paths = set(TOUCHED) | {'tools/mesh_demo_assets/kandi-boom.js', 'tests/typescript/kandi-boom.test.js'}
    backup = {name: (ROOT / name).read_bytes() if (ROOT / name).exists() else None for name in all_paths}
    try:
        # Copy replacement docs/new modules only after every touched tracked file
        # has been confirmed clean. Pattern-strict edits make the operation fail-fast.
        copy_payload()
        patch_builder()
        patch_app()
        patch_html()
        patch_css()
        patch_browser_test()
        patch_release_pages()
        patch_release_pages_tests()
        patch_readme()
        patch_release_docs()
        patch_workflow()
        patch_kandi_workflow()
        bump_versions()
        smoke_checks()
    except BaseException:
        for name, data in backup.items():
            target = ROOT / name
            if data is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        raise
    print('Kandi Boom final integration applied successfully.')
    print('Next: npm ci && npm test, then run the Python/release tests described in docs/mesh-demos.md.')
    print('Review with: git diff --check && git diff --stat && git status --short')


if __name__ == '__main__':
    main()
