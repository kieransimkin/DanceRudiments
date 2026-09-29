# Expansion 02 — 24 original default movements

This batch adds eight shaped LFOs, eight geometric paths, and eight rhythmic
interlocks. They join the normal C++/Python/TypeScript default catalogue.
All are original MIT-licensed definitions; no external downloads are needed.

## Preview

Open the generated release HTML and choose **LFO II**, **Geometry** or
**Interlock** in the family selector to isolate the new movements. Compare up
to four on the shared musical clock. Use a modest amplitude at higher BPM.
The torus knot, spatial weave and three-four-five interlock retain all XYZ
components; the gallery projects depth and plots the separate Z curve.

## Catalogue

| Name | Title | Beats | Description |
|---|---|---:|---|
| `lfo_twin_swell` | Unequal twin swells | 8 | Two broad swells of unequal depth, with a gentle lateral answer. Eight beats. |
| `lfo_pulse_hold` | Pulse, hold & recoil | 4 | A smooth outward pulse, sustained plateau, smaller opposite recoil, and rest. |
| `lfo_sweep_ratchet` | Sweep into ratchets | 8 | A slow lateral sweep followed by three decaying vertical ratchets; no reset jump. |
| `lfo_triplet_wobble` | Breathing triplet wobble | 8 | Three rounded oscillations per two beats, breathing in depth over an eight-beat phrase. |
| `lfo_breathing_orbit` | Breathing orbit | 8 | A closed ellipse expands and contracts twice during its eight-beat revolution. |
| `lfo_seeded_drift` | Seeded wandering loop | 16 | Two independently seeded smooth random lanes; irregular-looking but exactly periodic and seekable. |
| `lfo_pendulum_dwell` | Pendulum with dwell | 8 | Rounded saturation slows the pendulum near either side; a shallow arc connects the turns. |
| `lfo_reverse_swell` | Reverse swell & aftershock | 8 | A long anticipatory rise, quick softened return, and two diminishing aftershocks. |
| `path_lissajous_2_3` | Two-by-three weave | 8 | Two horizontal cycles cross three vertical cycles in a closed eight-beat Lissajous path. |
| `path_rose_4` | Four-petal rose | 8 | A signed radial oscillation draws four petals, passing through the centre between them. |
| `path_rose_5` | Five-petal rose | 8 | Five petals in one complete eight-beat traversal; the odd-petal parameter runs through pi, not two pi. |
| `path_bowed_diamond` | Bowed diamond | 8 | An astroid-shaped loop with inward-curved edges and naturally slow corners. |
| `path_orbit_dwell` | Orbit with downbeat dwell | 8 | An ellipse whose phase slows to zero speed at the loop boundary and accelerates through the opposite side. |
| `path_torus_knot` | Three-dimensional torus knot | 16 | Two turns around the axis and three through the tube. XYZ is retained; the demo projects depth. |
| `path_woven_3d` | Two-three-five spatial weave | 16 | Independent two-, three-, and five-cycle XYZ oscillations close after sixteen beats. |
| `path_crank_slider` | Slider & crank | 4 | Horizontal slider-crank travel with rod length three and crank radius one; vertical motion follows the crank tip. |
| `rhythm_five_four` | 5 against four | 8 | 5 lateral hits against four vertical hits per four beats; two bars preserve alternating directions. |
| `rhythm_seven_four` | 7 against four | 8 | 7 lateral hits against four vertical hits per four beats; two bars preserve alternating directions. |
| `rhythm_euclid_7_16` | 7 in sixteen | 8 | 7 evenly distributed onsets on a sixteen-step grid, repeated with alternating sides over eight beats. |
| `rhythm_euclid_5_16` | 5 in sixteen | 8 | 5 evenly distributed onsets on a sixteen-step grid, repeated with alternating sides over eight beats. |
| `rhythm_swung_answer` | Swung call & response | 4 | A two-to-one swung call on the right, answered on the left; four beats and eight peak-aligned gestures. |
| `rhythm_group_332` | Three-three-two accents | 8 | Groups of three, three, and two eighth notes. Six alternating accents make an eight-beat loop. |
| `rhythm_group_223` | Two-two-three stepping | 7 | Two 7/8 bars grouped as 2+2+3 eighth notes: a seven-quarter-note loop, not forced into four beats. |
| `rhythm_three_four_five` | Three-four-five interlock | 8 | Three X, four Y, and five Z gestures share an eight-beat phrase, with exact rational peak times. |

## Authoring and rebuilding

Edit `definitions.py`, then regenerate explicitly:

```sh
python tools/build_expansion_collection.py
```

This writes the editable score, compiled JSON, C++17 header and content manifest.
Check and intentionally update the Expansion 02 digest in `collections/defaults.json`
after reviewing data changes, then run `python tools/build_default_catalogue.py`.
No command silently rewrites that selection lock.

```sh
python tools/build_expansion_collection.py --check
python tools/build_default_catalogue.py --check
```

All new loops are position-closed and compile with `bounds=reject`, without
clipping, normalization or warnings. This does not assert that all trajectories
have continuous acceleration or are safe for unbounded/full-screen motion.
Finite-amplitude local translation and reduced-motion handling remain required.

`rhythm_group_223` spans two 7/8 bars: seven quarter-note beats / 448 pips.
The fifth/seventh and swung event scores preserve rational timestamps until
sampling. The random drift is a fixed cyclic interpolation, not stateful noise.
The five-petal rose traverses its minimal geometric period rather than drawing
every petal twice. Rates and amplitudes are authored examples, not genre claims.
