#!/usr/bin/env python3
"""CI/offline StemLab master loop audition against SOURCE-FIRST rig preview recordings.

No song, model, motion source or network dependency is downloaded by this script.
It reads original bundled masters locally, uses StemLab's loop analyser, and
builds an *audio-free* self-contained HTML review viewer. Source/derivative
rights are not inferred from the software licence.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
import hashlib
import json
import math
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VIEWER = Path(__file__).with_name('song_loop_viewer') / 'template.html'
SONGS = (
    ('arcadians', 'examples/arcadians/Arcadians - 320kbps.mp3', 'examples/arcadians/reference.json'),
    ('the-truth-is-a-virus', 'examples/the-truth-is-a-virus/master.mp3', 'examples/the-truth-is-a-virus/analysis.json'),
    ('star-lights-glow-mystery-liquid-kick', 'examples/star-lights-glow-mystery-liquid-kick/master.mp3',
     'examples/star-lights-glow-mystery-liquid-kick/evidence.json'),
)
MAX_VISUAL_MOTIONS = 8
METRICAL_FIT_FLOOR = .45
MATCH_MIN_RATIO, MATCH_MAX_RATIO = .45, 2.10


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _reference(root, song_id, audio_path, reference_path):
    info = json.loads(reference_path.read_text(encoding='utf-8-sig'))
    if song_id == 'arcadians':
        expected = info['example_audio']['sha256']
        tempo = info['bpm']
        title, artist = info['title'], info['artist']
    elif song_id == 'the-truth-is-a-virus':
        expected = info['source']['sha256']
        canonical = json.loads((root/'examples/the-truth-is-a-virus/canonical.json').read_text())
        title, artist, tempo = canonical['title'], canonical['artist'], None
    else:
        expected = info['listening_and_analysis_derivative']['sha256']
        canonical = json.loads((root/'examples/star-lights-glow-mystery-liquid-kick/canonical.json').read_text())
        title, artist, tempo = canonical['title'], canonical['artist'], None
    found = _hash(audio_path)
    if found != expected:
        raise ValueError(f'{song_id}: bundled master SHA-256 mismatch ({found} != {expected})')
    return dict(id=song_id, title=title, artist=artist, source_sha256=found,
                expected_filename=audio_path.name, size_bytes=audio_path.stat().st_size,
                canonical_bpm=tempo)


def _validate_grid(beats, downbeats, duration):
    """Do not repair or silently substitute downbeat positions."""
    beat = [float(t) for t in beats]
    down = [float(t) for t in downbeats]
    for seq, label in ((beat, 'beats'), (down, 'downbeats')):
        if any(not math.isfinite(t) or not 0 <= t <= duration + .02 for t in seq):
            raise ValueError(f'{label}: out of duration or non-finite')
        if any(b <= a for a, b in zip(seq, seq[1:])):
            raise ValueError(f'{label}: not strictly increasing')
    if len(beat) < 8 or len(down) < 2:
        raise ValueError('Need at least 8 beats and 2 downbeats for loop suggestions')
    for t in down:
        i = bisect_left(beat, t)
        if min((abs(beat[k]-t) for k in (i-1,i) if 0 <= k < len(beat)), default=1) > .03:
            raise ValueError('Downbeat must be an observed beat event')
    return beat, down


def _beat_grid(root, song, audio_path, duration):
    """Reuse saved StemLab evidence when present; otherwise run offline baseline.

    The fallback has a *hypothesised* 4-pulse phase. It is never a verified
    meter/downbeat and is not allowed to imply an approved audio edit.
    """
    if song['id'] == 'the-truth-is-a-virus':
        stored = json.loads((root/'examples/the-truth-is-a-virus/beats/consensus.json').read_text())
        beats, downs = _validate_grid(stored['beats'], stored['downbeats'], duration)
        return dict(beats=beats, downbeats=downs, model='stemlab_consensus_saved',
                    bpm=round(60 / sorted((b-a for a,b in zip(beats,beats[1:])))[len(beats)//2-1], 4),
                    beat_status='detected_consensus_not_artist_confirmed',
                    downbeat_status='detector_consensus_not_artist_confirmed',
                    meter_status='detector_estimate_not_approved')
    # First-party StemLab has no saved complete beat/downbeat grid for these two.
    # Run a traditional local estimation baseline, without downloading models.
    import librosa
    import numpy as np
    y, sr = librosa.load(str(audio_path), sr=11025, mono=True)
    hop = 256
    envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    _tempo, frames = librosa.beat.beat_track(onset_envelope=envelope, sr=sr,
                                           hop_length=hop, trim=False,
                                           start_bpm=float(song['canonical_bpm'] or 120))
    beat_times = librosa.frames_to_time(frames, sr=sr, hop_length=hop).astype(float).tolist()
    if len(beat_times) < 8:
        raise ValueError('Traditional beat tracker could not identify eight pulses')
    # Choose the most accent-supported quarter-note phase, but do NOT claim 4/4
    # meter or musical beat 1 was confirmed by any downbeat model.
    strengths = np.interp(np.asarray(beat_times),
                          librosa.frames_to_time(np.arange(len(envelope)), sr=sr, hop_length=hop),
                          envelope)
    phases = [float(np.mean(strengths[i::4])) for i in range(4)]
    phase = max(range(4), key=lambda i: phases[i])
    downbeats = beat_times[phase::4]
    beats, downbeats = _validate_grid(beat_times, downbeats, duration)
    measured = 60 / float(np.median(np.diff(beats)))
    return dict(beats=beats, downbeats=downbeats, model='librosa_baseline_motion_sync',
                bpm=round(measured, 4),
                beat_status='algorithmically_estimated_not_confirmed',
                downbeat_status='accent_based_four_pulse_phase_hypothesis',
                meter_status='four_pulse_preview_hypothesis_not_verified',
                artist_bpm_hint=song['canonical_bpm'],
                tempo_ambiguity=('Detected tempo differs from artist reference (possible metrical subdivision)'
                                 if song['canonical_bpm'] is not None and
                                 abs(math.log2(measured/song['canonical_bpm'])) > .12 else None))


def _waveform(audio_path, count=1200):
    """Bounded visual peak envelope; no audio bytes appear in published artifacts."""
    import soundfile as sf
    import numpy as np
    with sf.SoundFile(audio_path) as f:
        duration, frames = len(f)/f.samplerate, len(f)
        # Reading small sequential blocks is bounded independently of full length.
        group = max(1, math.ceil(frames / count))
        peaks = []
        while True:
            block = f.read(group, dtype='float32', always_2d=True)
            if not len(block):
                break
            peaks.append(round(float(np.max(np.abs(block))), 4))
        return dict(duration_seconds=duration, peaks=peaks, sample_rate=f.samplerate,
                    channels=f.channels, source_frames=frames)


def _motion_to_frames(path, max_frames=240):
    """Bake bounded source-joint diagnostics with the shared offline evaluator.

    Exact typed Recording/profile validation and portable carrier semantics are
    required. Unsupported control rigs retain a clearly labelled channel graph;
    invalid portable geometry is rejected rather than silently defaulted.
    """
    import numpy as np
    from dancerudiments_authoring.motion import load_rig_motion
    from dancerudiments_authoring.motion_import import RigCapture
    from dancerudiments_authoring.world_motion import evaluate_world_motion, UnsupportedWorldMotion
    if type(max_frames) is not int or max_frames < 1:
        raise ValueError('Preview frame budget must be a positive integer')
    motion = load_rig_motion(path)
    profile, recording = motion.profile, motion.recording
    rows = recording.samples
    steps = np.unique(np.linspace(0,len(rows)-1,min(max_frames,len(rows)),dtype=int)).tolist()
    capture = RigCapture(profile,
        tuple(recording.clock.time_seconds(k) for k in steps),
        tuple(profile.decode(rows[k]) for k in steps))
    unavailable = None
    try:
        world = evaluate_world_motion(capture)
    except UnsupportedWorldMotion as error:
        unavailable = str(error)
        world = None
    if world is not None:
        if len(world.bone_names) > 120:
            raise ValueError('Portable wireframe exceeds its 120-bone preview budget')
        points = np.round(world.positions,4).tolist()
        names = list(world.bone_names)
        edges = [[parent,i] for i,parent in enumerate(world.parents) if parent >= 0]
    else:
        # Unknown constraint/control semantics get no fabricated bone poses.
        names = []
        indices=[i for i,c in enumerate(profile.channels) if c.interpolation!='step'][:12]
        points=[[[round(float(rows[k][j]),4),i/3,0] for i,j in enumerate(indices)] for k in steps]
        edges=[[i,i+1] for i in range(max(0,len(indices)-1))]
    return dict(name=recording.name,profile_sha256=profile.fingerprint,
                frame_count=len(points),bones=names,
                links=edges,xyz=points,
                frame_relative_pips=[int(k) for k in steps],
                beats=len(rows)/64,raw_sample_count=len(rows),
                skeleton_kind='source_portable_fk' if world is not None else 'channel_graph_only',
                world_motion_unavailable_reason=unavailable)


def _motion_library(job_root, *, max_motions=MAX_VISUAL_MOTIONS):
    """Read a completed source-first job, retaining its genuine BPM alternatives.

    An inferred 120 BPM double-time hypothesis is not the same as proving that
    the original source was danced to 120 BPM. Preserve its diagnostic support,
    and allow it only as an explicitly labelled *preview* interpretation.
    """
    document=json.loads((job_root/'job.json').read_text())
    if document.get('format') != 'dancerudiments.source-motion-loop-job':
        raise ValueError('Expected a complete source-first motion loop job')
    full=document.get('full_motion_clips', [])[:1]
    untouched=document.get('loopable_clips',document.get('previews', []))
    corrected=document.get('repaired_loop_clips', [])
    loops=[]
    for index in range(max(len(untouched),len(corrected))):
        if index < len(untouched): loops.append(untouched[index])
        if index < len(corrected): loops.append(corrected[index])
    loops=loops[:max_motions-len(full)]
    candidates=[('full_length',entry) for entry in full]+[('loopable',entry) for entry in loops]
    whole_fit=document.get('full_motion_fit') or {}
    hypotheses=whole_fit.get('tempo_hypotheses') or []
    motions=[]
    for index,(kind,entry) in enumerate(candidates):
        relative=Path(entry['filename'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe preview file path')
        path=(job_root/relative).resolve()
        if not path.is_relative_to(job_root.resolve()) or _hash(path)!=entry['recording_sha256']:
            raise ValueError('Motion preview hash differs from completed job')
        data=_motion_to_frames(path)
        if (document.get('profile_sha256') and
                data['profile_sha256'] != document['profile_sha256']):
            raise ValueError('Completed motion job and exact rig profile fingerprint disagree')
        bpm=entry['bpm_estimated'] if kind=='full_length' else entry['source_bpm_estimated']
        confidence=entry.get('confidence',entry.get('score'))
        data.update(id=f'motion-{index+1}',motion_kind=kind,
                    loopable=(kind=='loopable'),
                    source_start_pip=entry.get('start_pip',0),
                    estimated_bpm=bpm,score=confidence,
                    full_motion_confidence=confidence if kind=='full_length' else None,
                    confidence_interpretation='uncalibrated_kinematic_fit_not_probability',
                    source_tempo_hypotheses=hypotheses,
                    original_source_sha256=document.get('source_original_sha256'),
                    source_capture_sha256=entry.get('corrected_capture_file_sha256',
                                                     document.get('source_capture_sha256')),
                    repaired=bool(entry.get('repaired',False)),
                    numerical_repeat_seam_verified=bool(entry.get('numerical_repeat_seam_verified',False)),
                    rig_type_uri=document.get('type_uri'),
                    requires_review=True,
                    source_start_seconds=entry.get('source_start_seconds',
                                                  entry.get('sampled_bounds_seconds',[0])[0]),
                    source_clock_start_seconds=(0. if entry.get('repaired') else
                        entry.get('source_start_seconds',entry.get('sampled_bounds_seconds',[0])[0])),
                    source_end_seconds=entry.get('source_end_seconds',
                                                entry.get('sampled_bounds_seconds',[0,0])[-1]),
                    audio_beat_alignment_verified=False)
        motions.append(data)
    return motions


def _metrical_variants(motion):
    """Derive only *evidenced* half/double interpretations of original source time.

    Never invent a music BPM from a song, or alter the stored 64-pip Recording.
    The variant changes the number of musical beats *represented* by the entire
    motion, not its sampled length; the preview then applies playback-speed
    matching to the chosen song grid. The weak hypotheses remain review-only.
    """
    bpm=motion.get('estimated_bpm')
    if type(bpm) not in (int,float) or not math.isfinite(bpm) or not 30 <= bpm <= 300:
        return []
    variants=[dict(factor=1, bpm=float(bpm), label='source_primary',
                   evidence_score=motion.get('score'), needs_phase_review=True)]
    for item in motion.get('source_tempo_hypotheses') or []:
        if not isinstance(item, dict):
            continue
        alternative=item.get('bpm')
        fit=item.get('fit_score')
        if type(alternative) not in (int,float) or not math.isfinite(alternative):
            continue
        if type(fit) not in (int,float) or not math.isfinite(fit) or fit < METRICAL_FIT_FLOOR:
            continue
        if item.get('notes') and any(n not in ('insufficient_independent_control_support',)
                                      for n in item['notes']):
            continue
        ratio=alternative/bpm
        factor=2 if abs(ratio-2)<.035 else .5 if abs(ratio-.5)<.009 else None
        relation={2:'double_time', .5:'half_time'}.get(factor)
        if (factor is None or item.get('metrical_relation_to_top')!=relation or
                type(item.get('supporting_control_groups')) is not int or
                item['supporting_control_groups'] < 1):
            continue
        variants.append(dict(factor=factor,bpm=float(alternative),
                             label='stemlab_'+relation, evidence_score=float(fit),
                             supporting_control_groups=item['supporting_control_groups'],
                             needs_phase_review=True))
    return variants


def _observed_beat_interval(song, audio, sr):
    """Use actual indexed beat events, not the assumption 'bars × four beats'.

    A track may have an uncertain downbeat/meter, but the events chosen by
    StemLab to anchor the cut are already in its observed/estimated beat series.
    If either boundary is absent or cannot be mapped, do not fabricate beats.
    """
    beats=song.get('grid',{}).get('beats',())
    a,b=audio.get('grid_start_sample'),audio.get('grid_end_sample')
    if (not isinstance(beats,list) or type(sr) is not int or sr <= 0 or
            type(a) is not int or type(b) is not int or not 0 <= a < b):
        return None
    def index(sample):
        t=sample/sr
        i=bisect_left(beats,t)
        nearest=min((k for k in (i-1,i) if 0<=k<len(beats)),
                    key=lambda k:abs(beats[k]-t),default=None)
        if nearest is None or abs(beats[nearest]-t)>.035:
            return None
        return nearest
    first,last=index(a),index(b)
    if first is None or last is None or last <= first:
        return None
    return first,last,last-first


def _rank_matches(song, motions, audio_report, max_pairs=18):
    """Rank *unapproved* source-motion previews against observed song beat spans.

    Each source-derived metrical interpretation represents a whole motion or a
    whole loop period: a half/double-time label cannot silently crop, stretch
    or repeat a non-looping complete Action. Ranking diversifies candidate kind
    and audio region so alternative motions are visible for human audition.
    """
    if type(max_pairs) is not int or not 1<=max_pairs<=64:
        raise ValueError('max_pairs must be 1..64')
    candidates=audio_report.get('loops',[])+audio_report.get('exploratory_candidates',[])
    proposed=[]
    for audio in candidates[:64]:
        if not isinstance(audio,dict):continue
        indexed=_observed_beat_interval(song,audio,audio_report.get('sample_rate'))
        if indexed is None: continue
        first,last,count=indexed
        song_beats=song['grid']['beats']
        observed_duration=song_beats[last]-song_beats[first]
        if observed_duration <= 0:continue
        local_bpm=60*count/observed_duration
        # Individual songs may have a non-uniform beat envelope. Local tempo
        # is only an average across the selected complete-bar interval; the
        # browser still uses observed beat timestamps for motion phase.
        intervals=[b-a for a,b in zip(song_beats[first:last],song_beats[first+1:last+1])]
        variability=(max(intervals)-min(intervals))/max(1e-9,sum(intervals)/len(intervals))
        for motion in motions:
            original=motion.get('beats')
            if type(original) not in (int,float) or not math.isfinite(original) or original<=0:
                continue
            kind=motion.get('motion_kind','loopable')
            if kind not in ('full_length','loopable'):continue
            for variant in _metrical_variants(motion):
                effective=original*variant['factor']
                # A motion measured in 64-pip beats may have a fractional end
                # for a full Action, but the audio pair must still use a whole
                # number of interpreted beats without truncating the source.
                if abs(effective-round(effective))>.10 or effective<1:
                    continue
                ticks=int(round(effective))
                if kind=='full_length':
                    if ticks!=count:continue
                    repeats=1
                else:
                    if count%ticks:continue
                    repeats=count//ticks
                ratio=local_bpm/variant['bpm']
                if not MATCH_MIN_RATIO<=ratio<=MATCH_MAX_RATIO:continue
                raw_confidence=motion.get('score',0)
                if type(raw_confidence) not in (float,int) or not math.isfinite(raw_confidence):continue
                confidence=float(raw_confidence)
                if not 0<=confidence<=1:continue
                alternative=variant['factor']!=1
                # Ranking remains a heuristic. A high whole-Action fit at 60
                # BPM does NOT turn weaker 120-BPM movement evidence into 84%.
                motion_fit=confidence
                if alternative:
                    motion_fit=min(confidence,variant['evidence_score'])
                quality=motion_fit/(1+abs(math.log2(ratio))*.25)
                if alternative:quality*=.97
                penalty=max(0.,float(audio.get('exploratory_ranking_cost',
                                               audio.get('ranking_cost',0.))))
                rank=quality/(1+penalty*.10)
                failed=audio.get('failed_gates',[])
                if 'waveform_join' in failed: rank*=.88
                proposed.append(dict(id=f'{audio["id"]}:{motion["id"]}:{variant["factor"]}',
                    motion_id=motion['id'],loop_id=audio['id'],
                    song_start_seconds=round(audio['start_seconds'],6),
                    song_end_seconds=round(audio['end_seconds'],6),
                    start_beat_index=first,end_beat_index=last,
                    song_beats=count,original_motion_beats=round(original,4),
                    motion_beats=ticks, motion_repeats=repeats,motion_kind=kind,
                    metrical_factor=variant['factor'],
                    metrical_interpretation=variant['label'],
                    interpreted_motion_bpm=round(variant['bpm'],4),
                    metrical_evidence_score=variant.get('evidence_score'),
                    full_motion_confidence=motion.get('full_motion_confidence'),
                    playback_tempo_ratio=round(ratio,4),
                    local_song_bpm=round(local_bpm,4),
                    local_beat_interval_variation=round(variability,4),
                    local_tempo_warp_preview=variability>.08,
                    estimated_score=round(rank,5),
                    beat_count_source='indexed_stemlab_audio_beat_grid',
                    audio_source='stemlab_exploratory' if audio.get('status') else 'stemlab_strict',
                    audio_failed_gates=failed,requires_review=True,
                    beat_alignment_confirmed=False,loop_seam_approved=False,
                    metrical_phase_verified=False))
    # Reserve room for both entire Actions and local loops, and avoid flooding
    # one selection with dozens of nearly identical alternatives.
    proposed.sort(key=lambda x:(-x['estimated_score'],x['song_start_seconds'],x['motion_id']))
    kinds={p['motion_kind'] for p in proposed}
    per_kind=(max_pairs+1)//2 if len(kinds)>1 else max_pairs
    selection=[]; selected=set(); motion_counts={}; audio_counts={}; kind_counts={}
    def add(item, *,kind_limit):
        if len(selection)>=max_pairs or item['id'] in selected:return False
        kind=item['motion_kind']
        if kind_counts.get(kind,0)>=kind_limit:return False
        if audio_counts.get(item['loop_id'],0)>=3:return False
        if motion_counts.get(item['motion_id'],0)>=max(3,max_pairs//2):return False
        selection.append(item);selected.add(item['id'])
        kind_counts[kind]=kind_counts.get(kind,0)+1
        audio_counts[item['loop_id']]=audio_counts.get(item['loop_id'],0)+1
        motion_counts[item['motion_id']]=motion_counts.get(item['motion_id'],0)+1
        return True
    for item in proposed:add(item,kind_limit=per_kind)
    for item in proposed:add(item,kind_limit=max_pairs)
    selection.sort(key=lambda x:(x['motion_kind']!='full_length',-x['estimated_score'],x['song_start_seconds']))
    return selection[:max_pairs]


def _alignment_reviews(paths, motions, songs, jobs):
    """Bind optional timing reports to actual source bytes and displayed media."""
    from stemlab.analysis.motion_alignment import (
        read_document, document_hash, create_alignment_revision)
    if len(paths)>16:
        raise ValueError('Select at most sixteen explicit timing reports')
    motion_hashes={m.get('source_capture_sha256') for m in motions}
    song_hashes={s['source_sha256'] for s in songs}
    known_captures={}
    for job in jobs:
        capture=job/'source.capture.json'
        if capture.is_file(): known_captures[_hash(capture)]=capture
        for capture in (job/'repaired-loops').glob('*.capture.json'):
            if capture.is_file() and not capture.is_symlink(): known_captures[_hash(capture)]=capture
    reviews=[]
    for path in paths:
        report,digest=read_document(path)
        if report.get('format')!='stemlab.motion-alignment.v1' or report.get('source_bytes_verified') is not True:
            raise ValueError('Select a source-verified StemLab motion alignment report')
        source=report.get('motion_source',{}).get('sha256')
        if source not in motion_hashes or source not in known_captures:
            raise ValueError('Timing report motion differs from the displayed source capture')
        if report.get('audio_source',{}).get('sha256') not in song_hashes:
            raise ValueError('Timing report audio differs from the bundled master')
        for candidate in report.get('candidates',[]):
            # Validate candidate mapping without accepting or writing a review.
            create_alignment_revision(report,report_sha256=digest,
                candidate_id=candidate['candidate_id'],reviewer='preview-validation',decision='needs_review')
        reviews.append(dict(report=report,report_sha256=digest,
                            report_content_sha256=document_hash(report)))
    return reviews


def build(stemlab_root, motion_job, output, *, fail_on_song_error=False, alignment_reports=()):
    import soundfile as sf
    from stemlab.analysis.loops import analyze_loops, LoopConfig
    from stemlab.types import BeatResult
    root=Path(stemlab_root).resolve()
    jobs=[Path(job).resolve() for job in (motion_job if isinstance(motion_job,(tuple,list)) else [motion_job])]
    if not 1<=len(jobs)<=8 or len(set(jobs))!=len(jobs):
        raise ValueError('Select 1..8 distinct source-first motion job directories')
    output=Path(output).resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Choose a new output directory: {output}')
    if not (root/'src/stemlab/analysis/loops.py').is_file():
        raise ValueError('StemLab source checkout with loop analyser required')
    # Refuse random other StemLab import or a vendored audio loop scorer.
    import inspect
    if Path(inspect.getfile(analyze_loops)).resolve() != (root/'src/stemlab/analysis/loops.py').resolve():
        raise ValueError('Imported StemLab analyser is not the requested source checkout')
    motions=[];seen_digests=set();job_hashes=[]
    for job in jobs:
        job_hashes.append(_hash(job/'job.json'))
        for motion in _motion_library(job):
            signature=(motion.get('profile_sha256'),motion.get('original_source_sha256'),
                       motion.get('source_start_pip'),motion.get('raw_sample_count'),motion['name'])
            if signature in seen_digests:continue
            seen_digests.add(signature)
            motion['id']=f'motion-{len(motions)+1}'
            motions.append(motion)
            if len(motions)>=MAX_VISUAL_MOTIONS:break
        if len(motions)>=MAX_VISUAL_MOTIONS:break
    if not motions:
        raise ValueError('No native motion previews: source-first job must succeed first')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.song-loop-preview-',dir=output.parent) as temp:
        stage=Path(temp)/'site';stage.mkdir()
        reports=stage/'reports';reports.mkdir()
        songs=[]; errors=[]
        for song_id, audio_rel, reference_rel in SONGS:
            audio=root/audio_rel;ref=root/reference_rel
            if not audio.is_file():
                raise FileNotFoundError(f'Bundled song master missing: {audio_rel}')
            entry=_reference(root,song_id,audio,ref)
            try:
                info=sf.info(str(audio))
                grid=_beat_grid(root,entry,audio,info.duration)
                wave=_waveform(audio)
                result_dir=reports/song_id
                result=analyze_loops(audio,result_dir,song_map=None,
                     beat_results=[BeatResult(model=grid['model'],beats=grid['beats'],
                           downbeats=grid['downbeats'],tempo_bpm=grid['bpm'])],
                     stems=[],export_audio=False,
                     config=LoopConfig(mode='exploratory',search_scope='whole_song',
                                       exploratory_algorithm='spectral_context',max_bars=8,
                                       max_seconds=30,loops_per_section=24))
                if result['source_sha256']!=entry['source_sha256']:
                    raise ValueError('StemLab report lost the exact MP3 source hash')
                entry.update(grid=grid, waveform=wave,
                             exploratory_loops=result.get('exploratory_candidates',[])[:24],
                             accepted_loops=result.get('loops',[])[:24],
                             audio_loop_report=f'reports/{song_id}/loops.json',
                             audio_loop_status='exploratory_requires_listening',
                             audio_loop_counts=dict(exploratory=result['exploratory_count'],
                                                    accepted=result['loop_count']),
                             pairs=[])
                entry['pairs']=_rank_matches(entry,motions,result)
                entry['status']='candidate_previews' if entry['pairs'] else 'no_compatible_preview'
            except Exception as exc:
                errors.append(dict(song_id=song_id,error=str(exc)))
                entry.update(status='analysis_failed',error=str(exc),grid=None,
                             pairs=[],waveform=None,accepted_loops=[],exploratory_loops=[])
            songs.append(entry)
        reviews=_alignment_reviews(alignment_reports,motions,songs,jobs) if alignment_reports else []
        data=dict(format='dancerudiments.song-motion-loop-preview',schema_version=1,
                  stemlab_source_checkout=str(root/'src/stemlab/analysis/loops.py'),
                  source_motion_job_sha256=job_hashes[0],
                  source_motion_job_sha256s=job_hashes,
                  media_policy='No MP3/WAV/cover/audio samples copied to the artifact; local exact-hash audio selection only.',
                  beat_status='model_or_detector_estimate_not_approved',
                  audio_loop_status='StemLab exploratory candidates; not verified seamless or vocal-clear',
                  motion_model_status='source-rig preview; final Kandi Boom skin is reviewed in the mesh gallery',
                  alignment_reviews=reviews,
                  songs=songs,motions=motions,errors=errors)
        raw=json.dumps(data,ensure_ascii=True,separators=(',',':'),allow_nan=False)
        (stage/'report.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
        # Embed data: local file:// pages cannot fetch arbitrary JSON under CORS.
        template=VIEWER.read_text(encoding='utf-8')
        timing_script=(VIEWER.parent/'alignment-review.js').read_text(encoding='utf-8')
        html=(template.replace('%%PREVIEW_DATA%%',raw.replace('<','\\u003c'))
              .replace('%%TIMING_REVIEW_SCRIPT%%',timing_script)
              .replace('%%BUILD_SOURCE%%','CI source-first loop analysis'))
        if '%%PREVIEW_DATA%%' in html or '%%TIMING_REVIEW_SCRIPT%%' in html:
            raise AssertionError('Missing report injection')
        (stage/'index.html').write_text(html,encoding='utf-8')
        stage.rename(output)
    if fail_on_song_error and errors:
        raise RuntimeError(f'{len(errors)} song(s) failed analysis; inspect {output / "report.json"}')
    return data


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stemlab-root',type=Path,required=True)
    parser.add_argument('--motion-job',type=Path,required=True,action='append',
                        help='Completed source-first job; repeat for additional local rig motions (max 8)')
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--require-all-songs',action='store_true')
    parser.add_argument('--alignment-report',type=Path,action='append',default=[],
                        help='Source-verified StemLab audio/motion timing report for phase review')
    opts=parser.parse_args(argv)
    try:
        result=build(opts.stemlab_root,opts.motion_job,opts.output_dir,
                     fail_on_song_error=opts.require_all_songs,alignment_reports=opts.alignment_report)
    except (ValueError,RuntimeError,OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output':str(opts.output_dir),'songs':[{k:v.get(k) for k in
         ('id','status','audio_loop_counts')}|{'pairs':len(v.get('pairs',[]))}
         for v in result['songs']],'errors':result['errors']},indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
