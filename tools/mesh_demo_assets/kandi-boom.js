import * as THREE from 'three';
import {FBXLoader} from 'three/addons/loaders/FBXLoader.js';

const SOURCE_TO_TARGET = new THREE.Quaternion().setFromAxisAngle(
  new THREE.Vector3(1, 0, 0), -Math.PI / 2,
);
const SOURCE_TO_TARGET_INV = SOURCE_TO_TARGET.clone().invert();

// CMU source skeleton -> Kandi Boom target skeleton. World-space deltas are
// retargeted, so omitted convenience joints (Neck1, L/RHipJoint, fingers) are
// naturally folded into mapped descendants instead of guessed as local axes.
export const KANDI_RETARGET_MAP = Object.freeze({
  Hips: 'Hips',
  LeftUpLeg: 'LeftUpLeg', LeftLeg: 'LeftLeg', LeftFoot: 'LeftFoot', LeftToeBase: 'LeftToeBase',
  RightUpLeg: 'RightUpLeg', RightLeg: 'RightLeg', RightFoot: 'RightFoot', RightToeBase: 'RightToeBase',
  Spine02: 'LowerBack', Spine01: 'Spine', Spine: 'Spine1', neck: 'Neck', Head: 'Head',
  LeftShoulder: 'LeftShoulder', LeftArm: 'LeftArm', LeftForeArm: 'LeftForeArm', LeftHand: 'LeftHand',
  RightShoulder: 'RightShoulder', RightArm: 'RightArm', RightForeArm: 'RightForeArm', RightHand: 'RightHand',
});

function arrayBuffer(bytes) {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

export function copyFbxTextureTransform(source, target) {
  if (!source?.isTexture || !target?.isTexture) throw Error('FBX texture transform requires two Three.js textures');
  // FBXLoader uses the normal Three.js image convention (flipY=true unless
  // the FBX says otherwise) and then applies FBX wrap/scale/translation.
  // Preserve those coordinates when swapping in the audited external PBR maps.
  target.flipY = source.flipY;
  target.mapping = source.mapping;
  target.channel = source.channel;
  target.wrapS = source.wrapS; target.wrapT = source.wrapT;
  target.magFilter = source.magFilter; target.minFilter = source.minFilter;
  target.anisotropy = source.anisotropy;
  target.generateMipmaps = source.generateMipmaps;
  target.premultiplyAlpha = source.premultiplyAlpha;
  target.unpackAlignment = source.unpackAlignment;
  target.offset.copy(source.offset); target.repeat.copy(source.repeat); target.center.copy(source.center);
  target.rotation = source.rotation; target.matrixAutoUpdate = source.matrixAutoUpdate;
  if (source.matrixAutoUpdate) target.updateMatrix(); else target.matrix.copy(source.matrix);
  // Deliberately do not copy colorSpace: albedo is sRGB; normal/roughness/
  // metalness remain data textures.
  target.needsUpdate = true;
  return target;
}

function textureTransformMatches(a, b) {
  return a.flipY === b.flipY && a.mapping === b.mapping && a.channel === b.channel &&
    a.wrapS === b.wrapS && a.wrapT === b.wrapT &&
    a.offset.equals(b.offset) && a.repeat.equals(b.repeat) && a.center.equals(b.center) &&
    a.rotation === b.rotation && a.matrixAutoUpdate === b.matrixAutoUpdate;
}

export function calibrationRelativeQuaternion(current, calibrationInverse, target = new THREE.Quaternion()) {
  return target.copy(current).multiply(calibrationInverse).normalize();
}

async function textureFromBytes(bytes, {srgb = false} = {}) {
  const url = URL.createObjectURL(new Blob([bytes], {type: 'image/png'}));
  try {
    const texture = await new THREE.TextureLoader().loadAsync(url);
    if (srgb) texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    return texture;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function sourcePoseEvaluator(rig) {
  if (!Array.isArray(rig.joints) || !rig.joints.length || !Array.isArray(rig.channels))
    throw Error('Source motion rig is incomplete');
  const matrices = rig.joints.map(() => new THREE.Matrix4());
  const local = new THREE.Matrix4(), position = new THREE.Vector3(), quaternion = new THREE.Quaternion(), scale = new THREE.Vector3();
  const evaluator = {
    names: rig.joints.map(joint => joint.name),
    lastMatrices: null,
    evaluate(values) {
      if (!Array.isArray(values) && !(values instanceof Float32Array) && !(values instanceof Float64Array))
        throw Error('Source pose values are unavailable');
      for (let i = 0; i < rig.joints.length; i++) {
        const joint = rig.joints[i];
        position.fromArray(joint.offset); quaternion.identity(); scale.set(1, 1, 1);
        if (joint.positionChannelIndices) for (let axis = 0; axis < 3; axis++)
          position.setComponent(axis, joint.offset[axis] + values[joint.positionChannelIndices[axis]]);
        if (joint.rotationChannelIndices) {
          const [w, x, y, z] = joint.rotationChannelIndices.map(index => values[index]);
          if (Math.abs(Math.hypot(w, x, y, z) - 1) > .0002) throw Error(`Source quaternion is not unit length: ${joint.name}`);
          quaternion.set(x, y, z, w).normalize();
        }
        if (joint.scaleChannelIndices) scale.fromArray(joint.scaleChannelIndices.map(index => values[index]));
        local.compose(position, quaternion, scale);
        matrices[i].copy(local);
        if (joint.parentIndex >= 0) matrices[i].premultiply(matrices[joint.parentIndex]);
      }
      evaluator.lastMatrices = matrices;
      return matrices;
    },
  };
  return evaluator;
}

function profileMatches(rig, profile) {
  return profile?.channels?.length === rig.channels.length && !profile.channels.some((channel, i) => {
    const expected = rig.channels[i];
    return channel.number !== i + 1 || ['name', 'bone', 'data_path', 'array_index', 'minimum', 'maximum', 'neutral']
      .some(key => channel[key] !== expected[key]);
  });
}

function validateTargetRig(targetRig, root) {
  if (targetRig?.type_uri !== 'syn://type/danceflow/motion/rig/custom/kandi-boom'
      || !/^[0-9a-f]{64}$/.test(targetRig?.fingerprint_sha256 || '') || !Array.isArray(targetRig?.bones))
    throw Error('Kandi Boom target-rig identity is invalid');
  const bones = new Map();
  root.traverse(object => { if (object.isBone) bones.set(object.name, object); });
  for (const record of targetRig.bones) {
    const bone = bones.get(record.name);
    if (!bone) throw Error(`Kandi Boom FBX is missing target bone ${record.name}`);
    const parentName = bone.parent?.isBone ? bone.parent.name : 'Armature';
    if (record.parent_name !== parentName && !(record.name === 'Hips' && record.parent_name === 'Armature'))
      throw Error(`Kandi Boom bone parent changed: ${record.name}`);
  }
  for (const target of Object.keys(KANDI_RETARGET_MAP)) if (!bones.has(target))
    throw Error(`Retarget target bone is absent: ${target}`);
  return bones;
}

function skinStats(meshes) {
  let vertexCount = 0, weightedVertexCount = 0, blendedVertexCount = 0;
  for (const mesh of meshes) {
    const position = mesh.geometry.getAttribute('position'), weight = mesh.geometry.getAttribute('skinWeight');
    vertexCount += position?.count ?? 0;
    if (!position || !weight || position.count !== weight.count) continue;
    for (let i = 0; i < weight.count; i++) {
      const values = [weight.getX(i), weight.getY(i), weight.getZ(i), weight.getW(i)];
      const positives = values.filter(v => v > 1e-7).length;
      if (values.reduce((a, b) => a + b, 0) > 1e-7) weightedVertexCount++;
      if (positives > 1) blendedVertexCount++;
    }
  }
  return {vertexCount, weightedVertexCount, blendedVertexCount};
}

function disposeMaterial(material) {
  if (!material) return;
  material.dispose();
}

export async function createKandiBoomCharacter(sourceRig, targetRig, assets,
  {onGeometryDisposed = () => {}} = {}) {
  if (!assets?.fbx || !assets?.albedo || !assets?.normal || !assets?.roughness || !assets?.metallic)
    throw Error('Kandi Boom FBX and four PBR maps are required');
  const [albedo, normalMap, roughnessMap, metalnessMap] = await Promise.all([
    textureFromBytes(assets.albedo, {srgb: true}), textureFromBytes(assets.normal),
    textureFromBytes(assets.roughness), textureFromBytes(assets.metallic),
  ]);
  const textures = [albedo, normalMap, roughnessMap, metalnessMap];
  let root;
  try {
    root = new FBXLoader().parse(arrayBuffer(assets.fbx), '');
  } catch (error) {
    textures.forEach(texture => texture.dispose());
    throw Error(`Kandi Boom FBX could not be parsed: ${error.message}`);
  }
  root.name = 'kandi-boom-fbx';
  root.updateMatrixWorld(true);
  const targetBones = validateTargetRig(targetRig, root);
  const targetBoneList = targetRig.bones.map(record => targetBones.get(record.name));
  const meshes = [], sourceMaps = [];
  // Read the FBX material's own texture coordinate contract before replacing
  // its embedded colour map with the separately hash-pinned PBR maps.
  root.traverse(object => {
    if (!(object.isMesh || object.isSkinnedMesh)) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) if (material?.map?.isTexture) sourceMaps.push(material.map);
  });
  if (!sourceMaps.length) {
    textures.forEach(texture => texture.dispose());
    throw Error('Kandi Boom FBX has no diffuse texture transform to bind the external PBR maps');
  }
  const sourceMap = sourceMaps[0];
  if (sourceMaps.some(texture => !textureTransformMatches(sourceMap, texture))) {
    textures.forEach(texture => texture.dispose());
    throw Error('Kandi Boom FBX uses incompatible diffuse texture transforms');
  }
  textures.forEach(texture => copyFbxTextureTransform(sourceMap, texture));
  const textureTransformMatched = textures.every(texture => textureTransformMatches(sourceMap, texture));
  if (!textureTransformMatched) throw Error('Kandi Boom PBR texture transforms do not match the FBX UV contract');

  root.traverse(object => {
    if (!(object.isMesh || object.isSkinnedMesh)) return;
    if (object.isSkinnedMesh) meshes.push(object);
    object.frustumCulled = false; object.castShadow = true; object.receiveShadow = true;
    const old = Array.isArray(object.material) ? object.material : [object.material];
    const replacement = old.map(material => new THREE.MeshStandardMaterial({
      name: `${material?.name || 'kandi'}-pbr`, map: albedo, normalMap, roughnessMap, metalnessMap,
      roughness: 1, metalness: 1, transparent: Boolean(material?.transparent), opacity: material?.opacity ?? 1,
      side: material?.side ?? THREE.FrontSide, alphaTest: material?.alphaTest ?? 0,
    }));
    old.forEach(disposeMaterial);
    object.material = Array.isArray(object.material) ? replacement : replacement[0];
  });
  if (!meshes.length) {
    textures.forEach(texture => texture.dispose());
    throw Error('Kandi Boom FBX contains no skinned mesh');
  }

  // Three/WebGL's standard skinning path consumes four weights. The canonical
  // FBX is retained unchanged; the source audit records the >4-weight vertices.
  // We require every runtime vertex to remain normalised and weighted so any
  // loader behaviour change fails visibly rather than silently.
  for (const mesh of meshes) {
    mesh.normalizeSkinWeights();
    const weights = mesh.geometry.getAttribute('skinWeight');
    if (!weights) throw Error('Kandi Boom runtime skin weights are missing');
    for (let i = 0; i < weights.count; i++) {
      const sum = weights.getX(i) + weights.getY(i) + weights.getZ(i) + weights.getW(i);
      if (Math.abs(sum - 1) > 2e-5) throw Error('Kandi Boom four-weight runtime skin is not normalised');
    }
  }

  const modelBounds = new THREE.Box3().setFromObject(root), modelSize = modelBounds.getSize(new THREE.Vector3());
  if (!(modelSize.y > 0 && Number.isFinite(modelSize.y))) throw Error('Kandi Boom model bounds are invalid');
  const group = new THREE.Group(); group.name = 'kandi-boom-presentation';
  const motionRoot = new THREE.Group(); motionRoot.name = 'kandi-boom-motion-root';
  motionRoot.add(root); group.add(motionRoot); group.scale.setScalar(2.4 / modelSize.y);
  group.updateMatrixWorld(true);

  const rest = new Map(), restWorld = new Map(), parentRestWorld = new Map();
  const rootWorldInverse = root.matrixWorld.clone().invert();
  for (const bone of targetBoneList) {
    rest.set(bone.name, {position: bone.position.clone(), quaternion: bone.quaternion.clone(), scale: bone.scale.clone()});
    const localWorld = new THREE.Matrix4().multiplyMatrices(rootWorldInverse, bone.matrixWorld);
    restWorld.set(bone.name, new THREE.Quaternion().setFromRotationMatrix(localWorld));
    const parentWorld = bone.parent
      ? new THREE.Matrix4().multiplyMatrices(rootWorldInverse, bone.parent.matrixWorld)
      : new THREE.Matrix4();
    parentRestWorld.set(bone.name, new THREE.Quaternion().setFromRotationMatrix(parentWorld));
  }

  const source = sourcePoseEvaluator(sourceRig), sourceIndex = new Map(source.names.map((name, i) => [name, i]));
  for (const sourceName of Object.values(KANDI_RETARGET_MAP)) if (!sourceIndex.has(sourceName))
    throw Error(`Source motion rig is missing retarget joint ${sourceName}`);
  const sourceHeight = Number(sourceRig.restBounds?.size?.[2]);
  if (!(sourceHeight > 0)) throw Error('Source motion rig height is invalid');
  const sourceToTargetUnits = modelSize.y / sourceHeight;
  const desiredWorld = new Map(), sourceCalibrationInverse = new Map();
  const sourceQ = new THREE.Quaternion(), sourceDeltaQ = new THREE.Quaternion(), deltaQ = new THREE.Quaternion();
  const parentQ = new THREE.Quaternion(), localQ = new THREE.Quaternion(), sourcePosition = new THREE.Vector3();
  let profileChecked = false, calibrationCaptured = false, rootReference = null, closed = false;

  function ensureProfile(profile) {
    if (profileChecked) return;
    if (!profileMatches(sourceRig, profile)) throw Error('Source motion bindings do not match the selected package profile');
    profileChecked = true;
  }

  function calibrateChannels(profile, values) {
    if (closed) throw Error('Kandi Boom character was disposed');
    if (calibrationCaptured) throw Error('Kandi Boom source calibration has already been established');
    ensureProfile(profile);
    const matrices = source.evaluate(values);
    for (const sourceName of new Set(Object.values(KANDI_RETARGET_MAP))) {
      sourceQ.setFromRotationMatrix(matrices[sourceIndex.get(sourceName)]);
      sourceCalibrationInverse.set(sourceName, sourceQ.clone().invert());
    }
    sourcePosition.setFromMatrixPosition(matrices[sourceIndex.get('Hips')]);
    sourcePosition.applyQuaternion(SOURCE_TO_TARGET).multiplyScalar(sourceToTargetUnits);
    rootReference = sourcePosition.clone();
    calibrationCaptured = true;
  }

  function resetTarget() {
    for (const bone of targetBoneList) {
      const value = rest.get(bone.name);
      bone.position.copy(value.position); bone.quaternion.copy(value.quaternion); bone.scale.copy(value.scale);
    }
  }

  function applyChannels(profile, values) {
    if (closed) throw Error('Kandi Boom character was disposed');
    ensureProfile(profile);
    if (!calibrationCaptured) throw Error('Kandi Boom source calibration must be established before retargeting');
    const matrices = source.evaluate(values);
    resetTarget(); desiredWorld.clear();
    root.updateMatrixWorld(true);
    for (const record of targetRig.bones) {
      const bone = targetBones.get(record.name), sourceName = KANDI_RETARGET_MAP[record.name];
      if (!sourceName) continue;
      sourceQ.setFromRotationMatrix(matrices[sourceIndex.get(sourceName)]);
      calibrationRelativeQuaternion(sourceQ, sourceCalibrationInverse.get(sourceName), sourceDeltaQ);
      deltaQ.copy(SOURCE_TO_TARGET).multiply(sourceDeltaQ).multiply(SOURCE_TO_TARGET_INV).normalize();
      const worldQ = deltaQ.multiply(restWorld.get(record.name)).normalize();
      desiredWorld.set(record.name, worldQ.clone());
      const parentName = bone.parent?.isBone ? bone.parent.name : null;
      if (parentName && desiredWorld.has(parentName)) parentQ.copy(desiredWorld.get(parentName));
      else parentQ.copy(parentRestWorld.get(record.name));
      localQ.copy(parentQ).invert().multiply(worldQ).normalize();
      bone.quaternion.copy(localQ);
    }
    // Preserve target rest offsets. Global source translation drives an outer
    // motion root relative to the retained converter calibration frame, scaled
    // by the ratio of source and Kandi skeleton heights.
    sourcePosition.setFromMatrixPosition(matrices[sourceIndex.get('Hips')]);
    sourcePosition.applyQuaternion(SOURCE_TO_TARGET).multiplyScalar(sourceToTargetUnits);
    motionRoot.position.copy(sourcePosition).sub(rootReference);
    root.updateMatrixWorld(true); group.updateMatrixWorld(true);
    for (const mesh of meshes) mesh.skeleton?.update();
  }

  const stats = {...skinStats(meshes), skinnedMeshCount: meshes.length, boneCount: targetBoneList.length,
    sourceBoneCount: sourceRig.joints.length, runtimeInfluenceLimit: 4};

  function representativeVertices(count = 40) {
    group.updateMatrixWorld(true);
    const total = meshes.reduce((sum, mesh) => sum + mesh.geometry.getAttribute('position').count, 0);
    const result = [], v = new THREE.Vector3();
    for (let i = 0; i < count; i++) {
      let index = Math.floor(i * Math.max(0, total - 1) / Math.max(1, count - 1));
      for (const mesh of meshes) {
        const n = mesh.geometry.getAttribute('position').count;
        if (index < n) { mesh.getVertexPosition(index, v); v.applyMatrix4(mesh.matrixWorld); result.push(v.toArray()); break; }
        index -= n;
      }
    }
    return result;
  }

  function frameOnFloor() {
    group.updateMatrixWorld(true);
    const box = new THREE.Box3(), v = new THREE.Vector3();
    for (const mesh of meshes) {
      const count = mesh.geometry.getAttribute('position').count;
      for (let i = 0; i < count; i++) { mesh.getVertexPosition(i, v); box.expandByPoint(v.applyMatrix4(mesh.matrixWorld)); }
    }
    if (box.isEmpty()) throw Error('Kandi Boom deformed bounds are empty');
    const centre = box.getCenter(new THREE.Vector3());
    group.position.x -= centre.x; group.position.z -= centre.z; group.position.y -= box.min.y - .025;
    group.updateMatrixWorld(true);
  }

  function diagnostics() {
    let restMaxPositionError = 0, restMaxAngularError = 0, restMaxScaleError = 0;
    for (const bone of targetBoneList) {
      const value = rest.get(bone.name);
      restMaxPositionError = Math.max(restMaxPositionError, bone.position.distanceTo(value.position));
      restMaxAngularError = Math.max(restMaxAngularError, bone.quaternion.angleTo(value.quaternion));
      restMaxScaleError = Math.max(restMaxScaleError, bone.scale.distanceTo(value.scale));
    }
    return {
      calibrated: calibrationCaptured,
      textureTransformMatched,
      fbxTextureFlipY: sourceMap.flipY,
      pbrTextureFlipY: albedo.flipY,
      restMaxPositionError, restMaxAngularError, restMaxScaleError,
    };
  }

  return Object.freeze({
    group, rootBone: targetBones.get('Hips'), targetBones: targetBoneList,
    sourceJointNames: source.names.slice(), stats: Object.freeze(stats),
    calibrateChannels, isCalibrated: () => calibrationCaptured, applyChannels, diagnostics,
    frameOnFloor, representativeVertices,
    sourceJointWorldMatrices: () => (source.lastMatrices || []).map(matrix => matrix.clone().transpose().toArray()),
    dispose() {
      if (closed) return; closed = true; group.removeFromParent();
      const geometries = new Set();
      root.traverse(object => {
        if (object.geometry && !geometries.has(object.geometry)) { geometries.add(object.geometry); object.geometry.dispose(); onGeometryDisposed(); }
        if (Array.isArray(object.material)) object.material.forEach(disposeMaterial); else disposeMaterial(object.material);
        object.skeleton?.dispose?.();
      });
      textures.forEach(texture => texture.dispose());
      targetBoneList.length = 0;
    },
  });
}
