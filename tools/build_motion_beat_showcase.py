#!/usr/bin/env python3
"""Build CI-only animated rig-movement previews from pinned CMU source Actions.

Provenance is verified by acquire_cmu_dance and the existing native
DanceRudiments/StemLab source-first analyser. Output is *visual review evidence*,
never a canonical music tempo, approved seam or a new motion data distribution.
No source frames or compiled motion documents are copied into the showcase.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
sys.path.insert(0, str(ROOT / 'tools'))

FORMAT = 'dancerudiments.ci-motion-beat-showcase'
DEFAULT_IDS = ('103_03', '106_12', '143_34', '143_35', '05_11', '90_28',
               '90_30', '55_01')
MAX_INPUTS = 10
MAX_FRAMES = 64
MIN_LOOP_SECONDS = 0.9
MAX_LOOP_SECONDS = 8.0
MIN_ACTIVITY_RATIO = 0.35
MIN_ABSOLUTE_ANGULAR_ACTIVITY = 0.0005  # radians/frame averaged over joints


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name}: expected finite number')
    return float(value)


def chosen_sources(manifest, ids):
    """Return unique, exact SHA-256-pinned source entries in requested order."""
    if not 1 <= len(ids) <= MAX_INPUTS or len(set(ids)) != len(ids):
        raise ValueError('Select 1..10 distinct motion IDs')
    by_id = {x['id']: x for x in manifest['files']}
    chosen, seen = [], set()
    for motion_id in ids:
        if motion_id not in by_id:
            raise ValueError(f'Unknown unpinned CMU motion: {motion_id}')
        entry = by_id[motion_id]
        if entry['sha256'] in seen:
            raise ValueError('Duplicate motion bytes across different IDs are not independent')
        seen.add(entry['sha256'])
        chosen.append(entry)
    return chosen


def _quaternion_angular_motion(clip):
    """Physical radians/frame by bone, insensitive to equivalent q/-q signs."""
    grouped = {}
    for index, c in enumerate(clip.profile.channels):
        if c.interpolation == 'quaternion':
            grouped.setdefault((c.bone, c.data_path), {})[c.array_index] = index
    arrays = []
    for (_, _), columns in grouped.items():
        if set(columns) != {0, 1, 2, 3}:
            continue
        q = np.asarray(clip.frames[:, [columns[i] for i in range(4)]], dtype=np.float64)
        dot = np.clip(np.abs(np.sum(q[1:] * q[:-1], axis=1)), 0.0, 1.0)
        # Finite signed-quaternion-safe angular distance. A new near-static
        # Action must not look like a wonderful loop simply because it does not move.
        arrays.append(2 * np.arccos(dot))
    if not arrays:
        return np.zeros(max(0, clip.frame_count - 1), dtype=float)
    return np.mean(np.stack(arrays), axis=0)


def motion_activity(angular_changes, *, start_seconds, end_seconds, frame_dt):
    """Relative non-root motion activity within a candidate, bounded and explicit."""
    x = np.asarray(angular_changes, dtype=float)
    if x.ndim != 1 or len(x) < 8 or not np.isfinite(x).all() or frame_dt <= 0:
        return 0.0
    a = max(0, math.floor(start_seconds / frame_dt))
    b = min(len(x), math.ceil(end_seconds / frame_dt))
    if b - a < 5:
        return 0.0
    global_activity = float(np.median(x))
    if global_activity <= MIN_ABSOLUTE_ANGULAR_ACTIVITY:
        return 0.0
    window_activity = float(np.median(x[a:b]))
    if window_activity <= MIN_ABSOLUTE_ANGULAR_ACTIVITY:
        return 0.0
    return round(min(5.0, max(0.0, window_activity / global_activity)), 5)


def pick_review_loops(report, angular_changes, *, frame_dt, max_per_action=2):
    """Only select native-verified, moving, nontrivial *review* loops."""
    if max_per_action < 0 or max_per_action > 12:
        raise ValueError('Invalid per-action review limit')
    candidates = []
    for item in report.get('previews', []):
        if (not item.get('native_samples_verified') or
                item.get('loop_seam_approved') or item.get('audio_beat_alignment_verified') or
                item.get('requires_review') is not True):
            continue
        start = _finite(item.get('source_start_seconds'), 'start')
        end = _finite(item.get('source_end_seconds'), 'end')
        duration = end - start
        if not MIN_LOOP_SECONDS <= duration <= MAX_LOOP_SECONDS:
            continue
        beats = item.get('source_beats')
        if type(beats) is not int or beats not in (2, 4, 8, 16, 32):
            continue
        diag = item.get('stemlab_diagnostics') or {}
        if (diag.get('alignment') != 'estimated_motion_beat_grid' or
                diag.get('requires_review') is not True or diag.get('repaired') is not False):
            continue
        if any(diag.get(k) is None or _finite(diag[k], k) > limit
               for k, limit in (('pose_mismatch', .32), ('velocity_mismatch', .60),
                                ('root_drift_relative', .02))):
            continue
        activity = motion_activity(angular_changes, start_seconds=start, end_seconds=end,
                                   frame_dt=frame_dt)
        if activity < MIN_ACTIVITY_RATIO:
            continue
        score = _finite(item.get('score'), 'loop rank')
        seam = _finite(diag['pose_mismatch'], 'pose') + _finite(diag['velocity_mismatch'], 'velocity')
        candidates.append({
            'start_seconds': round(start, 6), 'end_seconds': round(end, 6),
            'duration_seconds': round(duration, 6), 'beats_estimated': beats,
            'source_bpm_estimated': _finite(item.get('source_bpm_estimated'), 'source BPM'),
            'ranking': round(score, 5), 'activity_relative_to_action': activity,
            'pose_mismatch': diag['pose_mismatch'],
            'velocity_mismatch': diag['velocity_mismatch'],
            'root_drift_relative': diag['root_drift_relative'],
            'render_priority': round(score * min(1.5, activity) / (1.0 + .2 * seam), 6),
            'selection_kind': 'unverified_loop_candidate',
            'preview_identity_sha256': item['recording_sha256'],
            'native_samples_verified': True, 'requires_review': True,
            'beat_alignment_confirmed': False, 'loop_seam_approved': False,
        })
    candidates.sort(key=lambda v: (-v['render_priority'], -v['duration_seconds'], v['start_seconds']))
    selected = []
    for entry in candidates:
        if any(abs(entry['start_seconds'] - old['start_seconds']) < .5 for old in selected):
            continue
        selected.append(entry)
        if len(selected) >= max_per_action:
            break
    return selected


def _quat_rotation(q):
    w, x, y, z = [float(k) for k in q]
    n = math.sqrt(w*w + x*x + y*y + z*z)
    if n == 0:
        raise ValueError('Non-unit source quaternion')
    w, x, y, z = w/n, x/n, y/n, z/n
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)],
        [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)],
        [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]
    ])


def pose_joints(clip, frame_index):
    """Read-only offline skeletal forward kinematics from original physical frames."""
    if not 0 <= frame_index < clip.frame_count:
        raise IndexError('Source frame outside recording')
    skeleton = clip.profile.source['skeleton']
    bones = {b['name']: i for i, b in enumerate(skeleton)}
    matrices = [np.asarray(b['rest_matrix'], dtype=float).reshape(4, 4) for b in skeleton]
    groups = {}
    for index, channel in enumerate(clip.profile.channels):
        groups.setdefault((channel.bone, channel.data_path), {})[channel.array_index] = index
    row = np.asarray(clip.frames[frame_index], dtype=float)
    world = []
    for i, item in enumerate(skeleton):
        parent = bones.get(item['parent']) if item['parent'] is not None else None
        if parent is not None and parent >= i:
            raise ValueError('Non-topological source skeleton')
        relative = (np.linalg.inv(matrices[parent]) @ matrices[i] if parent is not None
                    else matrices[i].copy())
        controls = np.eye(4)
        location = groups.get((item['name'], 'location'), {})
        if location:
            if set(location) != {0, 1, 2}:
                raise ValueError('Incomplete location group')
            controls[:3, 3] = [row[location[k]] for k in (0, 1, 2)]
        quaternion = groups.get((item['name'], 'rotation_quaternion'), {})
        if quaternion:
            if set(quaternion) != {0, 1, 2, 3}:
                raise ValueError('Incomplete rotation group')
            controls[:3, :3] = _quat_rotation([row[quaternion[k]] for k in (0, 1, 2, 3)])
        composed = (world[parent] if parent is not None else np.eye(4)) @ relative @ controls
        world.append(composed)
    return skeleton, np.asarray([mat[:3, 3] for mat in world], dtype=float)


def _skeleton_frames(clip, start, end, *, frames_per_second=12):
    fps_source = 1. / float(clip.frame_time_seconds)
    count = min(MAX_FRAMES, max(8, math.ceil((end - start) * frames_per_second)))
    times = np.linspace(start, end, count, endpoint=False)
    positions = []
    for seconds in times:
        idx = min(clip.frame_count - 1, max(0, round(float(seconds) * fps_source)))
        joints, coords = pose_joints(clip, idx)
        positions.append(coords)
    return joints, positions


def make_preview_gif(clip, loop, output, *, label, attribution):
    """Render a 2-D projected *moving rig*, not a serialized source motion."""
    joints, frames = _skeleton_frames(clip, loop['start_seconds'], loop['end_seconds'])
    # Follow the root for view framing; report the measured uncorrected root
    # translation in the data and never imply this fixes a traveling-loop seam.
    basis = []
    for coords in frames:
        centered = coords.copy()
        centered[:, :2] -= centered[0, :2]
        x = .86*centered[:, 0] + .35*centered[:, 1]
        y = centered[:, 2] - .22*centered[:, 1]
        basis.append(np.stack([x, y], axis=1))
    all_points = np.concatenate(basis)
    limit = max(2., float(np.percentile(np.max(np.abs(all_points), axis=1), 98)))
    scale = 137 / limit
    image_frames = []
    fontsize = ImageFont.load_default()
    names = {j['name']: i for i, j in enumerate(joints)}
    for frame_no, projected in enumerate(basis):
        img = Image.new('RGB', (420, 380), (15, 23, 36))
        dr = ImageDraw.Draw(img)
        dr.rounded_rectangle((12, 12, 408, 368), radius=16, outline=(70, 90, 108), width=2)
        dr.text((26, 22), label[:42], font=fontsize, fill=(242, 238, 223))
        bpm = loop.get('source_bpm_estimated')
        tempo = f'motion BPM ~{bpm:.1f}' if bpm is not None else 'motion BPM unknown'
        repeating = loop.get('selection_kind', 'unverified_loop_candidate') == 'unverified_loop_candidate'
        note = (f"{loop['beats_estimated']} beat slots / LOOP REVIEW" if repeating
                else 'NON-LOOPING EXCERPT / MOTION REVIEW')
        dr.text((26, 40), (tempo + ' / ' + note)[:60], font=fontsize,
                fill=(183, 199, 218))
        dr.line((20, 344, 400, 344), fill=(83, 102, 119), width=1)
        pix = [(210 + p[0]*scale, 193 - p[1]*scale) for p in projected]
        for i, bone in enumerate(joints):
            p = names.get(bone['parent']) if bone['parent'] is not None else None
            if p is None:
                continue
            name = bone['name'].lower()
            color = (246, 164, 110) if 'left' in name else (104, 216, 190) if 'right' in name else (222, 221, 233)
            dr.line((*pix[p], *pix[i]), fill=color, width=4)
            if any(k in name for k in ('foot', 'hand', 'head')):
                xx, yy = pix[i]
                dr.ellipse((xx-3, yy-3, xx+3, yy+3), fill=color)
        progress = (frame_no + 1) / len(basis)
        dr.rounded_rectangle((26, 324, 394, 332), radius=4, fill=(52, 61, 80))
        dr.rounded_rectangle((26, 324, 26 + 368*progress, 332), radius=4, fill=(104, 216, 190))
        footer = ('CMU source rig / unverified motion-loop candidate' if repeating
                  else 'CMU source rig / excerpt NOT loopable or beat-aligned')
        dr.text((26, 348), footer, font=fontsize, fill=(157, 171, 190))
        image_frames.append(img)
    output.parent.mkdir(parents=True, exist_ok=True)
    # An unapproved loop candidate repeats for seam inspection. Source studies
    # play ONCE: a GIF loop would imply a seamless repeat where none was found.
    repeating = loop.get('selection_kind', 'unverified_loop_candidate') == 'unverified_loop_candidate'
    gif_options = {'loop': 0} if repeating else {}
    image_frames[0].save(output, format='GIF', save_all=True,
                         append_images=image_frames[1:], duration=round(1000/12),
                         optimize=True, disposal=2, **gif_options)
    with Image.open(output) as check:
        if check.n_frames < 8:
            raise AssertionError('Motion preview did not animate')
    return {'path': output.name, 'frames': len(image_frames),
            'mime': 'image/gif', 'source_licence': attribution}


def pick_motion_study(angular_changes, *, frame_dt, duration_seconds,
                      source_bpm=None):
    """Choose a genuinely moving, NON-LOOPING excerpt from the original Action.

    This is a fallback visualisation when no physical/beat-aligned source loop
    passes the established seam and native verification gates. It never invents
    an estimated musical beat zero, seam validation, or a compiled rig motion.
    """
    x = np.asarray(angular_changes, dtype=float)
    if (x.ndim != 1 or len(x) < 8 or not np.isfinite(x).all() or
            frame_dt <= 0 or duration_seconds < 1.8):
        return None
    global_activity = float(np.median(x))
    if global_activity <= MIN_ABSOLUTE_ANGULAR_ACTIVITY:
        return None
    length = min(3.0, max(1.5, min(2.6, duration_seconds * .54)))
    first = min(.15, max(frame_dt, duration_seconds - length))
    last = duration_seconds - length - .05
    if last < first:
        first = max(frame_dt, min(first, duration_seconds - length))
        last = first
    starts = np.linspace(first, last, min(44, max(2, math.ceil((last-first)/.16))))
    viable = []
    for start in starts:
        end = min(duration_seconds, float(start) + length)
        a = max(0, math.floor(start / frame_dt))
        b = min(len(x), math.ceil(end / frame_dt))
        if b-a < 8:
            continue
        segment = x[a:b]
        moving = float(np.mean(segment > MIN_ABSOLUTE_ANGULAR_ACTIVITY))
        median = float(np.median(segment))
        if median <= MIN_ABSOLUTE_ANGULAR_ACTIVITY or moving < .35:
            continue
        relative = median / global_activity
        if relative < MIN_ACTIVITY_RATIO:
            continue
        # Motion amount is only a display-interest heuristic. Not a probability
        # of musical timing, best dancer or seamless replay quality.
        q70 = float(np.percentile(segment, 70))
        interest = min(2., relative) * moving * math.log1p(q70 * 300)
        viable.append((interest, start, end, relative, moving))
    if not viable:
        return None
    interest, start, end, relative, moving = max(viable, key=lambda t: (t[0], -t[1]))
    return dict(selection_kind='non_looping_motion_study',
                start_seconds=round(float(start), 6),
                end_seconds=round(float(end), 6),
                duration_seconds=round(float(end-start), 6),
                source_bpm_estimated=(float(source_bpm) if source_bpm is not None else None),
                beats_estimated=None,
                activity_relative_to_action=round(relative, 5),
                moving_frame_fraction=round(moving, 5),
                render_priority=round(interest, 6),
                native_samples_verified=False,
                verified_source_bytes=True,
                requires_review=True, audio_beat_alignment_verified=False,
                loop_seam_approved=False, repeat_policy='do_not_repeat')


def _dance_family(row):
    """Prefer a mix of visibly different dances in the limited CI gallery."""
    title = row.get('title', row['source_id']).casefold()
    for style in ('charleston', 'twist', 'chicken', 'macarena', 'breakdance',
                  'russian', 'whirl', 'pirouette', 'ballet', 'salsa'):
        if style in title:
            return style
    return row['source_id']


def select_showcase(rows, *, max_selected=4):
    """Select verified loop candidates first, then active non-looping studies.

    Never lower the full-Action 70% confidence gate or turn pose recurrence
    into a published loop. Diversity is applied to each class independently.
    """
    if not 1 <= max_selected <= 8:
        raise ValueError('Select 1..8 showcases')
    options = []
    for row in rows:
        if row.get('error'):
            continue
        for loop in row.get('review_loops', []):
            options.append((0, -loop['render_priority'], row['source_id'], row, loop))
        study = row.get('motion_study')
        if study is not None:
            options.append((1, -study['render_priority'], row['source_id'], row, study))
    options.sort(key=lambda x: x[:3])
    result, seen, families = [], set(), set()
    for prefer_diversity in (True, False):
        for _, _, identity, row, selection in options:
            if identity in seen:
                continue
            family = _dance_family(row)
            if prefer_diversity and family in families:
                continue
            result.append((row, selection))
            seen.add(identity)
            families.add(family)
            if len(result) >= max_selected:
                return result
    return result


def write_gallery(directory, rows, selections, *, mirror_commit):
    "Publish distinct loop hypotheses and non-looping examples with safe HTML."
    directory = Path(directory)
    items = []
    loops = sum(p.get('selection_kind', 'unverified_loop_candidate') ==
                'unverified_loop_candidate' for _, p in selections)
    studies = len(selections) - loops
    for row, segment in selections:
        source = html.escape(row['source_id'])
        title = html.escape(row['title'])
        file = f"{row['source_id']}.gif"
        kind = segment.get('selection_kind', 'unverified_loop_candidate')
        bpm = segment.get('source_bpm_estimated')
        tempo = f'{bpm:.1f} BPM' if bpm is not None else 'unresolved BPM'
        duration = segment['duration_seconds']
        activity = segment['activity_relative_to_action']
        if kind == 'unverified_loop_candidate':
            tag = 'Loop candidate — NOT APPROVED'
            evidence = (f"Estimated {segment['beats_estimated']} motion beat slots; "
                        f"pose mismatch {segment['pose_mismatch']}; "
                        f"velocity mismatch {segment['velocity_mismatch']}; "
                        f"root drift {segment['root_drift_relative']}. "
                        'Native sample check passed, but foot plants and repeat seam remain unverified.')
        else:
            tag = 'Non-looping source-motion study'
            evidence = (f'{segment["moving_frame_fraction"]:.0%} of sampled frames contain '
                        'measurable joint motion. This is an ACTIVE EXCERPT, not a '
                        'beat-matched loop. Playback stops at the final frame.')
        items.append(f'''<article class="card"><img src="previews/{html.escape(file)}"
          alt="Moving source skeleton: {title}; {tag}. Musical timing unverified" loading="lazy">
          <h2>{title} <span>CMU {source}</span></h2>
          <p class="tag">{html.escape(tag)}</p>
          <p>Estimated whole-Action kinematic tempo: {html.escape(tempo)} ·
          Preview duration {duration:.2f}s · Relative motion activity {activity:.2f}×.</p>
          <p><small>{html.escape(evidence)}</small></p>
          <a href="{html.escape(row['source_url'], quote=True)}">Original CMU recording</a>
          <p class="caution">No confirmed music beats, beat one, foot contact or seamless repeat</p>
          </article>''')
    document=f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>DanceRudiments · source-motion beat finding</title><style>
    :root{{font:16px/1.5 system-ui;color:#d9e7ee;background:#0e1521}}
    main{{max-width:1160px;margin:0 auto;padding:32px 18px}}
    h1{{font-size:clamp(25px,4vw,43px)}}h2{{font-size:19px}}
    p{{max-width:74ch}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:20px}}
    .card{{background:#172335;padding:14px;border:1px solid #32475c;border-radius:12px}}
    img{{display:block;width:100%;border-radius:8px;aspect-ratio:420/380;object-fit:contain}}
    span{{font-size:12px;color:#a3bccc}}small{{color:#bacdd6}}
    a{{color:#94ded5}}.caution{{color:#f1bd9e;font-size:13px}}
    .tag{{text-transform:uppercase;letter-spacing:.05em;font-size:12px;color:#95d4c8}}
    </style></head><body><main><h1>Beat-finding on real rig movement</h1>
    <p>Source-hash-checked CMU motions analysed with DanceRudiments and StemLab.
    This build contains <strong>{loops} unapproved loop candidates</strong> and
    <strong>{studies} non-looping motion studies</strong>. Where the beat-and-seam
    evidence did not support a loop, the gallery displays an active source excerpt
    instead of pretending a repeating pose is a validated dance loop.</p>
    <div class="grid">{''.join(items)}</div>
    <p>Source: <a href="https://mocap.cs.cmu.edu/">CMU Graphics Lab</a>.
    The data used in this project was obtained from mocap.cs.cmu.edu.
    The database was created with funding from NSF EIA-0196217.
    BVH conversion by Bruce Hahne / cgspeed. Converted motion data may not be sold directly.
    Pinned source mirror commit: {html.escape(mirror_commit)}.</p>
    <p>CI publishes rendered skeleton previews and bounded analysis metadata only,
    never original BVH, converted rig-motion channels, or audio.
    An estimated source tempo does not establish musical downbeats, meter or beat phase.</p>
    </main></body></html>'''
    (directory/'index.html').write_text(document, encoding='utf-8')


def build(cache_root, output_dir, *, ids=DEFAULT_IDS, download=False, max_selected=4,
          min_full_confidence=.70, minimum_previews=3):
    """Run the original source-first StemLab pipeline; fail closed on identity errors."""
    from acquire_cmu_dance import load_manifest, _ensure_file
    from dancerudiments_authoring.bvh_import import load_bvh
    from dancerudiments_authoring.source_loop_analysis import source_capture_from_bvh, analyse_source_capture

    if not 0 <= min_full_confidence <= 1 or minimum_previews < 0:
        raise ValueError('Invalid confidence or showcase count requirement')
    cache_root, output_dir = Path(cache_root).resolve(), Path(output_dir).resolve()
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError('Choose a new CI showcase output directory')
    if output_dir == cache_root or output_dir.is_relative_to(cache_root):
        raise ValueError('Output may not overwrite the pinned source cache')
    manifest = load_manifest(ROOT/'motion-packages/cmu-dance-sources.json')
    requested = chosen_sources(manifest, ids)
    output_dir.mkdir(parents=True)
    (output_dir/'.private').mkdir()
    rows, private_clips = [], {}
    for item in requested:
        identity = item['id']
        row = {'source_id': identity, 'title': item['title'],
               'source_url': item['source_url'], 'sha256': item['sha256'],
               'license_id': 'LicenseRef-CMU-Mocap', 'frame_clock_verified_musical': False,
               'first_beat_confirmed': False, 'loop_seam_approved': False}
        try:
            _ensure_file(cache_root, item, download=download)
            path = cache_root/item['cache_path']
            if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Verified source SHA-256 changed unexpectedly')
            clip = load_bvh(path, source_id='cmu_dance', axis_forward='-Z',
                            axis_up='Y', root_offset_policy='motion')
            if clip.source_sha256 != item['sha256']:
                raise ValueError('BVH parser source identity mismatch')
            # Converter was documented to add one calibration pose. This is a
            # source-processing assumption, NOT proof of the original capture FPS.
            captured = source_capture_from_bvh(clip, calibration_frames=1,
                source_provenance={'source_sha256': item['sha256'],
                                   'source_url': item['source_url'],
                                   'source_license_id': 'LicenseRef-CMU-Mocap'})
            job_dir=output_dir/'.private'/identity
            report = analyse_source_capture(
                captured, job_dir, original_source_sha256=item['sha256'],
                min_bpm=55, max_bpm=220, max_previews=12,
                verify_native=True, full_motion_confidence_threshold=min_full_confidence)
            if report['source_original_sha256'] != item['sha256'] or report['profile_sha256'] != clip.profile.fingerprint:
                raise ValueError('Full source-motion report identity mismatch')
            motion_changes = _quaternion_angular_motion(clip)
            shortlist = pick_review_loops(report, motion_changes,
                                          frame_dt=float(clip.frame_time_seconds))
            fit = report.get('full_motion_fit', {})
            study = pick_motion_study(motion_changes,
                                      frame_dt=float(clip.frame_time_seconds),
                                      duration_seconds=float(clip.duration_seconds),
                                      source_bpm=fit.get('selected_bpm'))
            row.update(source_frames=clip.frame_count,
                       header_fps_estimated=round(clip.source_fps, 6),
                       duration_seconds=round(clip.duration_seconds, 6),
                       profile_sha256=clip.profile.fingerprint,
                       bpm_estimated=fit.get('selected_bpm'),
                       grid_fit_confidence_percent=fit.get('confidence_percent'),
                       grid_fit_confidence_is_calibrated_probability=False,
                       full_action_shortlisted=bool(report.get('full_motion_count')),
                       full_action_rejection_reasons=fit.get('reasons', []),
                       raw_motion_loop_candidates=(
                           int(report.get('unconverted_candidate_count', 0)) +
                           int(report.get('loopable_clip_count', 0))),
                       native_preview_count=len(report.get('previews', [])),
                       review_loops=shortlist, motion_study=study)
            private_clips[identity] = clip
        except (OSError, RuntimeError, ValueError) as exc:
            row['error'] = f'{type(exc).__name__}: {str(exc)[:400]}'
        rows.append(row)
    selections = select_showcase(rows, max_selected=max_selected)
    for row, loop in selections:
        make_preview_gif(private_clips[row['source_id']], loop,
                         output_dir/'previews'/f"{row['source_id']}.gif",
                         label=f"CMU {row['source_id']} · {row['title']}",
                         attribution='CMU-Mocap')
        row['showcase_selection'] = dict(loop)
        if loop.get('selection_kind') == 'unverified_loop_candidate':
            row['showcase_loop'] = dict(loop)
        row['preview_gif'] = f'previews/{row["source_id"]}.gif'
    # No numerical skeleton channels in the artifact: do not expose `.private`.
    write_gallery(output_dir, rows, selections, mirror_commit=manifest['mirror_commit'])
    metadata = {'format': FORMAT, 'schema_version': 1,
                'source_mirror_commit': manifest['mirror_commit'],
                'sources_reviewed': len(rows), 'sources_failed': sum('error' in r for r in rows),
                'reviewable_source_count': sum(bool(r.get('review_loops')) for r in rows),
                'selected_source_count': len(selections),
                'selected_loop_candidate_count': sum(
                    entry.get('selection_kind') == 'unverified_loop_candidate'
                    for _, entry in selections),
                'selected_motion_study_count': sum(
                    entry.get('selection_kind') == 'non_looping_motion_study'
                    for _, entry in selections),
                'selection_policy': ('native-verified physical loop candidates first; '
                    'fallback to original-byte-verified active NON-LOOPING studies; '
                    f'never weaken >= {MIN_LOOP_SECONDS}s seam gate, '
                    f'>={MIN_ACTIVITY_RATIO}x movement gate, or 70% full-Action gate'),
                'visualisation': 'animated GIF of original source rig, not a rig-motion binary',
                'annotations': 'source-time kinematic estimates, neither musical downbeats nor loop approval',
                'source_rights': 'CMU-Mocap; see source URLs and attribution',
                'sources': rows}
    (output_dir/'summary.json').write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n',
                                            encoding='utf-8')
    if len(selections) < minimum_previews:
        raise RuntimeError(f'Only {len(selections)} source-verified moving showcase excerpts; '
                           f'expected {minimum_previews}. See summary.json for rejected loops and studies.')
    return metadata


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-root', type=Path, default=ROOT/'.cache/motion-beat-source-pool')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--ids', nargs='+', default=DEFAULT_IDS)
    parser.add_argument('--download', action='store_true',
                        help='Allow download only of SHA-256 pinned CMU BVH files, after opt-in')
    parser.add_argument('--max-selected', type=int, default=4)
    parser.add_argument('--minimum-showcases', '--minimum-previews',
                        dest='minimum_previews', type=int, default=3,
                        help='Minimum source-verified animated demonstrations; NOT minimum approved loops')
    parser.add_argument('--min-full-confidence', type=float, default=.7)
    opts=parser.parse_args(argv)
    result=build(opts.cache_root,opts.output_dir,ids=tuple(opts.ids),
                 download=opts.download,max_selected=opts.max_selected,
                 min_full_confidence=opts.min_full_confidence,
                 minimum_previews=opts.minimum_previews)
    print(json.dumps({k:result[k] for k in ('sources_reviewed','sources_failed',
                  'reviewable_source_count','selected_source_count',
                  'selected_loop_candidate_count','selected_motion_study_count')},indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
