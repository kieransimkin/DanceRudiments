import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as THREE from 'three';
import {
  KANDI_RETARGET_MAP, calibrationRelativeQuaternion, copyFbxTextureTransform,
} from '../../tools/mesh_demo_assets/kandi-boom.js';

test('Kandi Boom production retarget map covers the deforming target chains', () => {
  assert.deepEqual(Object.keys(KANDI_RETARGET_MAP), [
    'Hips', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase',
    'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase',
    'Spine02', 'Spine01', 'Spine', 'neck', 'Head',
    'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand',
    'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand',
  ]);
  assert.equal(KANDI_RETARGET_MAP.Spine02, 'LowerBack');
  assert.equal(KANDI_RETARGET_MAP.Spine, 'Spine1');
  assert.equal(KANDI_RETARGET_MAP.neck, 'Neck');
});

test('replacement PBR maps inherit the FBX texture coordinate contract without copying color space', () => {
  const source = new THREE.Texture(), target = new THREE.Texture();
  source.flipY = true; source.channel = 1;
  source.wrapS = THREE.RepeatWrapping; source.wrapT = THREE.ClampToEdgeWrapping;
  source.offset.set(.125, .25); source.repeat.set(1.5, .75); source.center.set(.5, .5); source.rotation = .3;
  source.magFilter = THREE.NearestFilter; source.minFilter = THREE.LinearMipmapLinearFilter;
  source.anisotropy = 4; source.matrixAutoUpdate = false; source.updateMatrix();
  target.flipY = false; target.colorSpace = THREE.SRGBColorSpace;
  const colorSpace = target.colorSpace;
  copyFbxTextureTransform(source, target);
  assert.equal(target.flipY, source.flipY);
  assert.equal(target.channel, source.channel);
  assert.equal(target.wrapS, source.wrapS); assert.equal(target.wrapT, source.wrapT);
  assert.deepEqual(target.offset.toArray(), source.offset.toArray());
  assert.deepEqual(target.repeat.toArray(), source.repeat.toArray());
  assert.deepEqual(target.center.toArray(), source.center.toArray());
  assert.equal(target.rotation, source.rotation);
  assert.deepEqual(target.matrix.toArray(), source.matrix.toArray());
  assert.equal(target.colorSpace, colorSpace);
});

test('source motion is measured relative to the retained converter calibration pose', () => {
  const calibration = new THREE.Quaternion().setFromEuler(new THREE.Euler(.12, -.21, .08));
  const motionDelta = new THREE.Quaternion().setFromEuler(new THREE.Euler(-.17, .09, .31));
  const current = motionDelta.clone().multiply(calibration);
  const calibrationInverse = calibration.clone().invert();
  const actual = calibrationRelativeQuaternion(current, calibrationInverse);
  assert.ok(actual.angleTo(motionDelta) < 1e-7);
  const neutral = calibrationRelativeQuaternion(calibration, calibrationInverse);
  assert.ok(neutral.angleTo(new THREE.Quaternion()) < 1e-7);
});

test('production gallery imports Kandi Boom and does not present procedural fixtures', () => {
  const app = readFileSync('tools/mesh_demo_assets/app.js', 'utf8');
  const html = readFileSync('tools/mesh_demo_assets/index.html', 'utf8');
  assert.match(app, /createKandiBoomCharacter/);
  assert.doesNotMatch(app, /createSkinnedCharacter/);
  assert.match(html, /Kandi Boom/);
  assert.doesNotMatch(html, />Boxbot</);
  assert.doesNotMatch(html, />Prism</);
});
