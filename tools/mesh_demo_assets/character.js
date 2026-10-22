import * as THREE from 'three';

// These meshes are original, procedural artwork. The source joint frames stay
// unchanged: geometry is authored around the exact source skeleton at rest.
export function createSkinnedCharacter(rig, kind, {onGeometryDisposed = () => {}} = {}) {
  if (!['boxbot', 'prism'].includes(kind)) throw Error('Unknown character style');
  if (!Array.isArray(rig.joints) || !rig.joints.length || rig.joints.length > 1024)
    throw Error('Invalid source joint hierarchy');
  const bones = [], rest = [], names = new Map();
  for (const [index, joint] of rig.joints.entries()) {
    if (typeof joint.name !== 'string' || names.has(joint.name) ||
        !Number.isInteger(joint.parentIndex) || joint.parentIndex < -1 || joint.parentIndex >= index ||
        !Array.isArray(joint.offset) || joint.offset.length !== 3 || !joint.offset.every(Number.isFinite))
      throw Error('Invalid source joint rest transform');
    const bone = new THREE.Bone(); bone.name = joint.name;
    bone.position.fromArray(joint.offset);
    if (joint.parentIndex >= 0) bones[joint.parentIndex].add(bone);
    bones.push(bone); names.set(joint.name, index);
    rest.push(new THREE.Vector3().fromArray(joint.offset).add(joint.parentIndex < 0 ? new THREE.Vector3() : rest[joint.parentIndex]));
  }
  const byName = name => {
    const index = names.get(name);
    if (index === undefined) throw Error(`Character requires source joint ${name}`);
    return index;
  };
  const p = name => rest[byName(name)].clone();
  const extent = new THREE.Box3().setFromPoints(rest);
  const height = extent.max.z - extent.min.z + Math.max(rig.joints[byName('Head')].length, 0.5) * 1.4;
  if (!(height > 0 && Number.isFinite(height))) throw Error('Invalid source skeleton height');
  const h = height, robot = kind === 'boxbot';
  const palette = robot
    ? {body: '#e6b948', light: '#f6d879', dark: '#244e51', limb: '#e7ede0', joint: '#3e6d69', eye: '#b5fff1'}
    : {body: '#dd6b57', light: '#f8b894', dark: '#372c49', limb: '#e8e1cf', joint: '#ad5060', eye: '#fbf3d5'};
  const vertices = [], normals = [], colors = [], indices = [], weights = [];
  let blendedVertexCount = 0;
  function append(geometry, matrix, color, owner, blend) {
    const flat = geometry.index ? geometry.toNonIndexed() : geometry;
    if (flat !== geometry) geometry.dispose();
    const normalMatrix = new THREE.Matrix3().getNormalMatrix(matrix), c = new THREE.Color(color);
    const position = flat.getAttribute('position'), normal = flat.getAttribute('normal');
    const v = new THREE.Vector3(), n = new THREE.Vector3();
    for (let i = 0; i < position.count; i++) {
      v.fromBufferAttribute(position, i);
      const mix = blend ? blend(v) : null;
      v.applyMatrix4(matrix); n.fromBufferAttribute(normal, i).applyNormalMatrix(normalMatrix);
      vertices.push(v.x, v.y, v.z); normals.push(n.x, n.y, n.z); colors.push(c.r, c.g, c.b);
      const amount = mix ? Math.min(1, Math.max(0, mix.weight)) : 0;
      indices.push(owner, mix?.index ?? owner, 0, 0); weights.push(1 - amount, amount, 0, 0);
      if (amount > 0 && amount < 1) blendedVertexCount++;
    }
    flat.dispose();
  }
  function solid(center, size, color, owner, shape = 'box') {
    const geometry = shape === 'facet' ? new THREE.IcosahedronGeometry(1, 0) : new THREE.BoxGeometry(1, 1, 1);
    append(geometry, new THREE.Matrix4().compose(center, new THREE.Quaternion(), new THREE.Vector3(...size)), color, owner);
  }
  function segment(a, b, width, depth, color, owner, child, taper = 0.85) {
    const direction = b.clone().sub(a), length = direction.length();
    if (length < h * 0.003) return;
    const geometry = robot
      ? new THREE.BoxGeometry(width, length, depth, 1, 4, 1)
      : new THREE.CylinderGeometry(width * taper / 2, width / 2, length, 5, 4, false);
    const scale = robot ? new THREE.Vector3(1, 1, 1) : new THREE.Vector3(1, 1, depth / width);
    const matrix = new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5),
      new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize()), scale);
    append(geometry, matrix, color, owner, child === undefined ? null : local => ({
      index: child, weight: Math.max(0, (local.y / length + 0.5 - 0.72) / 0.28) * 0.38,
    }));
  }
  const hips = byName('Hips'), spine = byName('Spine'), chest = byName('Spine1'), head = byName('Head');
  // Broad volumes make these characters surfaces, rather than bone diagrams.
  solid(p('Hips').add(new THREE.Vector3(0, 0, -h * 0.012)), [h * .205, h * .12, h * .115], palette.dark, hips, robot ? 'box' : 'facet');
  segment(p('Hips'), p('Spine'), h * .15, h * .11, palette.joint, hips, spine);
  const torsoBottom = p('Spine').add(new THREE.Vector3(0, 0, -h * .025));
  const torsoTop = p('Neck').add(new THREE.Vector3(0, 0, h * .016));
  segment(torsoBottom, torsoTop, h * (robot ? .275 : .29), h * .13, palette.body, spine, chest, robot ? 1 : 1.25);
  if (robot) {
    solid(p('Spine').add(new THREE.Vector3(0, -h * .071, h * .045)), [h * .11, h * .014, h * .05], palette.dark, chest);
    for (let i = -1; i <= 1; i++) solid(p('Spine').add(new THREE.Vector3(i * h * .028, -h * .081, h * .045)),
      [h * .015, h * .008, h * .014], palette.eye, chest);
  } else {
    solid(p('Spine').add(new THREE.Vector3(0, -h * .066, h * .038)), [h * .08, h * .035, h * .08], palette.light, chest, 'facet');
  }
  segment(p('Neck'), p('Head'), h * .065, h * .065, palette.dark, byName('Neck'), head);
  const headCenter = p('Head').add(new THREE.Vector3(0, 0, h * .023));
  solid(headCenter, [h * .14, h * .12, h * .14], palette.light, head, robot ? 'box' : 'facet');
  if (robot) {
    solid(headCenter.clone().add(new THREE.Vector3(0, -h * .064, 0)), [h * .12, h * .014, h * .05], palette.dark, head);
    for (const side of [-1, 1]) solid(headCenter.clone().add(new THREE.Vector3(side * h * .032, -h * .073, h * .002)),
      [h * .024, h * .008, h * .016], palette.eye, head);
    solid(headCenter.clone().add(new THREE.Vector3(0, 0, h * .087)), [h * .016, h * .016, h * .035], palette.dark, head);
    solid(headCenter.clone().add(new THREE.Vector3(0, 0, h * .11)), [h * .033, h * .033, h * .026], palette.eye, head);
  } else {
    solid(headCenter.clone().add(new THREE.Vector3(0, -h * .085, h * .007)), [h * .09, h * .018, h * .035], palette.dark, head, 'facet');
    solid(headCenter.clone().add(new THREE.Vector3(0, 0, h * .11)), [h * .075, h * .07, h * .10], palette.body, head, 'facet');
  }
  for (const side of ['Left', 'Right']) {
    const arm = byName(side + 'Arm'), elbow = byName(side + 'ForeArm'), hand = byName(side + 'Hand');
    const thigh = byName(side + 'UpLeg'), knee = byName(side + 'Leg'), foot = byName(side + 'Foot');
    const toe = byName(side + 'ToeBase');
    segment(p(side + 'Arm'), p(side + 'ForeArm'), h * .082, h * .08, palette.body, arm, elbow);
    segment(p(side + 'ForeArm'), p(side + 'Hand'), h * .069, h * .066, palette.limb, elbow, hand);
    solid(p(side + 'Arm'), [h * .105, h * .095, h * .10], palette.light, arm, robot ? 'box' : 'facet');
    solid(p(side + 'ForeArm'), [h * .075, h * .075, h * .075], palette.dark, elbow, robot ? 'box' : 'facet');
    solid(p(side + 'Hand'), [h * .072, h * .063, h * .085], palette.dark, hand, robot ? 'box' : 'facet');
    segment(p(side + 'UpLeg'), p(side + 'Leg'), h * .11, h * .11, palette.body, thigh, knee);
    segment(p(side + 'Leg'), p(side + 'Foot'), h * .09, h * .085, palette.limb, knee, foot);
    solid(p(side + 'Leg'), [h * .10, h * .095, h * .10], palette.dark, knee, robot ? 'box' : 'facet');
    const footCentre = p(side + 'Foot').lerp(p(side + 'ToeBase'), .48).add(new THREE.Vector3(0, 0, -h * .012));
    solid(footCentre, [h * .09, h * .14, h * .065], palette.dark, foot, robot ? 'box' : 'facet');
    segment(p(side + 'Foot'), p(side + 'ToeBase'), h * .075, h * .065, palette.joint, foot, toe);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geometry.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(indices, 4));
  geometry.setAttribute('skinWeight', new THREE.Float32BufferAttribute(weights, 4));
  const material = new THREE.MeshStandardMaterial({vertexColors: true, roughness: .68, metalness: robot ? .12 : .02, flatShading: true});
  const mesh = new THREE.SkinnedMesh(geometry, material);
  mesh.name = kind + '-skin'; mesh.castShadow = true; mesh.receiveShadow = true; mesh.frustumCulled = false;
  for (let i = 0; i < bones.length; i++) if (rig.joints[i].parentIndex < 0) mesh.add(bones[i]);
  mesh.updateMatrixWorld(true);
  const skeleton = new THREE.Skeleton(bones); mesh.bind(skeleton); mesh.normalizeSkinWeights();
  const group = new THREE.Group(); group.name = kind + '-presentation';
  group.rotation.x = -Math.PI / 2; group.scale.setScalar(2.4 / height); group.add(mesh);
  const expectedChannels = rig.channels;
  if (!Array.isArray(expectedChannels) || !expectedChannels.length) throw Error('Source channel map is missing');
  let closed = false, profileChecked = false;
  function applyChannels(profile, values) {
    if (closed) throw Error('Character was disposed');
    if (!profileChecked) {
      if (profile.channels.length !== expectedChannels.length || profile.channels.some((channel, i) => {
        const expected = expectedChannels[i];
        return channel.number !== i + 1 || ['name', 'bone', 'data_path', 'array_index', 'minimum', 'maximum', 'neutral'].some(key => channel[key] !== expected[key]);
      })) throw Error('Saved scene channel bindings do not match the loaded profile');
      profileChecked = true;
    }
    if (values.length !== expectedChannels.length || values.some(value => typeof value !== 'number' || !Number.isFinite(value)))
      throw Error('Invalid decoded source pose');
    for (let i = 0; i < bones.length; i++) {
      const joint = rig.joints[i], bone = bones[i];
      bone.position.fromArray(joint.offset); bone.quaternion.identity(); bone.scale.set(1, 1, 1);
      if (joint.positionChannelIndices) for (let axis = 0; axis < 3; axis++)
        bone.position.setComponent(axis, joint.offset[axis] + values[joint.positionChannelIndices[axis]]);
      if (joint.rotationChannelIndices) {
        const [w, x, y, z] = joint.rotationChannelIndices.map(index => values[index]);
        if (Math.abs(Math.hypot(w, x, y, z) - 1) > .0001) throw Error('Source quaternion is not unit length');
        bone.quaternion.set(x, y, z, w);
      }
      if (joint.scaleChannelIndices) bone.scale.fromArray(joint.scaleChannelIndices.map(index => values[index]));
    }
    group.updateMatrixWorld(true); skeleton.update();
  }
  function representativeVertices(count = 32) {
    group.updateMatrixWorld(true); skeleton.update();
    const out = [], v = new THREE.Vector3();
    for (let i = 0; i < count; i++) {
      mesh.getVertexPosition(Math.floor(i * (geometry.attributes.position.count - 1) / Math.max(1, count - 1)), v);
      v.applyMatrix4(mesh.matrixWorld); out.push(v.toArray());
    }
    return out;
  }
  function frameOnFloor() {
    group.updateMatrixWorld(true); skeleton.update();
    const box = new THREE.Box3(), v = new THREE.Vector3();
    for (let i = 0; i < geometry.attributes.position.count; i++) {
      mesh.getVertexPosition(i, v); box.expandByPoint(v.applyMatrix4(mesh.matrixWorld));
    }
    const centre = box.getCenter(new THREE.Vector3());
    group.position.x -= centre.x; group.position.z -= centre.z; group.position.y -= box.min.y - .025;
    group.updateMatrixWorld(true); skeleton.update();
  }
  return Object.freeze({group, mesh, skeleton, bones, height, applyChannels, frameOnFloor, representativeVertices,
    stats: Object.freeze({skinnedMeshCount: 1, vertexCount: vertices.length / 3, boneCount: bones.length,
      weightedVertexCount: weights.length / 4, blendedVertexCount}),
    dispose() {
      if (closed) return; closed = true;
      group.removeFromParent(); geometry.dispose(); onGeometryDisposed(); material.dispose(); skeleton.dispose();
      bones.length = 0;
    },
  });
}
