import test from 'node:test';
import assert from 'node:assert/strict';
import {validateCollectionScenes} from '../../tools/build_loop_review_site.mjs';

function fixture(){const id='source-'+'a'.repeat(64);return {
  config:{scenes:[{id,sourceSha256:'a'.repeat(64),rigPath:'source/rig.json',manifestPath:'source/manifest.json',
    sceneRigSha256:'b'.repeat(64),manifestSha256:'c'.repeat(64),expectedProfile:{fingerprint:'d'.repeat(64)}}],
    auditionCalibrations:{[id]:{source_rig_sha256:'b'.repeat(64),target_rig_sha256:'e'.repeat(64)}},
    auditionTargets:{[id]:{rig_sha256:'e'.repeat(64),asset_sha256:'f'.repeat(64)}},character:{fbxAssetSha256:'f'.repeat(64)}},
  inventory:{files:{'source/rig.json':{sha256:'b'.repeat(64)},'source/manifest.json':{sha256:'c'.repeat(64)}}}};}
test('collection scenes bind original source, profile, target and saved calibration',()=>{
  const {config,inventory}=fixture();assert.doesNotThrow(()=>validateCollectionScenes(config,inventory));
  for(const change of [c=>c.scenes.push(c.scenes[0]),c=>c.scenes[0].sourceSha256='f'.repeat(64),
    c=>c.scenes[0].rigPath='../rig.json',c=>c.scenes[0].expectedProfile.fingerprint='stale',
    c=>c.auditionCalibrations[c.scenes[0].id].source_rig_sha256='f'.repeat(64),
    c=>c.auditionTargets[c.scenes[0].id].asset_sha256='a'.repeat(64)]){
    const broken=structuredClone(config);change(broken);
    assert.throws(()=>validateCollectionScenes(broken,inventory),/identity differs/);
  }
});
