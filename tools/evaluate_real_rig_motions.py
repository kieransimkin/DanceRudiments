#!/usr/bin/env python3
"""Real-CMU evidence-only benchmark for source-time tempo and loop discovery.

Uses the repository's *existing pinned* salsa/ballet mesh-demo recipes, verified
original bytes, explicit source FPS correction and exact source rig profile.
It does not infer rights, add new source URLs, or upload recorded motion samples.
Outputs ONLY diagnostic summaries; intermediate captures/previews remain ignored
project-local data, never included in CI artifacts or released packages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
sys.path.insert(0,str(ROOT/'tools'))


def summarize_action(recipe, scene, clip, report):
    """Reduce an analysed original Action to provenance + bounded diagnostics."""
    source=scene['source']
    identity=report.get('source_original_sha256')
    if identity != source['sha256'] or identity != clip.source_sha256:
        raise ValueError('Real-motion report changed original pinned source identity')
    if report.get('profile_sha256') != clip.profile.fingerprint:
        raise ValueError('Real-motion report changed numbered rig/profile identity')
    fit=report.get('full_motion_fit') or {}
    accepted=report.get('full_motion_count',0)
    if accepted not in (0,1) or (accepted and fit.get('confidence',0) < fit.get('threshold',.70)):
        raise ValueError('Invalid confidence gating of complete Action')
    reason=fit.get('reasons',[])
    if not isinstance(reason,list):raise ValueError('Unexpected motion report reasons')
    return dict(
        scene_id=scene['id'],original_motion_id=source['id'],
        source_title=source['title'], source_sha256=identity,
        source_url=source['source_url'], source_mirror_commit=recipe['mirror_commit'],
        source_license_id=recipe['license']['id'],
        profile_sha256=clip.profile.fingerprint, rig_type_uri=clip.profile.type_uri,
        source_frames=clip.frame_count, source_duration_seconds=round(clip.duration_seconds,6),
        effective_source_fps=round(clip.source_fps,6),
        source_timing_kind='physical_capture_seconds_not_verified_musical_bpm',
        confidence_method=fit.get('method'),
        confidence_interpretation=fit.get('confidence_interpretation'),
        bpm_estimated=fit.get('selected_bpm'),
        bpm_confidence_percent=fit.get('confidence_percent'),
        alternatives=[dict(bpm=x['bpm'],fit_score=x['fit_score'],
                           relation=x.get('metrical_relation_to_top'),notes=x.get('notes',[]))
                      for x in fit.get('tempo_hypotheses',[])[:5]],
        full_action_shortlisted=accepted==1,
        full_action_rejection_reasons=reason,
        number_of_source_loop_candidates=report.get('unconverted_candidate_count',0)
                       +report.get('loopable_clip_count',0),
        preview_loop_count=report.get('loopable_clip_count',0),
        loop_seam_approved=False,
        beat_alignment_confirmed=False,
        measured_target_mesh_deformation=False,
    )


def evaluate(output_dir,cache_root,*,download=False,required_complete=True,
             min_confidence=.70,max_previews=2):
    from dancerudiments_authoring.source_loop_analysis import (
        source_capture_from_bvh,analyse_source_capture)
    from build_mesh_demo_assets import load_sources,_prepare_clip
    from acquire_cmu_dance import _ensure_file
    from import_motion_collection import preflight
    output_dir=Path(output_dir).resolve();cache_root=Path(cache_root).resolve()
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError('Real-motion diagnostic output must be a new directory')
    if cache_root == output_dir or output_dir.is_relative_to(cache_root):
        raise ValueError('Source download cache cannot contain diagnostic output')
    recipe=load_sources()
    preflight(output_dir.parent)
    preflight(cache_root/'raw')
    rows=[]; errors=[]
    for scene in recipe['scenes']:
        original=scene['source']
        try:
            _ensure_file(cache_root,original,download=download)
            clip=_prepare_clip(recipe,scene,cache_root)  # original, pinned FPS/profile
            captured=source_capture_from_bvh(
                clip,calibration_frames=original['calibration_frame_count'])
            jobdir=output_dir.parent / ('.'+output_dir.name+'-private-'+scene['id'])
            if jobdir.exists():
                raise FileExistsError(f'Private CI motion analysis exists already: {jobdir}')
            report=analyse_source_capture(captured,jobdir,
                original_source_sha256=clip.source_sha256,
                min_bpm=55,max_bpm=220,max_previews=max_previews,
                verify_native=True,full_motion_confidence_threshold=min_confidence)
            rows.append(summarize_action(recipe,scene,clip,report))
        except (OSError,RuntimeError,ValueError) as exc:
            errors.append(dict(scene_id=scene['id'],source_sha256=original['sha256'],
                               error_type=type(exc).__name__,error=str(exc)[:500]))
    doc=dict(format='dancerudiments.real-rig-analysis-benchmark',schema_version=1,
             media_policy='summary_only; no original/converted rig recordings or source media',
             source_recipe='tools/mesh_demo_sources.json',source_license_id=recipe['license']['id'],
             benchmark_scene_count=len(recipe['scenes']),
             analysed_scene_count=len(rows),failed_scene_count=len(errors),
             source_time_analysis=True,source_tempo_is_musically_unverified=True,
             full_action_confidence_threshold=min_confidence,
             full_action_shortlist_count=sum(r['full_action_shortlisted'] for r in rows),
             total_loop_previews=sum(r['preview_loop_count'] for r in rows),
             scenes=rows, failures=errors)
    output_dir.mkdir(parents=True)
    (output_dir/'summary.json').write_text(json.dumps(doc,indent=2,allow_nan=False)+'\n')
    if required_complete and (errors or len(rows)!=len(recipe['scenes'])):
        raise RuntimeError('Real-motion analysis incomplete; inspect summary.json (no media uploaded)')
    return doc


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--cache-root',type=Path,default=ROOT/'.cache/real-motion-sources')
    parser.add_argument('--download',action='store_true',
                        help='Explicitly download only the two source files approved by pinned mesh demo recipe')
    parser.add_argument('--min-full-confidence',type=float,default=.70)
    parser.add_argument('--max-previews',type=int,default=2)
    args=parser.parse_args(argv)
    report=evaluate(args.output_dir,args.cache_root,download=args.download,
                    min_confidence=args.min_full_confidence,max_previews=args.max_previews)
    print(json.dumps({k:report[k] for k in (
        'analysed_scene_count','failed_scene_count',
        'full_action_shortlist_count','total_loop_previews')},indent=2))


if __name__=='__main__':main()
