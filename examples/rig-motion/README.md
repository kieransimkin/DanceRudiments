# Rig-motion authoring and native playback example

This original synthetic example exercises the complete capture → beat-grid
compile → native playback route without downloaded choreography or Blender.
It declares a custom seven-channel `root` control. It is an API example, not a
claim that a foreign skeleton has been retargeted to a Rigify character.

From the repository root:

```sh
python examples/rig-motion/quickstart.py --output generated/rig-motion
python tools/rig_motion.py inspect generated/rig-motion/synthetic.motion.json
```

The script writes a physical-value capture, its source beat map, and a normalized
rig-motion document. It refuses to overwrite an existing output. There are 257
samples, including both ends of the interval from pip 0 to pip 256 (four beats).
Playback is non-looping even though this particular example has matching ends.

| Channel | Parameter | Physical range |
| --- | --- | --- |
| 1 | `root.location.x` | −2 to +2 metres |
| 2 | `root.location.y` | −2 to +2 metres |
| 3 | `root.location.z` | −2 to +2 metres |
| 4 | `root.rotation_quaternion.w` | −1 to +1 |
| 5 | `root.rotation_quaternion.x` | −1 to +1 |
| 6 | `root.rotation_quaternion.y` | −1 to +1 |
| 7 | `root.rotation_quaternion.z` | −1 to +1 |

Recompile using an explicit source tempo and beat origin:

```sh
python tools/rig_motion.py compile generated/rig-motion/synthetic.capture.json generated/rig-motion/retimed.motion.json --name retimed_sway --source-bpm 120 --source-beat-zero 0 --bpm 100 --samples 257
```

Here the four source beats take 2.4 seconds at the nominal target tempo of
100 BPM. `--motion-rate 1/2 --samples 513` instead spreads those source beats
over eight target beats. `--source-beat-offset` chooses a source excerpt in
quarter-note beats; `--start-pip` is the absolute target musical position.
The compiler rejects any requested extent outside the captured motion.

## Sample through C++

Install/build the repository's native Python package before using playback.
The authoring-only steps above need only the Python standard library.

```sh
python -m pip install .
python tools/rig_motion.py sample generated/rig-motion/synthetic.motion.json --pip 32
python examples/rig-motion/quickstart.py --output generated/rig-motion-native --native
```

The last command also reads `beat-map-variable.json`. Its target tempo changes
from 120 to 60 to 240 BPM. At 1.5 seconds, the map gives beat 2.5 / pip 160,
rather than multiplying the entire elapsed time by the latest tempo.

The same explicit mapping is available in Python:

```python
from dancerudiments_authoring.io import read_json
from dancerudiments_authoring.motion import load_rig_motion
from dancerudiments_authoring.motion_clock import BeatMap

motion = load_rig_motion("generated/rig-motion/synthetic.motion.json")
target = BeatMap.from_dict(read_json("examples/rig-motion/beat-map-variable.json"))
player = motion.player()  # creates the real C++ SampledRecording
physical_values = player.sample_time(1.5, target)
assert target.pip_at(1.5) == 160
```

`BeatMap` interpolates between strictly increasing seconds/beat anchors and has
an exact inverse. Values are computed from absolute time rather than repeated
rounded frame increments. Use `seconds_fraction()` when generating a boundary
that must round-trip exactly; `seconds_at()` returns an ordinary floating-point
time. Measured maps refuse extrapolation by default. Constant-tempo maps created
with `from_bpm()` deliberately extend their known tempo beyond their two anchors.

## Real characters

Use the Blender bridge to discover/export the actual generated rig profile,
retarget and bake a source action onto that rig, then capture its controls.
The profile fingerprint records the exact channel mapping and rig metadata.
Changing a character's rest pose or channel range requires a matching capture;
renaming bones in this synthetic example is not retargeting.

Source captures retain physical units, frame times and provenance. Compilation
uses linear scalar interpolation, joint quaternion SLERP, and held integer/bool
selectors. Euler controls preserve their sampled winding, so source discontinuities
must be unwrapped before capture. No automatic beat detection, retargeting or foot
plant correction is implied. See the repository's rig-motion guide and researched
motion-source catalogue for the available import routes and rights information.
