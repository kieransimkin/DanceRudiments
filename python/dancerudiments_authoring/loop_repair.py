"""Bounded offline seam finishing for explicitly selected source-motion windows.

The original capture/profile are immutable inputs. A successful result is a new
capture, suitable for the existing 64-pip compiler, with measured numeric closure
and optional world-space contact checks. It is not a new runtime sampler, a
musical-timing authority, or approval of a retargeted mesh.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
import hashlib
import math

from ._validation import ScoreError, canonical_json
from .motion_import import RigCapture, _frame_at, _slerp, _unit_quaternion
from .recording import MAX_RECORDING_VALUES
from .world_motion import source_valid_segments

FORMAT = "dancerudiments.loop-repair"
METHOD = "bounded-local-pose-and-tangent-v1"


def _real(value, label, *, minimum=0.0, maximum=None):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < minimum or (maximum is not None and value > maximum)):
        raise ScoreError(f"{label} must be finite and within its declared bounds")
    return float(value)


@dataclass(frozen=True)
class LoopRepairOptions:
    """Explicit correction budget; distances use source units or body scale.

    ``translation_scale`` overrides the portable skeleton's rest-pose extent.
    A capture without that skeleton must supply it when translations change.
    ``in_place`` removes the selected root's linear travel before seam finishing;
    all of that change is included in the correction budget.
    """

    sample_count: int = 129
    blend_fraction: float = 0.20
    root_policy: str = "preserve"
    root_bone: str | None = None
    root_axes: tuple[int, ...] = (0, 1, 2)
    translation_scale: float | None = None
    max_rotation_correction_radians: float = 0.45
    max_translation_correction_fraction: float = 0.15
    max_scalar_correction_fraction: float = 0.08
    max_correction_rms_fraction: float = 0.12
    min_activity_retention: float = 0.65
    max_activity_increase: float = 1.60
    min_activity: float = 0.01
    contact_policy: str = "validate"
    require_contacts: bool = False
    max_contact_slip_fraction: float = 0.02
    max_contact_speed_fraction_per_second: float = 0.20
    max_contact_root_correction_fraction: float = 0.10
    closure_tolerance: float = 1e-7
    tangent_tolerance: float = 1e-6

    def __post_init__(self):
        if type(self.sample_count) is not int or not 9 <= self.sample_count <= 4097:
            raise ScoreError("sample_count must be 9..4097 inclusive endpoint samples")
        _real(self.blend_fraction, "blend_fraction", minimum=.03, maximum=.45)
        if self.root_policy not in ("preserve", "in_place"):
            raise ScoreError("root_policy must be preserve or in_place")
        if self.root_bone is not None and (not isinstance(self.root_bone, str) or not self.root_bone):
            raise ScoreError("root_bone must be an exact nonempty profile bone name")
        if (not isinstance(self.root_axes, (tuple, list)) or not self.root_axes
                or any(type(x) is not int or x not in (0, 1, 2) for x in self.root_axes)
                or len(set(self.root_axes)) != len(self.root_axes)):
            raise ScoreError("root_axes must contain unique location indices 0, 1, 2")
        object.__setattr__(self, "root_axes", tuple(self.root_axes))
        if self.translation_scale is not None:
            _real(self.translation_scale, "translation_scale", minimum=1e-9)
        for name in ("max_rotation_correction_radians", "max_translation_correction_fraction",
                     "max_scalar_correction_fraction", "max_correction_rms_fraction",
                     "min_activity", "max_contact_slip_fraction",
                     "max_contact_speed_fraction_per_second", "max_contact_root_correction_fraction",
                     "closure_tolerance", "tangent_tolerance"):
            _real(getattr(self, name), name, minimum=1e-12)
        _real(self.min_activity_retention, "min_activity_retention", minimum=0., maximum=1.)
        _real(self.max_activity_increase, "max_activity_increase", minimum=1.)
        if self.contact_policy not in ("validate", "root_stabilize"):
            raise ScoreError("contact_policy must be validate or root_stabilize")
        if type(self.require_contacts) is not bool:
            raise ScoreError("require_contacts must be boolean")


@dataclass(frozen=True)
class FootContact:
    """A supplied stance interval in original source seconds, never a beat claim."""

    bone: str
    start_seconds: float
    end_seconds: float
    anchor_position: tuple[float, float, float] | None = None
    evidence: str = "explicit_annotation"

    def __post_init__(self):
        if not isinstance(self.bone, str) or not self.bone:
            raise ScoreError("Contact bone must be an exact nonempty name")
        for name in ("start_seconds", "end_seconds"):
            _real(getattr(self, name), name, minimum=-1e12, maximum=1e12)
        if self.end_seconds <= self.start_seconds:
            raise ScoreError("Contact end must follow its start")
        if self.evidence not in ("explicit_annotation", "world_kinematic_hypothesis"):
            raise ScoreError("Contact evidence must be explicitly annotated or kinematic")
        if self.anchor_position is not None:
            if not isinstance(self.anchor_position, (tuple, list)) or len(self.anchor_position) != 3:
                raise ScoreError("Contact anchor_position must have three world coordinates")
            object.__setattr__(self, "anchor_position", tuple(
                _real(x, "contact anchor", minimum=-1e12, maximum=1e12)
                for x in self.anchor_position))


@dataclass(frozen=True)
class LoopRepairResult:
    capture: RigCapture | None
    report: dict

    @property
    def accepted(self):
        return self.capture is not None and self.report["accepted"]


def contacts_from_world_report(capture, report, *, min_confidence=.5):
    """Read stance hypotheses only from this exact capture/profile's report.

    The hypotheses remain labelled as such; passing measured slip constraints
    does not establish that a foot actually touches a ground plane or mesh.
    """
    if not isinstance(capture, RigCapture):
        raise ScoreError("Contact extraction requires a validated RigCapture")
    _real(min_confidence, "min_confidence", minimum=0., maximum=1.)
    if (not isinstance(report, dict) or report.get("format") != "dancerudiments.world-motion-evidence"
            or report.get("schema_version") != 1 or report.get("supported") is not True
            or report.get("capture_sha256") != capture.fingerprint
            or report.get("profile_sha256") != capture.profile.fingerprint):
        raise ScoreError("Contact evidence does not match the exact source capture/profile")
    intervals = report.get("contact_intervals")
    if not isinstance(intervals, list) or len(intervals) > 4096:
        raise ScoreError("Contact evidence needs a bounded interval list")
    contacts = []
    for item in intervals:
        if not isinstance(item, dict):
            raise ScoreError("Contact evidence entries must be objects")
        confidence = _real(item.get("confidence"), "contact confidence", minimum=0., maximum=1.)
        contact = FootContact(item.get("bone"), item.get("start_seconds"), item.get("end_seconds"),
                              item.get("anchor_position"), "world_kinematic_hypothesis")
        if not capture.frame_times_seconds[0] <= contact.start_seconds < contact.end_seconds <= capture.frame_times_seconds[-1]:
            raise ScoreError("Contact evidence interval lies outside the original capture")
        if confidence >= min_confidence:
            contacts.append(contact)
    return tuple(contacts)


def _norm(v):
    return math.sqrt(math.fsum(float(x) ** 2 for x in v))


def _qmul(a, b):
    w, x, y, z = a
    u, i, j, k = b
    return (w*u-x*i-y*j-z*k, w*i+x*u+y*k-z*j,
            w*j-x*k+y*u+z*i, w*k+x*j-y*i+z*u)


def _qinv(q):
    return (q[0], -q[1], -q[2], -q[3])


def _qlog(q):
    q = _unit_quaternion(q)
    if q[0] < 0:
        q = tuple(-x for x in q)
    length = _norm(q[1:])
    if length < 1e-12:
        return tuple(2*x for x in q[1:])
    scale = 2 * math.atan2(length, q[0]) / length
    return tuple(x * scale for x in q[1:])


def _qexp(v):
    angle = _norm(v)
    factor = .5 if angle < 1e-12 else math.sin(angle/2) / angle
    return _unit_quaternion((math.cos(angle/2), *(x*factor for x in v)))


def _qdelta(a, b):
    """Spatial rotation from a to b; invariant to either quaternion's sign."""
    return _qlog(_qmul(b, _qinv(a)))


def _qrow(row, indices):
    return tuple(row[i] for i in indices)


def _groups(profile, data_path):
    result = {}
    for i, channel in enumerate(profile.channels):
        if channel.data_path == data_path:
            result.setdefault(channel.bone, {})[channel.array_index] = i
    return result


def _world(capture):
    try:
        from .world_motion import evaluate_world_motion
        return evaluate_world_motion(capture), None
    except (ImportError, ScoreError) as exc:
        return None, str(exc)


def _resample_window(capture, start, end, count, *, _valid_segments=None):
    if not isinstance(capture, RigCapture):
        raise ScoreError("Loop repair requires a validated RigCapture")
    start = _real(start, "start_seconds", minimum=-1e12, maximum=1e12)
    end = _real(end, "end_seconds", minimum=-1e12, maximum=1e12)
    if not capture.frame_times_seconds[0] <= start < end <= capture.frame_times_seconds[-1]:
        raise ScoreError("Loop bounds must lie within the original capture")
    segments = source_valid_segments(capture) if _valid_segments is None else _valid_segments
    if not any(first <= start < end <= last for first, last in segments):
        raise ScoreError("Loop bounds cross a source timestamp gap or missing coverage")
    if end-start < 1e-6:
        raise ScoreError("Loop period must be at least one microsecond")
    if count * len(capture.profile.channels) > MAX_RECORDING_VALUES:
        raise ScoreError("Loop repair exceeds the capture scalar budget")
    first, last = Fraction(str(start)), Fraction(str(end))
    source_times = tuple(first + (last-first)*i/(count-1) for i in range(count))
    rows = [_frame_at(capture, t) for t in source_times]
    times = tuple(float(t-first) for t in source_times)
    return rows, times


def _diagnostics(profile, rows, period, scale):
    from .motion_import import _quaternion_groups
    quats = _quaternion_groups(profile)
    q_indices = {i for group in quats for i in group}
    locations = _groups(profile, "location")
    location_indices = {i for group in locations.values() for i in group.values()}
    h = period/(len(rows)-1)
    rotation, rotation_v = [], []
    for group in quats:
        a, b, y, z = (_qrow(rows[i], group) for i in (0, 1, -2, -1))
        rotation.append(_norm(_qdelta(a, z)))
        va, vz = _qdelta(a, b), _qdelta(y, z)
        rotation_v.append(_norm((x-y)/h for x, y in zip(va, vz)))
    translation, translation_v = [], []
    for group in locations.values():
        indices = tuple(group.values())
        translation.append(_norm(rows[-1][i]-rows[0][i] for i in indices))
        translation_v.append(_norm(((rows[1][i]-rows[0][i]) -
                                    (rows[-1][i]-rows[-2][i]))/h for i in indices))
    scalars, scalar_v, discrete = [], [], True
    for i, ch in enumerate(profile.channels):
        if ch.interpolation == "step":
            discrete &= rows[0][i] == rows[-1][i] == rows[-2][i]
        elif i not in q_indices and i not in location_indices:
            span = ch.maximum-ch.minimum
            scalars.append(abs(rows[-1][i]-rows[0][i])/span)
            scalar_v.append(abs((rows[1][i]-rows[0][i]) -
                                (rows[-1][i]-rows[-2][i]))/(h*span))
    output = dict(max_rotation_seam_radians=max(rotation, default=0.),
                  max_rotation_velocity_jump_radians_per_second=max(rotation_v, default=0.),
                  max_translation_seam=max(translation, default=0.),
                  max_translation_velocity_jump=max(translation_v, default=0.),
                  max_scalar_seam_fraction=max(scalars, default=0.),
                  max_scalar_velocity_jump_fraction_per_second=max(scalar_v, default=0.),
                  discrete_seam_matches=bool(discrete))
    denom = scale or 1.
    output["rank_cost"] = (output["max_rotation_seam_radians"] +
                           output["max_translation_seam"]/denom +
                           output["max_scalar_seam_fraction"] + .05*period*(
                           output["max_rotation_velocity_jump_radians_per_second"] +
                           output["max_translation_velocity_jump"]/denom +
                           output["max_scalar_velocity_jump_fraction_per_second"]))
    return output


def _correction_curve(d0, d1, width):
    """Compact cubic: exact first two corrections; zero value/slope at width."""
    x1 = 1/width
    b = (d1/(1-x1)**2-d0)/x1
    return [((d0+b*j/width)*(1-j/width)**2) for j in range(width+1)]


def _close_rows(profile, rows, blend_fraction):
    from .motion_import import _quaternion_groups
    output = [list(row) for row in rows]
    width = min((len(rows)-2)//2, max(2, math.ceil((len(rows)-1)*blend_fraction)))
    qgroups = _quaternion_groups(profile)
    qindices = {i for group in qgroups for i in group}
    for i, channel in enumerate(profile.channels):
        if i in qindices or channel.interpolation == "step":
            continue
        a, b, y, z = (rows[j][i] for j in (0, 1, -2, -1))
        seam = .5*(a+z)
        tangent = .5*((b-a)+(z-y))
        left = _correction_curve(seam-a, seam+tangent-b, width)
        right = _correction_curve(seam-z, seam-tangent-y, width)
        for j in range(width+1):
            output[j][i] += left[j]
            output[-1-j][i] += right[j]
    for group in qgroups:
        a, b, y, z = (_qrow(rows[j], group) for j in (0, 1, -2, -1))
        seam = _slerp(a, z, .5)
        va, vz = _qdelta(a, b), _qdelta(y, z)
        tangent = tuple(.5*(x+y) for x, y in zip(va, vz))
        second = _qmul(_qexp(tangent), seam)
        penultimate = _qmul(_qexp(tuple(-x for x in tangent)), seam)
        c0, c1 = _qdelta(a, seam), _qdelta(b, second)
        cn, cm = _qdelta(z, seam), _qdelta(y, penultimate)
        left = [_correction_curve(x, y, width) for x, y in zip(c0, c1)]
        right = [_correction_curve(x, y, width) for x, y in zip(cn, cm)]
        for j in range(width+1):
            for k, correction in ((j, left), (-1-j, right)):
                q = _qmul(_qexp(tuple(c[j] for c in correction)), _qrow(rows[k], group))
                for i, value in zip(group, _unit_quaternion(q)):
                    output[k][i] = value
        # Keep equivalent signs continuous, including an odd full turn where
        # the closing endpoint can legitimately be -q0 instead of q0.
        previous = None
        for row in output:
            q = _qrow(row, group)
            if previous is not None and sum(x*y for x, y in zip(q, previous)) < 0:
                q = tuple(-x for x in q)
            for i, value in zip(group, q):
                row[i] = value
            previous = q
    return output


def _activity(profile, rows, period, excluded=()):
    from .motion_import import _quaternion_groups
    groups = _quaternion_groups(profile)
    qindices = {i for group in groups for i in group}
    contributions = []
    for group in groups:
        contributions.append(math.fsum(_norm(_qdelta(_qrow(a, group), _qrow(b, group)))
                                       for a, b in zip(rows, rows[1:]))/period)
    for i, ch in enumerate(profile.channels):
        if i in qindices or i in excluded or ch.interpolation == "step":
            continue
        contributions.append(math.fsum(abs(b[i]-a[i]) for a, b in zip(rows, rows[1:])) /
                             ((ch.maximum-ch.minimum)*period))
    # Fixed channels contribute zero. A sum preserves the same denominator
    # before/after repair: cancelling root slip cannot accidentally double an
    # unchanged arm's average by removing one member of an "active" set.
    return math.fsum(contributions)


def _correction_metrics(profile, before, after, scale):
    from .motion_import import _quaternion_groups
    groups = _quaternion_groups(profile)
    qindices = {i for group in groups for i in group}
    locations = _groups(profile, "location")
    lindices = {i for group in locations.values() for i in group.values()}
    angle_max, distance_max, scalar_max, squares = 0., 0., 0., []
    for a, b in zip(before, after):
        for group in groups:
            angle = _norm(_qdelta(_qrow(a, group), _qrow(b, group)))
            angle_max = max(angle_max, angle)
            squares.append((angle/math.pi)**2)
        for group in locations.values():
            distance = _norm(b[i]-a[i] for i in group.values())
            distance_max = max(distance_max, distance)
            squares.append((distance/(scale or 1.))**2)
        for i, channel in enumerate(profile.channels):
            if i in qindices or i in lindices or channel.interpolation == "step":
                continue
            delta = abs(b[i]-a[i])
            value = delta/(channel.maximum-channel.minimum)
            scalar_max = max(scalar_max, value)
            if channel.data_path == "rotation_euler":
                angle_max = max(angle_max, delta)
            squares.append(value*value)
    return dict(max_rotation_radians=angle_max, max_translation=distance_max,
                max_translation_fraction=distance_max/(scale or 1.),
                max_scalar_fraction=scalar_max,
                rms_fraction=math.sqrt(math.fsum(squares)/max(1, len(squares))))


def _contact_rows(world, contacts, source_start, scale, options, anchors=None):
    """Measure only the supplied intervals; no automatic foot-name inference."""
    import numpy as np
    entries, constraints, reasons = [], {}, []
    anchors = {} if anchors is None else dict(anchors)
    for ordinal, contact in enumerate(contacts):
        if contact.bone not in world.bone_names:
            reasons.append("unknown_contact_bone")
            continue
        indices = np.flatnonzero((world.frame_times_seconds+source_start >= contact.start_seconds-1e-9) &
                                 (world.frame_times_seconds+source_start <= contact.end_seconds+1e-9))
        if len(indices) < 2:
            reasons.append("insufficient_contact_samples")
            continue
        positions = world.positions[indices, world.bone_names.index(contact.bone)]
        anchor = np.asarray(anchors.get(ordinal, contact.anchor_position
                            if contact.anchor_position is not None else positions[0]), dtype=float)
        anchors[ordinal] = tuple(float(x) for x in anchor)
        distances = np.linalg.norm(positions-anchor, axis=1)
        speeds = np.linalg.norm(np.diff(positions, axis=0), axis=1)/np.diff(world.frame_times_seconds[indices])
        slip, speed = float(distances.max()), float(speeds.max())
        entries.append(dict(bone=contact.bone, source_start_seconds=contact.start_seconds,
                            source_end_seconds=contact.end_seconds, sample_count=len(indices),
                            anchor_position=list(anchors[ordinal]), max_slip=slip,
                            max_speed=speed, max_slip_fraction=slip/scale,
                            max_speed_fraction_per_second=speed/scale))
        for frame, pos in zip(indices, positions):
            constraints.setdefault(int(frame), []).append(anchor-pos)
    return entries, constraints, anchors, reasons


def _stabilize_contacts(capture, rows, times, source_start, contacts, root, scale, options, anchors):
    """Root-only least-squares correction; impossible multi-foot constraints fail."""
    import numpy as np
    try:
        draft = RigCapture(capture.profile, times, rows)
    except ScoreError as exc:
        return rows, {"structural_error": str(exc)}, ["corrected_capture_outside_profile_contract"]
    world, error = _world(draft)
    if world is None:
        return rows, {}, ["contacts_require_portable_world_evaluation"]
    before, constraints, anchors, reasons = _contact_rows(world, contacts, source_start, scale, options, anchors)
    if reasons or not constraints:
        return rows, {"before": before}, reasons or ["no_contact_constraints"]
    indices = _groups(capture.profile, "location").get(root, {})
    if set(indices) != {0, 1, 2} or root != world.bone_names[world.root_index]:
        return rows, {"before": before}, ["contact_stabilization_requires_complete_root_translation"]
    targets = {}
    for frame, deltas in constraints.items():
        mean = np.mean(deltas, axis=0)
        if any(np.linalg.norm(delta-mean) > options.max_contact_slip_fraction*scale for delta in deltas):
            return rows, {"before": before}, ["conflicting_foot_contacts"]
        targets[frame] = mean
    known = sorted(targets)
    shifts = np.column_stack([np.interp(np.arange(len(rows)), known,
                                       [targets[k][axis] for k in known]) for axis in range(3)])
    # Express a world displacement in the saved root rest basis, never assume
    # source axes or metres. Close the shift itself so adding it preserves C1.
    rest = world.rest_matrices[world.root_index][:3, :3]
    local = shifts @ np.linalg.inv(rest).T
    shift_rows = [[0.]*len(capture.profile.channels) for _ in rows]
    for row, delta in zip(shift_rows, local):
        for axis, channel in indices.items():
            row[channel] = float(delta[axis])
    # Scalars only here: quaternion columns must remain valid unit rotations.
    for row in shift_rows:
        for group in capture._quaternions:
            row[group[0]] = 1.
    closed = _close_rows(capture.profile, shift_rows, options.blend_fraction)
    correction = max(_norm(row[i] for i in indices.values()) for row in closed)
    if correction > options.max_contact_root_correction_fraction*scale:
        return rows, {"before": before, "max_root_correction": correction}, ["contact_root_correction_limit"]
    output = [list(row) for row in rows]
    for row, delta in zip(output, closed):
        for i in indices.values():
            row[i] += delta[i]
    return output, {"before": before, "anchors": anchors, "max_root_correction": correction}, []


def repair_loop(capture, *, start_seconds, end_seconds, options=None, contacts=()):
    """Return a new closed capture only when the declared correction gates pass.

    Output seconds are local ``[0, period]`` including a closing endpoint; compile
    downstream to a half-open number of beats at 64 pips per beat. No source is
    edited and no runtime wrapping is enabled. Invalid API inputs raise
    ``ScoreError``; a valid but unrepairable window returns a rejected report.
    """
    options = LoopRepairOptions() if options is None else options
    if not isinstance(options, LoopRepairOptions):
        raise ScoreError("options must be LoopRepairOptions")
    if not isinstance(contacts, (tuple, list)) or any(not isinstance(c, FootContact) for c in contacts):
        raise ScoreError("contacts must be a sequence of FootContact annotations")
    if len(contacts) > 4096:
        raise ScoreError("Contact annotations exceed the bounded interval budget")
    rows, times = _resample_window(capture, start_seconds, end_seconds, options.sample_count)
    period = times[-1]
    # Keep the original world anchor/evidence while clipping the constraint's
    # temporal domain. A point contact outside this window is not a stance.
    selected_contacts = tuple(replace(c, start_seconds=max(float(start_seconds), c.start_seconds),
                                     end_seconds=min(float(end_seconds), c.end_seconds))
                              for c in contacts if min(float(end_seconds), c.end_seconds) -
                              max(float(start_seconds), c.start_seconds) >= period/(len(rows)-1))
    if len(selected_contacts) > 256:
        raise ScoreError("At most 256 overlapping stance intervals may constrain one repair")
    original = [list(row) for row in rows]
    extracted = RigCapture(capture.profile, times, rows)
    world, world_error = _world(extracted)
    scale = options.translation_scale or (float(world.body_scale) if world is not None else None)
    root = options.root_bone or (world.bone_names[world.root_index] if world is not None else None)
    report = dict(format=FORMAT, schema_version=1, method=METHOD, accepted=False,
                  status="rejected", rejection_reasons=[], source_capture_sha256=capture.fingerprint,
                  source_profile_sha256=capture.profile.fingerprint,
                  source_start_seconds=float(start_seconds), source_end_seconds=float(end_seconds),
                  period_seconds=period, sample_count=len(rows), options=asdict(options),
                  translation_scale=scale, world_evaluation_available=world is not None,
                  world_evaluation_unavailable_reason=world_error,
                  root_bone=root, root_travel_removed=[0., 0., 0.],
                  before=_diagnostics(capture.profile, rows, period, scale), after=None,
                  corrections=None, contacts={"provided_count": len(selected_contacts), "verified": False,
                      "constraints_satisfied": False, "foot_plant_verified": False,
                      "evidence_status": "supplied_constraints" if selected_contacts else "unavailable"},
                  requires_review=True, audio_beat_alignment_verified=False,
                  loop_seam_approved=False, target_mesh_verified=False)
    reasons = report["rejection_reasons"]

    def rejected(reason):
        if reason not in reasons:
            reasons.append(reason)
        return LoopRepairResult(None, report)

    if not report["before"]["discrete_seam_matches"]:
        return rejected("discrete_selector_seam_mismatch")
    if options.require_contacts and not selected_contacts:
        return rejected("foot_contact_evidence_required")
    if selected_contacts:
        if world is None:
            return rejected("contacts_require_portable_world_evaluation")
        details, _, anchors, failures = _contact_rows(world, selected_contacts, start_seconds, scale, options)
        report["contacts"].update(before=details, anchors=anchors,
                                  evidence_types=sorted({c.evidence for c in selected_contacts}))
        if failures:
            reasons.extend(failures)
            return LoopRepairResult(None, report)
    root_indices = _groups(capture.profile, "location").get(root, {})
    if options.root_policy == "in_place":
        if set(root_indices) != {0, 1, 2}:
            return rejected("in_place_requires_explicit_complete_root_translation")
        for axis in options.root_axes:
            index = root_indices[axis]
            travel = rows[-1][index]-rows[0][index]
            report["root_travel_removed"][axis] = travel
            for j, row in enumerate(rows):
                row[index] -= travel*j/(len(rows)-1)
    activity_reference = _activity(capture.profile, rows, period)
    report["activity_before"] = activity_reference
    if activity_reference < options.min_activity:
        return rejected("insufficient_meaningful_motion")
    rows = _close_rows(capture.profile, rows, options.blend_fraction)
    if selected_contacts:
        if world is None:
            return rejected("contacts_require_portable_world_evaluation")
        if options.contact_policy == "root_stabilize":
            rows, details, failures = _stabilize_contacts(capture, rows, times, start_seconds,
                                                         selected_contacts, root, scale, options,
                                                         report["contacts"].get("anchors"))
            report["contacts"].update({k: v for k, v in details.items() if k != "before"})
            report["contacts"]["before_stabilization"] = details.get("before")
            if failures:
                reasons.extend(failures)
                return LoopRepairResult(None, report)
    report["corrections"] = _correction_metrics(capture.profile, original, rows, scale)
    changes = report["corrections"]
    if scale is None and changes["max_translation"] > options.closure_tolerance:
        reasons.append("translation_scale_required")
    for measured, limit, reason in (
            (changes["max_rotation_radians"], options.max_rotation_correction_radians, "rotation_correction_limit"),
            (changes["max_translation_fraction"], options.max_translation_correction_fraction, "translation_correction_limit"),
            (changes["max_scalar_fraction"], options.max_scalar_correction_fraction, "scalar_correction_limit"),
            (changes["rms_fraction"], options.max_correction_rms_fraction, "rms_correction_limit")):
        if measured > limit:
            reasons.append(reason)
    activity_after = _activity(capture.profile, rows, period)
    report["activity_after"] = activity_after
    report["activity_retention"] = activity_after/activity_reference
    if not options.min_activity_retention <= report["activity_retention"] <= options.max_activity_increase:
        reasons.append("activity_retention_limit")
    if activity_after < options.min_activity:
        reasons.append("insufficient_repaired_motion")
    try:
        checked = RigCapture(capture.profile, times, rows)
    except ScoreError as exc:
        report["structural_error"] = str(exc)
        return rejected("corrected_capture_outside_profile_contract")
    after = report["after"] = _diagnostics(capture.profile, checked.frames, period, scale)
    if (after["max_rotation_seam_radians"] > options.closure_tolerance or
            after["max_translation_seam"]/(scale or 1.) > options.closure_tolerance or
            after["max_scalar_seam_fraction"] > options.closure_tolerance or
            not after["discrete_seam_matches"]):
        reasons.append("residual_pose_seam")
    if period * max(after["max_rotation_velocity_jump_radians_per_second"],
                    after["max_translation_velocity_jump"]/(scale or 1.),
                    after["max_scalar_velocity_jump_fraction_per_second"]) > options.tangent_tolerance:
        reasons.append("residual_velocity_seam")
    if selected_contacts:
        corrected_world, error = _world(checked)
        if corrected_world is None:
            return rejected("corrected_world_evaluation_failed")
        details, _, _, failures = _contact_rows(corrected_world, selected_contacts, start_seconds,
                                                scale, options, report["contacts"].get("anchors"))
        report["contacts"]["after"] = details
        reasons.extend(failures)
        if any(item["max_slip_fraction"] > options.max_contact_slip_fraction or
               item["max_speed_fraction_per_second"] > options.max_contact_speed_fraction_per_second
               for item in details):
            reasons.append("foot_contact_slip_limit")
        report["contacts"]["constraints_satisfied"] = not failures and "foot_contact_slip_limit" not in reasons
    if reasons:
        return LoopRepairResult(None, report)
    report["accepted"] = True
    report["status"] = "numerically_closed_review_candidate"
    report["repair_id"] = hashlib.sha256(canonical_json(dict(source=capture.fingerprint,
        start=start_seconds, end=end_seconds, options=asdict(options),
        contacts=[asdict(c) for c in selected_contacts])).encode("ascii")).hexdigest()
    provenance = dict(producer="dancerudiments.offline-loop-repair", source_capture_sha256=capture.fingerprint,
                      source_profile_sha256=capture.profile.fingerprint, source_provenance=capture.provenance,
                      repair=report, loop_policy="closed_endpoint_capture_for_half_open_compilation")
    result = RigCapture(capture.profile, times, checked.frames, canonical_json(provenance))
    # This hash lives in the external report to avoid a self-referential digest.
    report["corrected_capture_sha256"] = result.fingerprint
    return LoopRepairResult(result, report)


def propose_loop_repairs(capture, *, bpm, beat_zero_seconds=0., beat_counts=(4, 8, 16),
                         max_candidates=6, max_windows=128, options=None, contacts=()):
    """Rank bounded beat-aligned windows, then attempt at most max_candidates.

    This explicit *repair* catalogue is independent of unmodified seam-finder
    acceptance. A supplied BPM remains a hypothesis. Results include rejected
    attempts and must never be relabelled as accepted raw source loops.
    """
    bpm = _real(bpm, "bpm", minimum=30., maximum=300.)
    zero = _real(beat_zero_seconds, "beat_zero_seconds", minimum=-1e12, maximum=1e12)
    if type(max_candidates) is not int or not 1 <= max_candidates <= 24:
        raise ScoreError("max_candidates must be 1..24")
    if type(max_windows) is not int or not max_candidates <= max_windows <= 128:
        raise ScoreError("max_windows must be max_candidates..128")
    if (not isinstance(beat_counts, (tuple, list)) or not beat_counts
            or any(type(n) is not int or n not in (1, 2, 4, 8, 16, 32) for n in beat_counts)
            or len(set(beat_counts)) != len(beat_counts)):
        raise ScoreError("beat_counts must contain unique supported integer counts")
    options = LoopRepairOptions() if options is None else options
    if not isinstance(options, LoopRepairOptions) or not isinstance(capture, RigCapture):
        raise ScoreError("Expected validated options and capture")
    segments = source_valid_segments(capture)
    # Rest geometry defines the ranking scale. One actual observed pose is
    # sufficient; never interpolate across the full timeline merely to get it.
    ranking_world, _ = _world(RigCapture(capture.profile,
        (capture.frame_times_seconds[0],), (capture.frames[0],)))
    ranking_scale = options.translation_scale or (ranking_world.body_scale if ranking_world is not None else None)
    step = 60./bpm
    windows = []
    # Uniformly cover each length's eligible source windows, excluding timestamp
    # holes before allocating the bounded candidate budget. No beat-sized array
    # is allocated for an arbitrarily long source recording.
    allowance = max(1, max_windows//len(beat_counts))
    for beats in beat_counts:
        ranges = []
        for first, last in segments:
            low = math.ceil((first-zero)/step-1e-10)
            high = math.floor((last-zero)/step-beats+1e-10)
            if high >= low:
                ranges.append((low, high))
        total = sum(high-low+1 for low, high in ranges)
        if not total:
            continue
        count = min(allowance, total)
        if len(ranges) == 1:
            # Preserve the original rounding and selected windows exactly when
            # the source has one continuous eligible span.
            low, high = ranges[0]
            starts = {low if count == 1 else round(low+i*(high-low)/(count-1)) for i in range(count)}
        else:
            selected = {0 if count == 1 else round(i*(total-1)/(count-1)) for i in range(count)}
            starts = set()
            cursor = 0
            for low, high in ranges:
                width = high-low+1
                starts.update(low+index-cursor for index in selected if cursor <= index < cursor+width)
                cursor += width
        for offset in sorted(starts):
            start, end = zero+offset*step, zero+(offset+beats)*step
            if not any(first <= start < end <= last for first, last in segments):
                continue
            rows, times = _resample_window(capture, start, end, min(options.sample_count, 33),
                                          _valid_segments=segments)
            if _activity(capture.profile, rows, times[-1]) < options.min_activity:
                continue
            seam = _diagnostics(capture.profile, rows, times[-1], ranking_scale)
            if seam["discrete_seam_matches"]:
                windows.append((seam["rank_cost"], start, end, beats))
    results = []
    for rank, (cost, start, end, beats) in enumerate(sorted(windows)[:max_candidates], 1):
        # Measure the very same seam tangent that a native half-open loop will
        # have: each inclusive authoring sample is exactly one output pip.
        native_options = replace(options, sample_count=beats*64+1)
        result = repair_loop(capture, start_seconds=start, end_seconds=end,
                             options=native_options, contacts=contacts)
        result.report["proposal"] = dict(rank=rank, initial_seam_cost=cost, bpm=bpm,
                                         beat_zero_seconds=zero, beats=beats,
                                         source_grid_status="supplied_hypothesis_unverified",
                                         windows_ranked=len(windows), attempts_limit=max_candidates)
        results.append(result)
    return tuple(sorted(results, key=lambda item: (not item.accepted, item.report["proposal"]["rank"])))


def verify_compiled_loop_seam(motion, corrected_capture, repair_report):
    """Check actual half-open compiled rows, identities, wrap tangent and contacts.

    This is an offline verification of the final normalized Recording payload.
    Native execution parity remains the existing compiler's independent check.
    A failed result must not be exported as a verified corrected loop.
    """
    from .motion import RigMotion
    if not isinstance(motion, RigMotion) or not isinstance(corrected_capture, RigCapture):
        raise ScoreError("Compiled loop verification requires RigMotion and RigCapture")
    if (not isinstance(repair_report, dict) or repair_report.get("format") != FORMAT
            or repair_report.get("accepted") is not True):
        raise ScoreError("Compiled loop verification requires an accepted repair report")
    result = dict(format="dancerudiments.compiled-loop-check", schema_version=1,
                  passed=False, rejection_reasons=[],
                  method="all_decoded_samples_and_half_open_wrap_v1",
                  compiled_motion_fingerprint=motion.fingerprint,
                  corrected_capture_sha256=corrected_capture.fingerprint,
                  native_execution_verified=False, loop_seam_approved=False)
    reasons = result["rejection_reasons"]
    original_report = corrected_capture.provenance.get("repair", {})
    provenance = motion.recording.provenance
    if (motion.profile.fingerprint != corrected_capture.profile.fingerprint
            or repair_report.get("source_profile_sha256") != corrected_capture.profile.fingerprint
            or repair_report.get("corrected_capture_sha256") != corrected_capture.fingerprint
            or provenance.get("source_capture_sha256") != corrected_capture.fingerprint
            or repair_report.get("repair_id") != original_report.get("repair_id")
            or repair_report.get("source_capture_sha256") !=
            corrected_capture.provenance.get("source_capture_sha256")):
        reasons.append("compiled_repair_identity_mismatch")
        return result
    if (len(motion.recording.samples) != len(corrected_capture.frames)-1
            or motion.recording.clock.start_pip != 0):
        reasons.append("compiled_half_open_extent_mismatch")
        return result
    options = LoopRepairOptions(**repair_report["options"])
    period = float(repair_report["period_seconds"])
    if (corrected_capture.frame_times_seconds[0] != 0. or period <= 0 or
            abs(corrected_capture.frame_times_seconds[-1]-period) > 1e-10):
        reasons.append("compiled_repair_clock_mismatch")
        return result
    rows = [motion.profile.decode(row) for row in motion.recording.samples]
    qindices = {i for group in corrected_capture._quaternions for i in group}
    scalar_error, rotation_error = 0., 0.
    for expected, actual in zip(corrected_capture.frames, rows):
        for group in corrected_capture._quaternions:
            rotation_error = max(rotation_error, _norm(_qdelta(_qrow(expected, group), _qrow(actual, group))))
        for i, channel in enumerate(motion.profile.channels):
            if i not in qindices:
                scalar_error = max(scalar_error, abs(actual[i]-expected[i])/(channel.maximum-channel.minimum))
    result.update(max_normalized_scalar_sample_error=scalar_error,
                  max_rotation_sample_error_radians=rotation_error)
    if scalar_error > 2e-10 or rotation_error > 1e-8:
        reasons.append("compiled_samples_differ_from_corrected_capture")
    # Append the first *encoded and decoded* row, exactly as an explicit host
    # repeat will do. Do not verify the omitted source endpoint instead.
    wrapped = rows + [rows[0]]
    scale = repair_report.get("translation_scale")
    after = _diagnostics(motion.profile, wrapped, period, scale)
    result["after"] = after
    if not after["discrete_seam_matches"]:
        reasons.append("compiled_discrete_selector_seam")
    if period * max(after["max_rotation_velocity_jump_radians_per_second"],
                    after["max_translation_velocity_jump"]/(scale or 1.),
                    after["max_scalar_velocity_jump_fraction_per_second"]) > options.tangent_tolerance:
        reasons.append("compiled_velocity_seam")
    contact_evidence = repair_report.get("contacts", {})
    if contact_evidence.get("constraints_satisfied"):
        capture = RigCapture(motion.profile, corrected_capture.frame_times_seconds, wrapped)
        world, error = _world(capture)
        if world is None:
            result["world_evaluation_error"] = error
            reasons.append("compiled_contact_evaluation_unavailable")
        else:
            constraints = tuple(FootContact(item["bone"], item["source_start_seconds"],
                item["source_end_seconds"], item["anchor_position"])
                for item in contact_evidence.get("before", ()))
            details, _, _, failures = _contact_rows(world, constraints,
                repair_report["source_start_seconds"], scale, options)
            result["contacts"] = details
            reasons.extend(failures)
            if not constraints or any(
                    item["max_slip_fraction"] > options.max_contact_slip_fraction or
                    item["max_speed_fraction_per_second"] > options.max_contact_speed_fraction_per_second
                    for item in details):
                reasons.append("compiled_foot_contact_slip_limit")
    result["passed"] = not reasons
    return result
