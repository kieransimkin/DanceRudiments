#!/usr/bin/env python3
"""Source-first full Action + loop search over an exact Blender extraction index.

Consumes only the `.capture.json` files explicitly listed by Blender's index.
Validates original source/profile identities; does not open or execute .blend/FBX
files, download assets, follow directory symlinks or retarget an untrusted rig.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePath
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from dancerudiments_authoring.motion_import import load_capture
from dancerudiments_authoring.source_loop_analysis import analyse_source_capture
from import_motion_collection import preflight, slug

SHA = re.compile(r'^[a-f0-9]{64}$')


def analyse_batch(index_path, output_root, *, max_previews=4, min_full_confidence=.70,
                  target_bpm=None, verify_native=False, max_actions=100):
    index_path = Path(index_path).expanduser().resolve()
    root = index_path.parent
    output_root = Path(output_root).expanduser().absolute()
    if index_path.name != 'index.json':
        raise ValueError('Choose the exact index.json from Blender Action extraction')
    if not index_path.is_file() or index_path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Missing or oversized Blender extraction index')
    index = json.loads(index_path.read_text(encoding='utf-8'))
    if index.get('format') != 'dancerudiments.blender-import' or index.get('schema_version') != 1:
        raise ValueError('Not a versioned DanceRudiments Blender extraction index')
    source = index.get('source')
    if not isinstance(source, dict) or not isinstance(source.get('sha256'), str) or not SHA.fullmatch(source['sha256']):
        raise ValueError('Original source SHA-256 is required in Blender index')
    inputs = index.get('captures')
    if not isinstance(inputs, list) or not inputs or len(inputs) > 1000:
        raise ValueError('Blender index must list 1..1000 original captures')
    if type(max_actions) is not int or not 1 <= max_actions <= 1000:
        raise ValueError('max_actions must be within 1..1000')
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError('Output directory must be new')
    # The input extraction folder must remain disjoint from its analysis outputs.
    if output_root == root or root.is_relative_to(output_root) or output_root.is_relative_to(root):
        raise ValueError('Analysis output may not contain the original extraction')
    preflight(output_root.parent)
    report = dict(format='dancerudiments.blender-source-motion-analysis', schema_version=1,
                  extraction_index_sha256=hashlib.sha256(index_path.read_bytes()).hexdigest(),
                  source_file_sha256=source['sha256'],
                  source_file_details=source, actions=[], failures=[],
                  full_motion_shortlist=[], loopable_shortlist=[],
                  full_motion_confidence_threshold=min_full_confidence,
                  timing_status='kinematic_estimate_not_musically_verified')
    seen_paths, seen_bindings = set(), set()
    with tempfile.TemporaryDirectory(prefix='.blender-source-analysis-', dir=output_root.parent) as temporary:
        stage = Path(temporary)/'output'; stage.mkdir()
        for row in inputs[:max_actions]:
            identity = {'capture':row.get('capture'), 'binding_id':row.get('binding_id')} if isinstance(row,dict) else {}
            try:
                if not isinstance(row,dict):
                    raise ValueError('Invalid indexed capture descriptor')
                rel=row.get('capture')
                binding=row.get('binding_id')
                if (not isinstance(rel,str) or not rel.endswith('.capture.json')
                        or PurePath(rel).name != rel or '/' in rel or '\\' in rel):
                    raise ValueError('Capture path must be a direct .capture.json file')
                if not isinstance(binding,str) or not binding or len(binding) > 128:
                    raise ValueError('Missing bounded source Action binding identifier')
                if rel in seen_paths or binding in seen_bindings:
                    raise ValueError('Duplicate Action or capture filename')
                seen_paths.add(rel); seen_bindings.add(binding)
                path=(root/rel).resolve()
                if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
                    raise ValueError('Capture path escapes extraction or is missing')
                capture=load_capture(path)
                if capture.profile.fingerprint != row.get('profile_sha256'):
                    raise ValueError('Extracted capture has another rig profile identity')
                recorded = capture.provenance.get('source_file', {})
                if not isinstance(recorded,dict) or recorded.get('sha256') != source['sha256']:
                    raise ValueError('Capture original source SHA-256 differs from Blender index')
                folder=stage/(slug(binding,64)+'_'+capture.profile.fingerprint[:10])
                result=analyse_source_capture(capture,folder,
                    original_source_sha256=source['sha256'],
                    max_previews=max_previews, target_bpm=target_bpm,
                    full_motion_confidence_threshold=min_full_confidence,
                    verify_native=verify_native)
                output=folder.relative_to(stage).as_posix()
                item=dict(identity, relative_output=output,
                          source_capture_sha256=result['source_capture_sha256'],
                          original_source_sha256=source['sha256'],
                          profile_sha256=capture.profile.fingerprint,
                          confidence_percent=result['full_motion_fit']['confidence_percent'],
                          selected_bpm=result['full_motion_fit']['selected_bpm'],
                          full_motion_count=result['full_motion_count'],
                          loopable_clip_count=result['loopable_clip_count'])
                report['actions'].append(item)
                for full in result['full_motion_clips']:
                    report['full_motion_shortlist'].append(dict(item,
                        filename=full['filename'], confidence_percent=full['confidence_percent']))
                for loop in result['loopable_clips']:
                    report['loopable_shortlist'].append(dict(item,
                        filename=loop['filename'], score=loop['score'],
                        beats=loop['source_beats']))
            except (ValueError, KeyError, RuntimeError, OSError) as exc:
                report['failures'].append(dict(identity, error=str(exc)))
        report['analysed_action_count']=len(report['actions'])
        report['failed_action_count']=len(report['failures'])
        report['truncated']=len(inputs)>max_actions
        report['full_motion_count']=len(report['full_motion_shortlist'])
        report['loopable_clip_count']=len(report['loopable_shortlist'])
        report['full_motion_shortlist'].sort(key=lambda x:-x['confidence_percent'])
        report['loopable_shortlist'].sort(key=lambda x:-x['score'])
        (stage/'index.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        if output_root.exists() or output_root.is_symlink():
            raise FileExistsError('Output destination appeared during analysis')
        stage.rename(output_root)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index',type=Path,required=True,help='Blender extraction index.json')
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--max-previews',type=int,default=4)
    parser.add_argument('--min-full-confidence',type=float,default=.70)
    parser.add_argument('--target-bpm',type=float)
    parser.add_argument('--max-actions',type=int,default=100)
    parser.add_argument('--verify-native',action='store_true')
    a=parser.parse_args(argv)
    try:
        d=analyse_batch(a.index,a.output_root,max_previews=a.max_previews,
              min_full_confidence=a.min_full_confidence,target_bpm=a.target_bpm,
              max_actions=a.max_actions,verify_native=a.verify_native)
    except (ValueError,RuntimeError,OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(dict(actions=d['analysed_action_count'],
        full_motions=d['full_motion_count'], loops=d['loopable_clip_count'],
        failures=d['failed_action_count'],truncated=d['truncated']),indent=2))
    return 2 if d['failures'] or d['truncated'] else 0


if __name__=='__main__':
    raise SystemExit(main())
