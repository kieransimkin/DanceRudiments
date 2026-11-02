#!/usr/bin/env python3
"""Prepare local collection scenes with the existing portable-rig/Kandi adapter.

Only sources with a declared original calibration frame and the reviewed bone
map enter the mesh view. Other Actions remain explicitly unavailable for skin
review; this tool never invents a calibration or changes the public gallery.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from build_loop_review_assets import digest,descriptor,prepare_review_assets,write_json
from build_song_loop_preview import collection_jobs
from dancerudiments_authoring.bvh_import import parse_bvh,override_bvh_frame_time
from dancerudiments_authoring.motion_import import load_capture,write_capture
from dancerudiments_authoring.loop_review import document_hash
from dancerudiments_authoring.source_loop_analysis import source_capture_from_bvh
from import_motion_collection import preflight
from verify_motion_package import verify_packages


def build(index_path,cache_root,output):
    index_path,cache_root,output=map(lambda p:Path(p).resolve(),(index_path,cache_root,output))
    if output.exists():raise FileExistsError('Use a new collection mesh output')
    preflight(output.parent)
    jobs,index=collection_jobs(index_path)
    source_plan=json.loads((ROOT/'motion-packages/sources.json').read_text(encoding='utf-8'))
    cmu=next(item for item in source_plan['sources'] if item['id']=='cmu_dance')
    manifest=json.loads((ROOT/'motion-packages/cmu-dance-sources.json').read_text(encoding='utf-8'))
    originals={item['sha256']:item for item in reversed(manifest['files'])}
    settings={key:value for key,value in cmu['conversion'].items() if key in
        ('unit_scale','axis_forward','axis_up','location_range','translation_convention','root_offset_policy')}
    scenes=[];calibrations={};targets={};unavailable=[];character=None
    with tempfile.TemporaryDirectory(prefix='.collection-mesh-',dir=output.parent) as temporary:
        stage=Path(temporary)/'assets';stage.mkdir()
        for job,action in zip(jobs,index['actions']):
            if action['source_id']!='cmu_dance':
                unavailable.append(dict(source_sha256=action['source_sha256'],source_id=action['source_id'],
                    member=action['member'],reason='No reviewed Kandi bone map and original calibration frame in this source recipe'))
                continue
            record=originals[action['source_sha256']]
            if record.get('calibration_frame_count')!=1 or record.get('first_frame_kind')!='converter-added-calibration-t-pose':
                raise ValueError('CMU source has no declared original calibration frame')
            raw=cache_root/'cmu-dance'/record['cache_path']
            if digest(raw)!=action['source_sha256']:raise ValueError('Original BVH changed')
            clip=parse_bvh(raw.read_bytes(),source_id='cmu_dance',source_name=action['member'],**settings)
            entry=cmu['archives'][0]['members'][action['member']]
            if entry.get('frame_time_override'):clip=override_bvh_frame_time(clip,**entry['frame_time_override'])
            calibration=source_capture_from_bvh(clip,calibration_frames=0)
            capture_path=job/'source.capture.json';capture=load_capture(capture_path)
            if calibration.profile.fingerprint!=capture.profile.fingerprint:
                raise ValueError('Original calibration and analysed source profile differ')
            calibration=replace(calibration,frame_times_seconds=(calibration.frame_times_seconds[0],),frames=(calibration.frames[0],))
            with tempfile.TemporaryDirectory(prefix='.action-',dir=temporary) as action_temp:
                action_temp=Path(action_temp);calibration_path=action_temp/'calibration.capture.json'
                write_capture(calibration_path,calibration)
                prepared=action_temp/'prepared'
                result=prepare_review_assets(capture_path,prepared,
                    start_seconds=capture.frame_times_seconds[0],end_seconds=capture.frame_times_seconds[-1],
                    original_source_sha256=action['source_sha256'],calibration_capture_path=calibration_path,
                    calibration_seconds=calibration.frame_times_seconds[0],license=cmu['license'],
                    title=record.get('official_title',record['title']))
                config=result['config']
                if character is None:
                    character=config['character'];shutil.copytree(prepared/'characters',stage/'characters')
                elif character!=config['character']:raise ValueError('Kandi target changed during collection build')
                scene=config['scenes'][0]
                identifier='source-'+action['source_sha256']
                base=stage/'motions'/identifier;base.parent.mkdir(exist_ok=True)
                shutil.move(str(prepared/'motions/review-action'),base)
                rig=json.loads((base/'scene-rig.json').read_text(encoding='ascii'));rig['sceneId']=identifier
                write_json(base/'scene-rig.json',rig)
                scene.update(id=identifier,title=record['id']+' — '+record.get('official_title',record['title']),
                    sourceTitle=record.get('official_title',record['title']),sourceUrl=record['source_url'],
                    manifestPath=f'motions/{identifier}/manifest.json',rigPath=f'motions/{identifier}/scene-rig.json',
                    sceneRigSha256=digest(base/'scene-rig.json'))
                evidence=dict(config['reviewCalibrationEvidence'],source_rig_sha256=scene['sceneRigSha256'])
                calibrations[identifier]=evidence
                targets[identifier]=dict(config['reviewTarget'],calibration_sha256=document_hash(evidence))
                scenes.append(scene)
                checked=verify_packages([base])
                if not checked['passed']:raise ValueError('Prepared source-time native package failed verification')
                print(json.dumps({'prepared':len(scenes),'source':record['id'],'native_verified':True}),flush=True)
        if not scenes:raise ValueError('No source has a supported target/calibration')
        config=dict(reviewWorkspace=False,collectionAudition=True,scenes=scenes,character=character,
            auditionCalibrations=calibrations,auditionTargets=targets,
            sourceCollectionSha256=digest(index_path),unavailable=unavailable)
        write_json(stage/'config.json',config)
        files={path.relative_to(stage).as_posix():descriptor(path) for path in sorted(stage.rglob('*'))
            if path.is_file() and path.name!='config.json'}
        write_json(stage/'assets.json',{'format':'dancerudiments.loop-review-assets.v1','files':files})
        stage.rename(output)
    return {'output':str(output),'mesh_scenes':len(scenes),'unavailable':unavailable}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection-index',type=Path,required=True)
    parser.add_argument('--cache-root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.collection_index,args.cache_root,args.output_dir),indent=2))

if __name__=='__main__':main()
