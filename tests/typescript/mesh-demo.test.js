import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {PipTransport} from '../../tools/mesh_demo_assets/transport.js';
import {createSkinnedCharacter} from '../../tools/mesh_demo_assets/character.js';

// Deliberately synthetic proportions/poses, with the source-style joint names
// needed by both original character designs. No downloaded recording fixture.
function fixture() {
  const joints = [], channels = [], names = new Map();
  function add(name, parent, offset) {
    const joint = {name, parentIndex: parent === null ? -1 : names.get(parent), offset,
      length: 1, positionChannelIndices: null, rotationChannelIndices: [], scaleChannelIndices: null};
    names.set(name, joints.length); joints.push(joint);
    if (parent === null) {
      joint.positionChannelIndices = [0, 1, 2];
      for (let axis = 0; axis < 3; axis++) channels.push({number: channels.length + 1, name: `root_location_${axis}`,
        bone: name, data_path: 'location', array_index: axis, minimum: -100, maximum: 100, neutral: 0});
    }
    for (let axis = 0; axis < 4; axis++) {
      joint.rotationChannelIndices.push(channels.length);
      channels.push({number: channels.length + 1, name: `${name.toLowerCase()}_q_${axis}`,
        bone: name, data_path: 'rotation_quaternion', array_index: axis, minimum: -1, maximum: 1, neutral: axis === 0 ? 1 : 0});
    }
  }
  add('Hips', null, [0, 0, 0]); add('LowerBack', 'Hips', [0, 0, 0]);
  add('Spine', 'LowerBack', [0, 0, 2]); add('Spine1', 'Spine', [0, 0, 2]);
  add('Neck', 'Spine1', [0, 0, 0]); add('Neck1', 'Neck', [0, 0, 1]); add('Head', 'Neck1', [0, 0, 1]);
  for (const [side, sign] of [['Left', 1], ['Right', -1]]) {
    add(side + 'Shoulder', 'Spine1', [0, 0, 0]); add(side + 'Arm', side + 'Shoulder', [sign * 2, 0, 0]);
    add(side + 'ForeArm', side + 'Arm', [sign * 3, 0, 0]); add(side + 'Hand', side + 'ForeArm', [sign * 2, 0, 0]);
    add(side + 'UpLeg', 'Hips', [sign, 0, -1]); add(side + 'Leg', side + 'UpLeg', [0, 0, -4]);
    add(side + 'Foot', side + 'Leg', [0, 0, -4]); add(side + 'ToeBase', side + 'Foot', [0, -1, 0]);
  }
  return {rig: {joints, channels}, profile: {channels}, pose: channels.map(channel => channel.neutral), names};
}

test('time-only transport uses absolute integer pips without repeated-play drift', () => {
  let now = 0;
  const clock = new PipTransport(-64, 1000, () => now);
  clock.play(); now = 1001; assert.equal(clock.pip(), 0);
  clock.play(); now = 2000; assert.equal(clock.pip(), 64);
  now = 2500; clock.setSpeed(.5); now = 3500; assert.equal(clock.pip(), 128);
  clock.pause(); now = 9000; assert.equal(clock.pip(), 128);
  clock.seek(-32); clock.play(); now = 10000; assert.equal(clock.pip(), 0);
  assert.throws(() => clock.seek(.5), /Seek/);
});

test('non-looping transport preserves exact endpoint and can seek/restart explicitly', () => {
  let now = 0;
  const clock = new PipTransport(10, 74, () => now);
  clock.play(); now = 20000; assert.equal(clock.pip(), 74); assert.equal(clock.playing, false);
  now += 20000; assert.equal(clock.pip(), 74);
  clock.seek(10); clock.play(); now += 500; assert.equal(clock.pip(), 42);
  assert.throws(() => clock.seek(75), /outside/); assert.throws(() => clock.setSpeed(0), /speed/);
});

test('both original characters have real skinned surfaces, unit weights and blended joints', () => {
  const f = fixture(), counts = [];
  for (const kind of ['boxbot', 'prism']) {
    let disposed = 0;
    const character = createSkinnedCharacter(f.rig, kind, {onGeometryDisposed: () => disposed++});
    assert.equal(character.mesh.isSkinnedMesh, true); assert.equal(character.stats.boneCount, f.rig.joints.length);
    assert.ok(character.stats.vertexCount > 1000); assert.ok(character.stats.blendedVertexCount > 100);
    const weights = character.mesh.geometry.getAttribute('skinWeight');
    for (let i = 0; i < weights.count; i++) assert.ok(Math.abs(weights.getX(i) + weights.getY(i) + weights.getZ(i) + weights.getW(i) - 1) < 1e-6);
    character.applyChannels(f.profile, f.pose); counts.push(character.stats.vertexCount);
    character.dispose(); character.dispose(); assert.equal(disposed, 1);
    assert.throws(() => character.applyChannels(f.profile, f.pose), /disposed/);
  }
  assert.notEqual(counts[0], counts[1]);
});

test('source identity rest frames and wxyz physical poses drive the skin without rest-axis guessing', () => {
  const f = fixture(), character = createSkinnedCharacter(f.rig, 'boxbot');
  const before = (() => { character.applyChannels(f.profile, f.pose); return character.representativeVertices(); })();
  const pose = f.pose.slice(); pose[0] = 3; pose[1] = -2; pose[2] = 5;
  const armIndex = f.names.get('LeftArm'), arm = f.rig.joints[armIndex];
  for (const [i, value] of [Math.SQRT1_2, 0, 0, Math.SQRT1_2].entries()) pose[arm.rotationChannelIndices[i]] = value;
  character.applyChannels(f.profile, pose);
  assert.deepEqual(character.bones[0].position.toArray(), [3, -2, 5]);
  assert.ok(character.bones[armIndex].quaternion.equals(new THREE.Quaternion(0, 0, Math.SQRT1_2, Math.SQRT1_2)));
  const inversePresentation = character.group.matrixWorld.clone().invert();
  const elbow = character.bones[f.names.get('LeftForeArm')];
  const sourceMatrix = new THREE.Matrix4().multiplyMatrices(inversePresentation, elbow.matrixWorld);
  const sourcePosition = new THREE.Vector3().setFromMatrixPosition(sourceMatrix);
  assert.ok(sourcePosition.distanceTo(new THREE.Vector3(5, 1, 9)) < 1e-10);
  const after = character.representativeVertices();
  assert.ok(after.some((v, i) => v.some((value, j) => Math.abs(value - before[i][j]) > .01)));
  character.dispose();
  const bad = createSkinnedCharacter(f.rig, 'prism'), wrong = structuredClone(f.profile);
  wrong.channels[0].number = 2;
  assert.throws(() => bad.applyChannels(wrong, f.pose), /bindings/); bad.dispose();
});
