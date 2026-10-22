import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {KANDI_RETARGET_MAP} from '../../tools/mesh_demo_assets/kandi-boom.js';

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

test('production gallery imports Kandi Boom and does not present procedural fixtures', () => {
  const app = readFileSync('tools/mesh_demo_assets/app.js', 'utf8');
  const html = readFileSync('tools/mesh_demo_assets/index.html', 'utf8');
  assert.match(app, /createKandiBoomCharacter/);
  assert.doesNotMatch(app, /createSkinnedCharacter/);
  assert.match(html, /Kandi Boom/);
  assert.doesNotMatch(html, />Boxbot</);
  assert.doesNotMatch(html, />Prism</);
});
