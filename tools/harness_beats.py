"""Collect the frozen beat/event scores for the full HTML harness.

No re-transcription, network access, native extension or floating-point recipe
regeneration. Musical times stay rational until the browser schedules them.
"""
from __future__ import annotations

from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
GM = {"kick": 36, "snare": 38, "clap": 39, "rim": 37, "hat": 42,
      "open_hat": 46, "pedal_hat": 44, "shaker": 70, "tom": 45,
      "ride": 51, "crash": 49, "bell": 56, "bass": 36}
CORE_STROKES = ("single_stroke_roll", "double_stroke_roll", "multiple_bounce_roll",
                "single_paradiddle", "flam", "drag", "five_stroke_roll")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def fraction(value):
    if type(value) is bool:
        raise ValueError("Boolean musical time")
    value = Fraction(str(value))
    if abs(value) > 65535:
        raise ValueError("Musical time out of range")
    return value


def instrument(gesture, gestures):
    """Explicit audition timbres, not a claim that an abstract lane was a drum."""
    if gesture in GM:
        return GM[gesture], 0 if gesture == "bass" else 9
    aliases = {"l": 37, "left": 37, "r": 38, "right": 38, "up": 50,
               "down": 45, "near": 43, "far": 47, "hit": 38, "ratchet": 38}
    if gesture in aliases:
        return aliases[gesture], 9
    notes = (36, 38, 42, 45, 50, 37, 39, 56, 75, 54, 51, 46)
    return notes[sorted(gestures).index(gesture) % len(notes)], 9


def event(beat, lane, velocity, note, channel=9, duration="1/16"):
    if not math.isfinite(float(velocity)) or not 0 < float(velocity) <= 1:
        raise ValueError("Invalid source velocity")
    return dict(beat=str(fraction(beat)), lane=lane, velocity=float(velocity),
                note=int(note), channel=int(channel), duration=str(fraction(duration)))


def collect(root=ROOT):
    root = Path(root)
    beats = {}
    references = {}
    inputs = {}
    linked = {}
    lock = json.loads((root / "collections/defaults.json").read_text(encoding="utf-8"))
    required = {n for c in lock["collections"] for n in c["patterns"]}

    def read(path):
        raw = path.read_bytes()
        # The builder consumes parsed canonical JSON; source checksums record
        # the file, not a recalculated platform-dependent curve.
        inputs[path.relative_to(root).as_posix()] = sha256(raw).hexdigest()
        return json.loads(raw)

    # Every persisted rhythm document is discovered, including future collections.
    for path in sorted((root / "collections").glob("*/rhythms.json")):
        doc = read(path)
        source_file = path.with_name("sources.json")
        if source_file.exists():
            source = read(source_file)
            source = source.get("sources", source) if isinstance(source, dict) else source
            if isinstance(source, dict):
                references.update(source)
        for r in doc.get("rhythms", []):
            identity = r["id"]
            if identity in beats:
                if beats[identity]["source_score"] != r:
                    raise ValueError("Conflicting shared rhythm: " + identity)
                continue
            events = [event(e["beat"], e["lane"], e["velocity"],
                            (e.get("note") or 36) if e["lane"] == "bass" else GM[e["lane"]],
                            0 if e["lane"] == "bass" else 9,
                            e.get("duration", "1/4" if e["lane"] == "bass" else "1/16"))
                      for e in r["events"]]
            beats[identity] = dict(id=identity, title=r["title"], family=r["genre"], kind="dance",
                                  period_beats=r["period_beats"], bpm=r["bpm"],
                                  meter=r.get("meter"), notes=r.get("notes", ""),
                                  license="MIT", source_score=r, source_path=path.relative_to(root).as_posix(),
                                  reference_ids=r.get("reference_ids", []), events=events)

    for source in lock["collections"]:
        pack = read(root / source["pack"])
        for p in pack["patterns"]:
            if p["name"] not in required:
                continue
            rid = p.get("provenance", {}).get("rhythm_id")
            if rid:
                if rid not in beats:
                    raise ValueError("Movement references a missing beat: " + p["name"])
                linked[p["name"]] = rid

    # The earlier L/R, Euclidean, poly/additive, and Groove MIDI event studies.
    for path in sorted((root / "collections").glob("*/*.score.json")):
        doc = read(path)
        for p in doc.get("patterns", []):
            if p["name"] not in required or p["name"] in linked or not p.get("events"):
                continue
            period = fraction(p["period_beats"])
            if period <= 0:
                raise ValueError("Invalid event-score period")
            gestures = p.get("gestures", {})
            meta = p.get("provenance", {})
            markers = meta.get("event_markers", [])
            converted = []
            for event_index, e in enumerate(p["events"]):
                lane = e["gesture"]
                note, channel = instrument(lane, gestures)
                # Groove provenance retains per-hit cymbal/hat articulation even
                # where the visual gesture intentionally groups those together.
                if p["name"].startswith("groove_") and len(markers) == len(p["events"]):
                    marker = markers[event_index]
                    if fraction(marker["beat"]) % period != fraction(e["beat"]) % period:
                        raise ValueError("Groove marker/onset mismatch")
                    recorded_note = marker.get("note")
                    if recorded_note in GM.values():
                        note = recorded_note
                    elif lane == "hat" and recorded_note in (22, 26):
                        note = 42 if recorded_note == 22 else 46
                # Do not move onset/peak/end anchor timestamps. They have the
                # meaning recorded in the original score, described below.
                converted.append(event(fraction(e["beat"]) % period, lane, e.get("strength", 1), note, channel))
            meta = p.get("provenance", {})
            rid = "score_" + p["name"]
            is_groove = p["name"].startswith("groove_")
            notes = ("Original scored drum onsets, including the retained played/quantised timing." if is_groove else
                     "Audition of abstract event lanes: timbres are assigned for listening, not recorded instruments. "
                     "Each MIDI onset uses the score's event timestamp; onset/peak/end gesture anchors remain as authored.")
            beats[rid] = dict(id=rid, title=meta.get("title", p["name"]), family=meta.get("family", "Event studies"),
                              kind="groove" if is_groove else "events", period_beats=str(period),
                              bpm=meta.get("bpm", 80 if is_groove else 120), meter=None,
                              notes=notes, license=meta.get("license", "MIT"), provenance=meta,
                              source_path=path.relative_to(root).as_posix(), source_score_sha256=sha256(canonical(p).encode()).hexdigest(),
                              events=converted)
            linked[p["name"]] = rid

    # Read (rather than duplicate) the seven original C++ sticking definitions.
    # Fail loudly if their representation changes and needs a new adapter.
    text = (root / "src/dance_rudiments.cpp").read_text(encoding="utf-8")
    for name in CORE_STROKES:
        match = re.search(r"Offset3\s+" + name + r"\(int pip\) noexcept\s*\{\s*return stroke_motion\(pip,\s*(\d+),\s*(\{\{.*?\}\})\);\s*\}", text, re.S)
        if not match:
            raise ValueError("Cannot extract the C++ stroke score: " + name)
        period_pips = int(match[1])
        strokes = re.findall(r"\{([^{}]+)\}", match[2])
        events = []
        for row in strokes:
            start, hand, strength, width = map(fraction, row.split(","))
            lane = "right" if hand > 0 else "left"
            events.append(event(start / 64, lane, float(strength), 38 if hand > 0 else 37))
        rid = "core_" + name
        beats[rid] = dict(id=rid, title=name.replace("_", " ").capitalize(), family="Original drum rudiments",
                          kind="core", period_beats=str(Fraction(period_pips, 64)), bpm=100, meter=None,
                          notes="C++ stroke-start timestamps. These legacy movement envelopes peak half a stroke-width AFTER the onset; the movements are unchanged.",
                          license="MIT", source_path="src/dance_rudiments.cpp",
                          source_score_sha256=sha256(match[0].encode()).hexdigest(), events=events)
        linked[name] = rid

    for b in beats.values():
        b["events"].sort(key=lambda e: (fraction(e["beat"]), e["channel"], e["note"]))
        b["pattern_names"] = [n for n, rid in linked.items() if rid == b["id"]]
        b["score_sha256"] = sha256(canonical([b["period_beats"], b["events"]]).encode()).hexdigest()
        b.pop("source_score", None)  # no redundant event document in the HTML
    # Note-bearing scores only: continuous wave/path recipes do not imply a drum beat.
    output = dict(format="dancerudiments.harness-beats", schema_version=1, beat_unit="quarter_note",
                  beats=list(beats.values()), pattern_beats=linked, sources=references,
                  source_hashes=inputs, coverage=dict(dance_scores=sum(b["kind"] == "dance" for b in beats.values()),
                  event_scores=sum(b["kind"] == "events" for b in beats.values()),
                  groove_scores=sum(b["kind"] == "groove" for b in beats.values()),
                  core_scores=len(CORE_STROKES), linked_movements=len(linked)))
    output["sha256"] = sha256(canonical(output).encode()).hexdigest()
    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = collect()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(canonical(result) + "\n", encoding="utf-8")
    print(json.dumps(result["coverage"], indent=2))
