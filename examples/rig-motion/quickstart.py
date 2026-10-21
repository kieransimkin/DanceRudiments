#!/usr/bin/env python3
"""Original synthetic rig capture: author, compile, and optionally sample natively."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))

from dancerudiments_authoring.io import read_json
from dancerudiments_authoring.motion import write_rig_motion
from dancerudiments_authoring.motion_clock import BeatMap
from dancerudiments_authoring.motion_import import RigCapture, compile_capture, write_capture
from dancerudiments_authoring.recording import RecordingClock, _write_json_document
from dancerudiments_authoring.rigs import RigChannel, RigProfile, rig_type_uri


def make_capture():
    """A synthetic root control, independent of Blender and external clips."""
    channels = []
    for axis, letter in enumerate("xyz"):
        channels.append(RigChannel(len(channels) + 1, "root_" + letter, "root", "location",
                                   axis, "metre", -2, 2, 0))
    for axis, letter in enumerate("wxyz"):
        channels.append(RigChannel(len(channels) + 1, "root_q" + letter, "root", "rotation_quaternion",
                                   axis, "unitless", -1, 1, 1 if axis == 0 else 0,
                                   interpolation="quaternion", rotation_mode="QUATERNION"))
    profile = RigProfile(rig_type_uri("synthetic_root", kind="custom"), "synthetic_root",
                         tuple(channels), source_json=json.dumps({
                             "description": "Original seven-channel example; not a generated Rigify model",
                             "author": "DanceRudiments", "license": "MIT"}))
    times = tuple(index / 4 for index in range(9))
    frames = []
    for time in times:
        sway = math.sin(time * math.tau)
        yaw = math.radians(30) * sway
        frames.append((0.25 * sway, 0, 0.1 * (1 - math.cos(time * math.tau)),
                       math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)))
    return RigCapture(profile, times, tuple(frames), json.dumps({
        "author": "DanceRudiments", "license": "MIT", "source": "original synthetic control motion",
        "coordinate_system": "Blender-style right-handed Z-up, metre scale"}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("generated/rig-motion"))
    parser.add_argument("--native", action="store_true", help="Also sample through the installed C++ extension")
    args = parser.parse_args(argv)
    outputs = {key: args.output / filename for key, filename in (
        ("capture", "synthetic.capture.json"), ("motion", "synthetic.motion.json"),
        ("source_beats", "source.beats.json"))}
    for path in outputs.values():
        if path.exists():
            parser.error(f"Output already exists: {path}; choose a fresh --output directory")
    capture = make_capture()
    source = BeatMap.from_bpm(120, beat_zero_seconds=0, source="synthetic musical timing",
                             bpm_status="confirmed", phase_status="supplied")
    motion = compile_capture(capture, name="synthetic_root_sway", source_beat_map=source,
                             clock=RecordingClock(120, "example presentation tempo", "confirmed",
                                                  phase_status="supplied"),
                             sample_count=257)
    # The optional native check happens before writing the three output files.
    # No Python fallback substitutes for an absent native extension.
    native_sample = None
    if args.native:
        target = BeatMap.from_dict(read_json(Path(__file__).with_name("beat-map-variable.json")))
        native_sample = dict(seconds=1.5, beat=target.beat_at(1.5), pip=target.pip_at(1.5),
                             values=motion.player().sample_time(1.5, target))
    write_capture(outputs["capture"], capture)
    write_rig_motion(outputs["motion"], motion)
    _write_json_document(outputs["source_beats"], source.to_dict())
    report = dict(paths={key: str(value) for key, value in outputs.items()},
                  type_uri=motion.type_uri, channels=len(motion.profile.channels),
                  sample_count=len(motion.recording.samples), start_pip=0, last_pip=256)
    if native_sample is not None:
        report["native_variable_tempo_sample"] = native_sample
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
