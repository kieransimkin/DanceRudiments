"""Offline, source-bound skeletal kinematics and contact hypotheses.

Only the explicitly evaluated portable source carrier can be reconstructed here.
Animator controls of a constrained Rigify rig do not specify the resulting joint
positions. Those captures must first be evaluated by the existing Blender
extractor. This module never samples a native Recording or rewrites source data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from statistics import median

from ._validation import ScoreError
from .motion_import import RigCapture

FORMAT = 'dancerudiments.world-motion-evidence'
SOURCE_ADAPTER = 'dancerudiments.skeletal-source-v1'
FULL_INHERITANCE = 'FULL; local location; inherit rotation'
MAX_WORLD_MATRIX_VALUES = 16_777_216
MAX_REPORT_POSITION_VALUES = 2_000_000
_DEFAULTS = {'location': (0., 0., 0.),
             'rotation_quaternion': (1., 0., 0., 0.), 'scale': (1., 1., 1.)}


class UnsupportedWorldMotion(ScoreError):
    """The capture lacks evaluated, reconstructible skeletal semantics."""


def _numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise ImportError('World-motion authoring requires the optional motion-import NumPy extra') from exc
    return np


def _readonly(array):
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class WorldMotion:
    """Physical poses evaluated only at the original captured timestamps.

    Arrays are read-only. Bone order is the saved profile's skeleton order,
    which need not be topological. ``root_relative_positions`` remove the
    complete root transform, including its rotation/scale, for gesture analysis.
    All distances remain in the carrier's declared Blender/source units.
    """

    frame_times_seconds: object
    bone_names: tuple[str, ...]
    parents: tuple[int, ...]
    rest_matrices: object
    world_matrices: object
    positions: object
    root_relative_positions: object
    root_index: int
    body_scale: float
    profile_sha256: str
    capture_sha256: str


@dataclass(frozen=True)
class ContactThresholds:
    """Explicit, uncalibrated tolerances relative to the rest-skeleton extent."""

    height_fraction: float = .04
    planar_speed_fraction: float = .20
    vertical_speed_fraction: float = .20
    minimum_contact_seconds: float = .08

    def __post_init__(self):
        for name, value in asdict(self).items():
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0):
                raise ScoreError(f'{name} must be a positive finite number')
        if self.minimum_contact_seconds > 2:
            raise ScoreError('minimum_contact_seconds cannot exceed two seconds')


def _source_layout(profile, np):
    source = profile.source
    if (source.get('adapter') != SOURCE_ADAPTER
            or source.get('carrier_inheritance') != FULL_INHERITANCE):
        raise UnsupportedWorldMotion(
            'World-space evidence requires the evaluated skeletal-source-v1 FULL carrier; '
            'raw Rigify controls and unknown constraint/inheritance semantics need Blender evaluation')
    skeleton = source.get('skeleton')
    if not isinstance(skeleton, list) or not skeleton or len(skeleton) > 4096:
        raise ScoreError('Portable skeleton must contain 1..4096 bones')
    if any(not isinstance(bone, dict) for bone in skeleton):
        raise ScoreError('Portable skeleton entries must be objects')
    names = tuple(bone.get('name') for bone in skeleton)
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        raise ScoreError('Portable skeleton names must be nonempty and unique')
    lookup = {name: i for i, name in enumerate(names)}
    parents = []
    matrices = []
    for index, bone in enumerate(skeleton):
        parent = bone.get('parent')
        if parent is not None and (not isinstance(parent, str) or parent not in lookup):
            raise ScoreError(f'Missing skeleton parent for {names[index]}')
        parents.append(-1 if parent is None else lookup[parent])
        try:
            matrix = np.asarray(bone['rest_matrix'], dtype=np.float64).reshape(4, 4)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ScoreError('Each portable bone needs a finite row-major rest matrix') from exc
        if (not np.isfinite(matrix).all() or not np.allclose(matrix[3], (0, 0, 0, 1), atol=1e-8)
                or not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=2e-6)
                or not np.isclose(np.linalg.det(matrix[:3, :3]), 1., atol=2e-6)):
            raise ScoreError('Portable rest matrices must be finite, rigid, proper affine transforms')
        matrices.append(matrix)
    roots = [i for i, parent in enumerate(parents) if parent == -1]
    if len(roots) != 1 or source.get('object_motion_root') != names[roots[0]]:
        raise ScoreError('Portable skeleton requires exactly its declared object_motion_root')
    root = roots[0]
    # Blender exports bones alphabetically, so parent-before-child is not an
    # interchange requirement. Resolve the graph explicitly and reject cycles.
    children = [[] for _ in names]
    for index, parent in enumerate(parents):
        if parent >= 0:
            children[parent].append(index)
    order = [root]
    for index in order:
        order.extend(children[index])
        if len(order) > len(names):
            raise ScoreError('Portable skeleton hierarchy contains a cycle')
    if len(order) != len(names):
        raise ScoreError('Portable skeleton hierarchy contains a disconnected cycle')
    scale = source.get('scene_unit_scale_length')
    if (isinstance(scale, bool) or not isinstance(scale, (int, float))
            or not math.isfinite(scale) or scale <= 0):
        raise ScoreError('Portable source requires a positive scene unit scale')
    return names, tuple(parents), np.asarray(matrices), root, order


def evaluate_world_motion(capture: RigCapture) -> WorldMotion:
    """Evaluate exact portable FK at all source frames, without interpolation.

    The existing Blender importer has already baked constraints/inheritance into
    carrier TRS. Omitted groups must be explicit, never silently defaulted.
    """
    if not isinstance(capture, RigCapture):
        raise ScoreError('World motion requires a validated RigCapture')
    np = _numpy()
    names, parents, rest, root, order = _source_layout(capture.profile, np)
    count = len(capture.frames)
    if count * len(names) * 16 > MAX_WORLD_MATRIX_VALUES:
        raise ScoreError('World-motion matrix budget exceeded; select a shorter explicit source excerpt')
    groups = {}
    for index, channel in enumerate(capture.profile.channels):
        if (channel.bone not in names or channel.data_path not in _DEFAULTS
                or channel.value_type != 'float'):
            raise UnsupportedWorldMotion('Only evaluated portable location/quaternion/scale channels are supported')
        groups.setdefault((channel.bone, channel.data_path), {})[channel.array_index] = index
    omitted = {}
    omitted_groups = capture.profile.source.get('omitted_neutral_groups', [])
    if not isinstance(omitted_groups, list):
        raise ScoreError('Omitted transform groups must be an explicit list')
    for item in omitted_groups:
        if not isinstance(item, dict):
            raise ScoreError('Omitted transform groups must be explicit objects')
        key = (item.get('bone'), item.get('data_path'))
        if (not all(isinstance(value, str) for value in key)
                or key[0] not in names or key[1] not in _DEFAULTS or key in omitted or key in groups):
            raise ScoreError('Invalid, duplicate or conflicting omitted transform group')
        try:
            values = np.asarray(item.get('values'), dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise ScoreError('Invalid omitted transform values') from exc
        if values.shape != (len(_DEFAULTS[key[1]]),) or not np.isfinite(values).all():
            raise ScoreError('Invalid omitted transform values')
        if not np.allclose(values, _DEFAULTS[key[1]], atol=1e-9):
            raise ScoreError('Omitted portable groups must contain the declared neutral transform')
        omitted[key] = values
    rows = np.asarray(capture.frames, dtype=np.float64)

    def values(bone, path):
        key = (bone, path)
        indices = groups.get(key)
        width = len(_DEFAULTS[path])
        if indices is None:
            if key not in omitted:
                raise ScoreError(f'Missing explicit transform group: {bone}.{path}')
            return np.broadcast_to(omitted[key], (count, width))
        if set(indices) != set(range(width)):
            raise ScoreError(f'Incomplete transform group: {bone}.{path}')
        return rows[:, [indices[i] for i in range(width)]]

    worlds = np.empty((count, len(names), 4, 4), dtype=np.float64)
    for index in order:
        name = names[index]
        translation = values(name, 'location')
        quat = values(name, 'rotation_quaternion')
        # RigCapture permits small storage roundoff around unit norm. Match the
        # existing Blender apply bridge's normalization before forming a matrix.
        quat = quat / np.linalg.norm(quat, axis=1)[:, None]
        scale = values(name, 'scale')
        if np.any(np.abs(scale) < 1e-10):
            raise UnsupportedWorldMotion('Singular animated scale prevents a stable root-relative/contact evaluation')
        w, x, y, z = quat.T
        basis = np.zeros((count, 4, 4), dtype=np.float64)
        basis[:, 0, 0] = 1 - 2 * (y*y + z*z)
        basis[:, 0, 1] = 2 * (x*y - w*z)
        basis[:, 0, 2] = 2 * (x*z + w*y)
        basis[:, 1, 0] = 2 * (x*y + w*z)
        basis[:, 1, 1] = 1 - 2 * (x*x + z*z)
        basis[:, 1, 2] = 2 * (y*z - w*x)
        basis[:, 2, 0] = 2 * (x*z - w*y)
        basis[:, 2, 1] = 2 * (y*z + w*x)
        basis[:, 2, 2] = 1 - 2 * (x*x + y*y)
        basis[:, :3, :3] *= scale[:, None, :]
        basis[:, :3, 3] = translation
        basis[:, 3, 3] = 1.
        parent = parents[index]
        local_rest = rest[index] if parent < 0 else np.linalg.inv(rest[parent]) @ rest[index]
        local = local_rest @ basis
        worlds[:, index] = local if parent < 0 else worlds[:, parent] @ local
    if not np.isfinite(worlds).all():
        raise ScoreError('World transforms overflowed the finite physical range')
    positions = worlds[:, :, :3, 3].copy()
    relative = (np.linalg.inv(worlds[:, root])[:, None, :, :] @ worlds)[:, :, :3, 3].copy()
    extent = float(np.linalg.norm(np.ptp(rest[:, :3, 3], axis=0)))
    if extent <= 1e-9:
        lengths = [b.get('length', 0.) for b in capture.profile.source['skeleton']]
        extent = max((float(x) for x in lengths if type(x) in (int, float) and math.isfinite(x)), default=0.)
    if extent <= 1e-9:
        raise UnsupportedWorldMotion('Portable skeleton has no measurable rest extent for relative thresholds')
    return WorldMotion(_readonly(np.asarray(capture.frame_times_seconds)), names, parents,
                       _readonly(rest), _readonly(worlds), _readonly(positions), _readonly(relative),
                       root, extent, capture.profile.fingerprint, capture.fingerprint)


def _source_segment_indices(times):
    """Partition observed timestamps without importing NumPy or inferring poses."""
    if len(times) < 2:
        return ((0, len(times)),)
    deltas = [float(right)-float(left) for left, right in zip(times, times[1:])]
    ordinary = float(median(deltas))
    splits = [index+1 for index, delta in enumerate(deltas) if delta > ordinary * 3.0]
    bounds = [0, *splits, len(times)]
    return tuple(zip(bounds, bounds[1:]))


def source_valid_segments(capture: RigCapture) -> tuple[tuple[float, float], ...]:
    """Return closed source-time coverage intervals using the shared gap rule.

    An adjacent interval greater than three times the capture's median sample
    interval splits coverage. Nonuniform intervals below that threshold remain
    usable. One captured frame gives one zero-duration ``(time, time)`` segment;
    it cannot support a positive-duration repair. Two frames alone cannot
    establish a gap relative to another sampling interval. This function needs
    neither reconstructed world geometry nor the optional NumPy dependency.
    """
    if not isinstance(capture, RigCapture):
        raise ScoreError('Source coverage requires a validated RigCapture')
    times = capture.frame_times_seconds
    return tuple((times[first], times[last-1])
                 for first, last in _source_segment_indices(times))


def _segments(times, np):
    return list(_source_segment_indices(times))


def _gradient(values, times, segments, np):
    result = np.zeros_like(values, dtype=np.float64)
    for first, last in segments:
        if last-first >= 3:
            result[first:last] = np.gradient(values[first:last], times[first:last], axis=0, edge_order=2)
    return result


def _smooth(values, times, np):
    # A time-bounded symmetric mean uses actual source samples, including an
    # irregular final frame, without synthesizing any new event timestamp.
    left = np.searchsorted(times, times - .025)
    right = np.searchsorted(times, times + .025, side='right')
    cumulative = np.r_[0., np.cumsum(values)]
    return (cumulative[right] - cumulative[left]) / (right - left)


def _minimum_events(values, times, segments, *, family, minimum_prominence, np):
    result = []
    for first, last in segments:
        if last-first < 3:
            continue
        t = times[first:last]
        v = _smooth(values[first:last], t, np)
        spread = float(np.percentile(v, 90) - np.percentile(v, 10))
        if spread < minimum_prominence:
            continue
        candidates = []
        for i in range(1, len(v) - 1):
            if not (v[i] <= v[i - 1] and v[i] < v[i + 1]):
                continue
            lo, hi = np.searchsorted(t, (t[i] - .20, t[i] + .20))
            if lo >= i or hi <= i + 1:
                continue
            prominence = min(float(np.max(v[lo:i])), float(np.max(v[i+1:hi]))) - v[i]
            if prominence >= minimum_prominence:
                candidates.append((i, min(1., float(prominence / spread))))
        selected = []
        for index, strength in sorted(candidates, key=lambda p: (-p[1], p[0])):
            if all(abs(float(t[index] - t[previous])) >= .12 for previous, _ in selected):
                selected.append((index, strength))
        result.extend(dict(seconds=float(t[index]), strength=round(strength, 6),
                           family=family, kind='kinetic_minimum')
                      for index, strength in sorted(selected))
    return result


def _select_feet(names, requested):
    if requested is not None:
        if isinstance(requested, (str, bytes)):
            raise ScoreError('foot_bones must be a sequence of exact bone names')
        try:
            feet = tuple(requested)
        except TypeError as exc:
            raise ScoreError('foot_bones must be a sequence of exact bone names') from exc
        if any(not isinstance(name, str) for name in feet):
            raise ScoreError('foot_bones must contain exact bone names')
        if len(set(feet)) != len(feet) or any(name not in names for name in feet):
            raise ScoreError('Explicit foot bones must be unique members of the source profile')
        if len(feet) > 16:
            raise ScoreError('At most sixteen explicit foot keypoints can be analysed')
        return feet, 'explicit_caller_bone_names'
    # Names are only a labelled anatomical hypothesis. Prefer ankle/foot heads
    # to toe chains; callers can override this for unusual or nonhuman rigs.
    feet = [name for name in names if re.search(r'foot|ankle', name, re.IGNORECASE)]
    if not feet:
        feet = [name for name in names if re.search(r'toe', name, re.IGNORECASE)]
    return tuple(feet[:16]), 'bone_name_hypothesis_not_anatomical_verification'


def _runs(mask, first, last):
    start = None
    for index in range(first, last):
        if mask[index] and start is None:
            start = index
        if start is not None and (not mask[index] or index == last - 1):
            end = index if mask[index] else index - 1
            yield start, end
            start = None


def analyze_world_motion(capture: RigCapture, *, source_file_sha256=None,
                         foot_bones=None, thresholds=None, include_positions=False):
    """Return JSON-safe world/contact evidence, preserving all source clocks.

    ``source_file_sha256`` binds the sidecar to exact capture-file bytes when it
    is passed to StemLab. ``capture_sha256`` independently binds parsed content.
    Contacts and floor height are motion-derived hypotheses, never mesh/contact
    approval. Initial/final held contacts do not invent plant/toe-off events.
    """
    if source_file_sha256 is not None and (not isinstance(source_file_sha256, str)
            or re.fullmatch(r'[a-f0-9]{64}', source_file_sha256) is None):
        raise ScoreError('source_file_sha256 must be a lowercase SHA-256 digest')
    if type(include_positions) is not bool:
        raise ScoreError('include_positions must be boolean')
    thresholds = ContactThresholds() if thresholds is None else thresholds
    if not isinstance(thresholds, ContactThresholds):
        raise ScoreError('thresholds must be ContactThresholds')
    np = _numpy()
    motion = evaluate_world_motion(capture)
    times, positions, relative = motion.frame_times_seconds, motion.positions, motion.root_relative_positions
    segments = _segments(times, np)
    velocity = _gradient(positions, times, segments, np)
    relative_velocity = _gradient(relative, times, segments, np)
    included = [i for i in range(len(motion.bone_names)) if i != motion.root_index] or [motion.root_index]
    world_speed = np.mean(np.linalg.norm(velocity[:, included], axis=2), axis=1)
    relative_speed = np.mean(np.linalg.norm(relative_velocity[:, included], axis=2), axis=1)
    height = np.mean(positions[:, included, 2], axis=1)
    root_speed = np.linalg.norm(velocity[:, motion.root_index], axis=1)
    scale = motion.body_scale
    accents = []
    for values, family, prominence in ((world_speed, 'world_joint_velocity', .025*scale),
                                       (relative_speed, 'root_relative_joint_velocity', .025*scale),
                                       (height, 'body_height_proxy', .006*scale)):
        accents.extend(_minimum_events(values, times, segments, family=family,
                                        minimum_prominence=prominence, np=np))
    feet, selection = _select_feet(motion.bone_names, foot_bones)
    per_foot, contacts, events = [], [], []
    for bone in feet:
        index = motion.bone_names.index(bone)
        point = positions[:, index]
        planar_speed = np.linalg.norm(velocity[:, index, :2], axis=1)
        vertical_speed = np.abs(velocity[:, index, 2])
        floor = float(np.percentile(point[:, 2], 5))
        elevated = np.maximum(0., point[:, 2] - floor)
        height_limit = thresholds.height_fraction * scale
        speed_limit = thresholds.planar_speed_fraction * scale
        vertical_limit = thresholds.vertical_speed_fraction * scale
        stance = (elevated <= height_limit) & (vertical_speed <= vertical_limit)
        state = stance & (planar_speed <= speed_limit)
        confidence = (np.maximum(0., 1. - elevated / height_limit)
                      * np.maximum(0., 1. - planar_speed / speed_limit)
                      * np.maximum(0., 1. - vertical_speed / vertical_limit))
        # Unsupported temporal gaps cannot become held contacts.
        retained = np.zeros(len(times), dtype=bool)
        stance_slip = []
        for first, last in segments:
            if last-first < 3:
                continue
            for start, end in _runs(stance, first, last):
                if times[end] - times[start] >= thresholds.minimum_contact_seconds:
                    stance_slip.append(float(np.max(np.linalg.norm(point[start:end+1, :2]
                                                                      - point[start, :2], axis=1)) / scale))
            for start, end in _runs(state, first, last):
                if times[end] - times[start] < thresholds.minimum_contact_seconds:
                    continue
                retained[start:end+1] = True
                drift = float(np.max(np.linalg.norm(point[start:end+1, :2] - point[start, :2], axis=1)))
                quality = float(np.mean(confidence[start:end+1]))
                contacts.append(dict(bone=bone, start_seconds=float(times[start]), end_seconds=float(times[end]),
                    sample_start_index=int(start), sample_end_index_inclusive=int(end),
                    boundary_policy='first_to_last_observed_contact_samples', confidence=round(quality, 6),
                    anchor_position=point[start].tolist(), drift_distance=drift,
                    drift_relative=drift/scale, max_planar_speed=float(np.max(planar_speed[start:end+1])),
                    foot_plant_verified=False))
                if start > first:
                    events.append(dict(bone=bone, kind='foot_plant', seconds=float(times[start]),
                        time_interval_seconds=[float(times[start-1]), float(times[start])],
                        strength=round(quality, 6)))
                if end + 1 < last:
                    events.append(dict(bone=bone, kind='toe_off', seconds=float(times[end+1]),
                        time_interval_seconds=[float(times[end]), float(times[end+1])],
                        strength=round(quality, 6)))
        per_foot.append(dict(bone=bone, floor_height_estimate=floor,
                            floor_interpretation='low_quantile_bone_height_not_measured_ground_plane',
                            contact_state=retained.tolist(), height_above_estimated_floor=elevated.tolist(),
                            planar_speed=planar_speed.tolist(),
                            maximum_low_height_stance_drift_relative=max(stance_slip, default=0.)))
    accents.extend(dict(seconds=e['seconds'], strength=e['strength'], bone=e['bone'],
                        kind=e['kind'], family='contact_hypotheses')
                   for e in events if e['kind'] == 'foot_plant')
    accents.sort(key=lambda e: (e['seconds'], e['family'], e.get('bone', '')))
    events.sort(key=lambda e: (e['seconds'], e['bone'], e['kind']))
    report = dict(format=FORMAT, schema_version=1, supported=True, status='estimated',
        source_file_sha256=source_file_sha256, capture_sha256=motion.capture_sha256,
        profile_sha256=motion.profile_sha256, type_uri=capture.profile.type_uri,
        source_start_seconds=float(times[0]), source_end_seconds=float(times[-1]),
        frame_times_seconds=times.tolist(), validity_segments_seconds=[
            [float(times[first]), float(times[last-1])] for first, last in segments],
        coordinate_basis=dict(up_axis='Z', units='source_units', space='portable_source_world',
            scene_unit_scale_length=capture.profile.source['scene_unit_scale_length'],
            source_coordinate_system=capture.profile.source.get('coordinate_system'),
            physical_units_verified=False),
        bone_names=list(motion.bone_names), parent_indices=list(motion.parents),
        root_bone=motion.bone_names[motion.root_index], root_positions=positions[:, motion.root_index].tolist(),
        body_scale=scale, body_scale_method='rest_joint_bounding_box_diagonal_or_declared_single_bone_length',
        body_height_method='unweighted_mean_joint_height_not_mass_center_of_mass',
        evidence_families=['world_joint_velocity', 'root_relative_joint_velocity',
                           'body_height_proxy', 'contact_hypotheses'],
        family_lineage={'world_joint_velocity': 'world_kinematics',
                        'root_relative_joint_velocity': 'world_kinematics',
                        'body_height_proxy': 'world_kinematics',
                        'contact_hypotheses': 'contact_heuristic_from_same_capture'},
        envelopes=dict(world_speed=world_speed.tolist(), root_relative_speed=relative_speed.tolist(),
                       body_height_proxy=height.tolist(), root_speed=root_speed.tolist()),
        motion_accents=accents, contact_events=events, contact_intervals=contacts,
        foot_keypoints=per_foot, foot_selection_policy=selection,
        thresholds=asdict(thresholds), requires_review=True, musical_timing_verified=False,
        contacts_verified=False, limitations=[
            'Joint positions come from the captured source skeleton, not target skin geometry.',
            'Foot names, low-height stance, ground level and contact confidence are hypotheses.',
            'Root-relative gestures remove the complete root transform; world travel is retained separately.',
            'Correlated kinematic feature families are not independent detector votes.',
            'Source gaps have no inferred event or contact continuation.'])
    if any(last-first < 3 for first, last in segments):
        report['short_segment_policy'] = (
            'Fewer than three source frames retain their positions and coverage; '
            'velocities are zero placeholders, with no inferred accents or contacts.')
        report['derivative_validity_segments_seconds'] = [
            [float(times[first]), float(times[last-1])]
            for first, last in segments if last-first >= 3]
    if include_positions:
        if positions.size > MAX_REPORT_POSITION_VALUES:
            raise ScoreError('World-position JSON budget exceeded; use the in-memory evaluator or a shorter excerpt')
        report['joint_positions'] = {name: positions[:, i].tolist() for i, name in enumerate(motion.bone_names)}
    return report
