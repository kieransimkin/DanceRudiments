import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as THREE from 'three';
import {
  KANDI_RETARGET_AIM_CHILD, KANDI_RETARGET_MAP, calibrationRelativeQuaternion,
  copyFbxTextureTransform, retargetAimCorrection,
  sourcePoseEvaluator, sourceRetargetConfiguration,
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

test('per-control retarget reference aligns Kandi A-pose aims to CMU calibration aims', () => {
  assert.equal(KANDI_RETARGET_AIM_CHILD.LeftShoulder, 'LeftArm');
  assert.equal(KANDI_RETARGET_AIM_CHILD.LeftArm, 'LeftForeArm');
  assert.equal(KANDI_RETARGET_AIM_CHILD.RightArm, 'RightForeArm');
  assert.equal(KANDI_RETARGET_AIM_CHILD.LeftUpLeg, 'LeftLeg');

  const kandiLeftUpperArm = new THREE.Vector3(
    11.505179405212402, -17.811187744140625, -1.8974318504333496,
  );
  const cmuCalibrationAim = new THREE.Vector3(1, -.0875, 0).normalize();
  const correction = retargetAimCorrection(kandiLeftUpperArm, cmuCalibrationAim);
  const aligned = kandiLeftUpperArm.clone().normalize().applyQuaternion(correction);
  assert.ok(aligned.angleTo(cmuCalibrationAim) < 1e-7);
  assert.ok(new THREE.Quaternion().angleTo(correction) > .5);
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

test('portable source evaluator composes rest matrices before local TRS in hierarchy order',()=>{
  const rest=new THREE.Matrix4().makeRotationZ(Math.PI/2);rest.setPosition(10,0,0);
  const childRest=new THREE.Matrix4().makeTranslation(0,2,0);
  const rig={channels:[{},{},{}],joints:[
    {name:'child',parentIndex:1,localRestMatrix:childRest.clone().transpose().toArray(),positionChannelIndices:[0,1,2]},
    {name:'root',parentIndex:-1,localRestMatrix:rest.clone().transpose().toArray()},
  ]};
  const result=sourcePoseEvaluator(rig).evaluate([1,0,0]);
  const actual=new THREE.Vector3().setFromMatrixPosition(result[0]);
  assert.ok(actual.distanceTo(new THREE.Vector3(8,1,0))<1e-12);
  const legacy=sourcePoseEvaluator({channels:[{},{},{}],joints:[
    {name:'root',parentIndex:-1,offset:[2,3,4],positionChannelIndices:[0,1,2]}]}).evaluate([1,2,3]);
  assert.deepEqual(new THREE.Vector3().setFromMatrixPosition(legacy[0]).toArray(),[3,5,7]);
  assert.throws(()=>sourcePoseEvaluator({...rig,joints:[{...rig.joints[0],parentIndex:0},rig.joints[1]]}),/parent index/);
  assert.throws(()=>sourcePoseEvaluator(rig).evaluate([1,NaN,3]),/finite/);
});

test('generic Kandi sources require a complete explicit map and a declared unit orientation',()=>{
  const map=Object.fromEntries(Object.keys(KANDI_RETARGET_MAP).map((key,index)=>[key,`bone${index}`]));
  const rig={joints:Object.values(map).map(name=>({name})),retargetMap:map,
    sourceToTargetQuaternion:[1,0,0,0],sourceHeightAxis:1,restBounds:{size:[1,8,3]}};
  const config=sourceRetargetConfiguration(rig);assert.equal(config.sourceHeight,8);
  assert.equal(config.map.Hips,'bone0');assert.equal(config.sourceToTarget.w,1);
  assert.throws(()=>sourceRetargetConfiguration({...rig,retargetMap:{...map,Hips:'missing'}}),/complete/);
  assert.throws(()=>sourceRetargetConfiguration({...rig,sourceToTargetQuaternion:[2,0,0,0]}),/unit quaternion/);
  assert.throws(()=>sourceRetargetConfiguration({...rig,sourceHeightAxis:3}),/height axis/);
});
