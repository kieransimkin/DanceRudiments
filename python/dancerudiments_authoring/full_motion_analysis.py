"""Source-time BPM/beat-fit evidence for complete rig Actions.

This is an auditable *heuristic fit* (0..1), NOT a statistically calibrated
probability or verification of musical BPM, meter, downbeat, tempo constancy,
foot contact or final target-mesh quality. StemLab remains the beat inference
engine; this evaluates whether its hypotheses describe the *whole* performance.
No compiled Recording, GPU model or machine-learning dependency is needed.
"""
from __future__ import annotations

import math

METHOD = 'dancerudiments.full-motion-grid-fit.v1'
DEFAULT_THRESHOLD = .70


def _number(value, default=0.0):
    return (float(value) if type(value) in (int, float) and math.isfinite(value)
            else default)


def _limit(value):
    return max(0.0, min(1.0, value))


def _score_hypothesis(item, accents, start, end):
    """Score periodicity, phase agreement, source-wide coverage and bone support.

    Scores describe original motion only. Accent alignment is a *soft* score,
    since a foot can strike just before or after the inferred musical beat.
    """
    bpm = _number(item.get('bpm'))
    zero = _number(item.get('beat_zero_seconds'), float('nan'))
    if not 30 <= bpm <= 300 or not math.isfinite(zero):
        return None
    duration = end - start
    period = 60.0 / bpm
    beat_count = duration / period
    if beat_count < 4:
        return None
    periodicity = _limit(_number(item.get('group_periodicity')))
    pooled = _limit(_number(item.get('autocorrelation')))
    # Agreement between a bone group's period and the pooled signal is an
    # independent guard against one intermittent moving control dominating.
    periodicity = .75 * periodicity + .25 * pooled
    phase_contrast = _limit(_number(item.get('phase_contrast')))
    active = item.get('active_control_groups', 0)
    supporting = item.get('supporting_control_groups', 0)
    if type(active) is not int or type(supporting) is not int or active < 0 or supporting < 0:
        return None
    support = _limit(supporting / max(2, min(4, active)))
    useful = sorted((t, strength) for t, strength in accents if start <= t <= end)
    if useful:
        def alignment(t):
            phase = ((t - zero + period * .5) % period - period * .5) / period
            return math.exp(-.5 * (phase / .22)**2)
        denom = sum(w for _, w in useful)
        grid_fit = sum(alignment(t)*w for t, w in useful) / denom if denom > 0 else 0
    else:
        grid_fit = 0.
    # At least one aligned accented event must recur in each four-beat window
    # over the entire Action. This prevents an excellent eight-beat passage at
    # the beginning being treated as a fit for a long, unrelated performance.
    segments = max(1, min(64, math.ceil(beat_count / 4)))
    occupied = set()
    for t, strength in useful:
        phase = abs(((t - zero + period*.5) % period - period*.5) / period)
        if strength >= .10 and phase <= .28:
            occupied.add(min(segments-1, int((t-start)*segments/duration)))
    coverage = len(occupied) / segments
    repetitions = _limit(beat_count / 12)
    raw = (_limit(periodicity) * .28 + _limit(grid_fit) * .19 +
           coverage * .15 + support * .15 + phase_contrast * .13 + repetitions * .10)
    notes = []
    if active < 2 or supporting < 2:
        notes.append('insufficient_independent_control_support')
        raw = min(raw, .69)
    if len(useful) < 8:
        notes.append('insufficient_motion_accents')
        raw = min(raw, .69)
    if coverage < .50:
        notes.append('weak_whole_action_coverage')
        raw = min(raw, .69)
    if phase_contrast < .06:
        notes.append('uncertain_beat_phase')
        raw = min(raw, .69)
    if periodicity < .25:
        notes.append('weak_periodic_evidence')
        raw = min(raw, .69)
    return dict(bpm=round(bpm, 5), beat_zero_seconds=round(zero, 6),
                fit_score=round(_limit(raw), 4),
                components={key: round(_limit(val), 4) for key, val in (
                    ('periodicity', periodicity), ('accent_grid_alignment', grid_fit),
                    ('whole_action_coverage', coverage), ('independent_control_support', support),
                    ('phase_contrast', phase_contrast), ('duration_support', repetitions))},
                supporting_control_groups=supporting, active_control_groups=active,
                accent_count=len(useful), notes=notes,
                stemlab_rank_score=_number(item.get('score')),
                metrical_relation_to_top=item.get('metrical_relation_to_top', 'unknown'))


def assess_full_motion(report, capture, *, confidence_threshold=DEFAULT_THRESHOLD):
    """Rank StemLab tempo hypotheses, but auto-select only its validated primary.

    A 70% policy is 0.70 on this *heuristic scale*, not a 70% probability.
    Alternative half/double tempi remain visible; we do not silently pick a
    different downbeat/metrical level or treat a song's target BPM as evidence.
    """
    if type(confidence_threshold) not in (int, float) or not math.isfinite(confidence_threshold) or not 0 <= confidence_threshold <= 1:
        raise ValueError('Full-motion confidence threshold must be within 0..1')
    times = capture.frame_times_seconds
    start, end = float(times[0]), float(times[-1])
    result = dict(method=METHOD, confidence_interpretation='uncalibrated_kinematic_fit_not_probability',
                  threshold=round(float(confidence_threshold), 4),
                  source_start_seconds=start, source_end_seconds=end,
                  musical_beat_alignment_verified=False, source_bpm_status='estimated',
                  auto_convert=False, confidence=0.0, confidence_percent=0.0,
                  selected_bpm=None, selected_beat_zero_seconds=None,
                  tempo_hypotheses=[], reasons=[])
    primary = report.get('recommended_tempo')
    if not isinstance(primary, dict):
        result['reasons'].append('no_supported_stemlab_tempo')
        return result
    grid = report.get('estimated_beat_map')
    # The primary source-time grid is an immutable input to authoring. Never
    # accept a missing, confirmed or unrelated report as an analysis authority.
    if (not isinstance(grid, dict) or grid.get('format') != 'dancerudiments.beat-map'
            or grid.get('bpm_status') != 'estimated' or grid.get('phase_status') != 'estimated'
            or grid.get('extrapolate') is not False
            or not isinstance(grid.get('source'), str)
            or not isinstance(report.get('source_file_sha256'), str)
            or report['source_file_sha256'] not in grid['source']
            or not isinstance(grid.get('anchors'), list) or len(grid['anchors']) < 2):
        result['reasons'].append('missing_or_inconsistent_source_beat_map')
        return result
    try:
        a, b = grid['anchors'][:2]
        inferred_bpm = 60 * (b['beat']-a['beat']) / (b['seconds']-a['seconds'])
        if (not math.isfinite(inferred_bpm) or abs(inferred_bpm - _number(primary.get('bpm'))) >
                max(1.0, .02 * _number(primary.get('bpm')))):
            result['reasons'].append('source_beat_map_tempo_mismatch')
            return result
    except (KeyError, TypeError, ZeroDivisionError, ValueError):
        result['reasons'].append('malformed_source_beat_map')
        return result
    accents = []
    for item in report.get('motion_accents', ()):
        if not isinstance(item, dict):
            continue
        t = _number(item.get('seconds'), float('nan'))
        w = _number(item.get('strength'))
        if math.isfinite(t) and w > 0:
            accents.append((t, _limit(w)))
    proposals = [primary] + [x for x in report.get('bpm_candidates', ())
                             if isinstance(x, dict) and x is not primary
                             and _number(x.get('bpm')) != _number(primary.get('bpm'))]
    scored = [x for x in (_score_hypothesis(proposal, accents, start, end)
                           for proposal in proposals[:9]) if x is not None]
    result['tempo_hypotheses'] = scored
    if not scored:
        result['reasons'].append('no_valid_bpm_hypothesis')
        return result
    best = scored[0]
    confidence = best['fit_score']
    for other in scored[1:]:
        ratio = other['bpm'] / best['bpm']
        if ((abs(ratio-.5) < .06 or abs(ratio-2) < .12)
                and other['fit_score'] >= best['fit_score']*.75):
            result['reasons'].append('metrical_half_double_time_ambiguity')
            confidence = max(0., confidence-.06)
            break
    result['confidence'] = round(confidence, 4)
    result['confidence_percent'] = round(confidence * 100, 2)
    result['selected_bpm'] = best['bpm']
    result['selected_beat_zero_seconds'] = best['beat_zero_seconds']
    result['reasons'].extend(best['notes'])
    result['auto_convert'] = confidence >= confidence_threshold and not best['notes']
    if not result['auto_convert']:
        result['reasons'].append('below_full_length_conversion_threshold')
    return result
