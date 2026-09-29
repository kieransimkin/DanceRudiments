# Expansion 03: Motion Atlas

256 original presets in 16 families. All are registered as native defaults.
The complete default catalogue contains 323 movements. No new third-party data.

Authoring is Python; movement playback is generated C++17. Every period is
expressed in quarter-note beats at 64 pips per beat. No runtime Python,
random-state evolution, network access, or JavaScript motion fallback is required.

## Families

| Family | Count |
| --- | ---: |
| Additive meters | 16 |
| Envelopes | 16 |
| Euclidean II | 16 |
| Gesture paths | 16 |
| Harmonic orbits | 16 |
| Lissajous II | 16 |
| Looped noise | 16 |
| Mechanisms | 16 |
| Polar paths | 16 |
| Polyrhythms II | 16 |
| Spatial loops | 16 |
| Spirographs | 16 |
| Step sequences | 16 |
| Stick studies | 16 |
| Swing studies | 16 |
| Waves III | 16 |

## Rebuild and inspect

```sh
python tools/build_atlas_collection.py --check
python tools/build_default_catalogue.py --check
```

Omit `--check` to regenerate tables after editing definitions. An intentional
table change also requires updating its hash in `collections/defaults.json`.
The hash lock is not silently rewritten by the builder.

The release demo enumerates the native catalogue, including these defaults.
Use its collection filter to isolate Motion Atlas, then choose a family.
Use `atlas_pack()` only for inspection/export; `sample(name, pip)` needs no pack load.

## Scope and interpretation

These are original preset studies, not extracted synth presets, official drum
rudiment transcriptions, motion-capture data, or full-body choreography. Related
presets deliberately explore ratios, event grids, geometry and curve shape.
Duplicate checks do not promise that every related preset looks unrelated.
Position closure is checked, but continuous acceleration is not guaranteed for
piecewise or cusped curves. Apply bounded amplitudes and respect reduced motion.

## Pattern reference

| Name | Title | Family | Beats |
| --- | --- | --- | ---: |
| `wave_pinched` | Pinched sine | Waves III | 8.0 |
| `wave_shouldered` | Shouldered sine | Waves III | 8.0 |
| `wave_folded` | Folded sine | Waves III | 8.0 |
| `wave_double_fold` | Double-fold wave | Waves III | 8.0 |
| `wave_rounded_square` | Rounded square | Waves III | 8.0 |
| `wave_soft_rectifier` | Soft rectified swell | Waves III | 8.0 |
| `wave_skew_warp` | Phase-skew sweep | Waves III | 8.0 |
| `wave_scoop_warp` | Scooped return | Waves III | 8.0 |
| `wave_shelf_wave` | Shelf and scoop | Waves III | 8.0 |
| `wave_notched` | Notched crest | Waves III | 8.0 |
| `wave_bottle` | Bottle-neck swell | Waves III | 8.0 |
| `wave_reed` | Reed flutter | Waves III | 8.0 |
| `wave_unequal_peaks` | Unequal double crest | Waves III | 8.0 |
| `wave_ripple_return` | Rippled recovery | Waves III | 8.0 |
| `wave_soft_teeth` | Soft triple teeth | Waves III | 8.0 |
| `wave_warped_fold` | Warped wave fold | Waves III | 8.0 |
| `env_lift_hold_drop` | Lift, hold, settle | Envelopes | 8.0 |
| `env_inhale_exhale` | Long inhale, short exhale | Envelopes | 8.0 |
| `env_triple_swell` | Three unequal swells | Envelopes | 8.0 |
| `env_rising_echo` | Rising echo ladder | Envelopes | 8.0 |
| `env_falling_echo` | Falling echo ladder | Envelopes | 8.0 |
| `env_anticipation` | Backward anticipation | Envelopes | 8.0 |
| `env_plateau_scoop` | Plateau then scoop | Envelopes | 8.0 |
| `env_hesitant` | Hesitant reach | Envelopes | 8.0 |
| `env_double_hold` | Two-height hold | Envelopes | 8.0 |
| `env_swell_recoil` | Deep swell and recoil | Envelopes | 8.0 |
| `env_late_release` | Late release | Envelopes | 8.0 |
| `env_split_attack` | Split attack | Envelopes | 8.0 |
| `env_suspended` | Suspended answer | Envelopes | 8.0 |
| `env_valley_peaks` | Valley between peaks | Envelopes | 8.0 |
| `env_four_breaths` | Four breathing accents | Envelopes | 8.0 |
| `env_return_stair` | Stepped soft recovery | Envelopes | 8.0 |
| `seq_up_down_even` | Up Down / even | Step sequences | 8.0 |
| `seq_up_down_lilt` | Up Down / lilt | Step sequences | 8.0 |
| `seq_pendulum_even` | Pendulum / even | Step sequences | 8.0 |
| `seq_pendulum_lilt` | Pendulum / lilt | Step sequences | 8.0 |
| `seq_octave_even` | Octave / even | Step sequences | 8.0 |
| `seq_octave_lilt` | Octave / lilt | Step sequences | 8.0 |
| `seq_unequal_even` | Unequal / even | Step sequences | 8.0 |
| `seq_unequal_lilt` | Unequal / lilt | Step sequences | 8.0 |
| `seq_question_even` | Question / even | Step sequences | 8.0 |
| `seq_question_lilt` | Question / lilt | Step sequences | 8.0 |
| `seq_answer_even` | Answer / even | Step sequences | 8.0 |
| `seq_answer_lilt` | Answer / lilt | Step sequences | 8.0 |
| `seq_ratchet_even` | Ratchet / even | Step sequences | 8.0 |
| `seq_ratchet_lilt` | Ratchet / lilt | Step sequences | 8.0 |
| `seq_stairs_even` | Stairs / even | Step sequences | 8.0 |
| `seq_stairs_lilt` | Stairs / lilt | Step sequences | 8.0 |
| `noise_drift_5` | Drift / 5 knots | Looped noise | 16.0 |
| `noise_drift_7` | Drift / 7 knots | Looped noise | 16.0 |
| `noise_drift_9` | Drift / 9 knots | Looped noise | 16.0 |
| `noise_drift_11` | Drift / 11 knots | Looped noise | 16.0 |
| `noise_orbit_6` | Orbit / 6 knots | Looped noise | 16.0 |
| `noise_orbit_8` | Orbit / 8 knots | Looped noise | 16.0 |
| `noise_orbit_10` | Orbit / 10 knots | Looped noise | 16.0 |
| `noise_orbit_12` | Orbit / 12 knots | Looped noise | 16.0 |
| `noise_ripple_5` | Ripple / 5 knots | Looped noise | 16.0 |
| `noise_ripple_7` | Ripple / 7 knots | Looped noise | 16.0 |
| `noise_ripple_9` | Ripple / 9 knots | Looped noise | 16.0 |
| `noise_ripple_11` | Ripple / 11 knots | Looped noise | 16.0 |
| `noise_depth_6` | Depth / 6 knots | Looped noise | 16.0 |
| `noise_depth_8` | Depth / 8 knots | Looped noise | 16.0 |
| `noise_depth_10` | Depth / 10 knots | Looped noise | 16.0 |
| `noise_depth_12` | Depth / 12 knots | Looped noise | 16.0 |
| `orbit_harmonic_01` | Harmonic orbit 2 / open | Harmonic orbits | 8.0 |
| `orbit_harmonic_02` | Harmonic orbit 3 / open | Harmonic orbits | 8.0 |
| `orbit_harmonic_03` | Harmonic orbit 4 / open | Harmonic orbits | 8.0 |
| `orbit_harmonic_04` | Harmonic orbit 5 / open | Harmonic orbits | 8.0 |
| `orbit_harmonic_05` | Harmonic orbit 6 / open | Harmonic orbits | 8.0 |
| `orbit_harmonic_06` | Harmonic orbit 7 / open | Harmonic orbits | 8.0 |
| `orbit_harmonic_07` | Harmonic orbit 8 / open | Harmonic orbits | 8.0 |
| `orbit_harmonic_08` | Harmonic orbit 9 / open | Harmonic orbits | 8.0 |
| `orbit_harmonic_09` | Harmonic orbit 2 / offset | Harmonic orbits | 8.0 |
| `orbit_harmonic_10` | Harmonic orbit 3 / offset | Harmonic orbits | 8.0 |
| `orbit_harmonic_11` | Harmonic orbit 4 / offset | Harmonic orbits | 8.0 |
| `orbit_harmonic_12` | Harmonic orbit 5 / offset | Harmonic orbits | 8.0 |
| `orbit_harmonic_13` | Harmonic orbit 6 / offset | Harmonic orbits | 8.0 |
| `orbit_harmonic_14` | Harmonic orbit 7 / offset | Harmonic orbits | 8.0 |
| `orbit_harmonic_15` | Harmonic orbit 8 / offset | Harmonic orbits | 8.0 |
| `orbit_harmonic_16` | Harmonic orbit 9 / offset | Harmonic orbits | 8.0 |
| `weave_1_3` | 1 by 3 weave | Lissajous II | 16.0 |
| `weave_1_4` | 1 by 4 weave | Lissajous II | 16.0 |
| `weave_1_5` | 1 by 5 weave | Lissajous II | 16.0 |
| `weave_2_5` | 2 by 5 weave | Lissajous II | 16.0 |
| `weave_2_7` | 2 by 7 weave | Lissajous II | 16.0 |
| `weave_3_4` | 3 by 4 weave | Lissajous II | 16.0 |
| `weave_3_5` | 3 by 5 weave | Lissajous II | 16.0 |
| `weave_3_7` | 3 by 7 weave | Lissajous II | 16.0 |
| `weave_3_8` | 3 by 8 weave | Lissajous II | 16.0 |
| `weave_4_5` | 4 by 5 weave | Lissajous II | 16.0 |
| `weave_4_7` | 4 by 7 weave | Lissajous II | 16.0 |
| `weave_4_9` | 4 by 9 weave | Lissajous II | 16.0 |
| `weave_5_6` | 5 by 6 weave | Lissajous II | 16.0 |
| `weave_5_7` | 5 by 7 weave | Lissajous II | 16.0 |
| `weave_5_8` | 5 by 8 weave | Lissajous II | 16.0 |
| `weave_5_9` | 5 by 9 weave | Lissajous II | 16.0 |
| `polar_rose_3` | 3-petal rose | Polar paths | 16.0 |
| `polar_rose_6` | 6-petal rose | Polar paths | 16.0 |
| `polar_rose_7` | 7-petal rose | Polar paths | 16.0 |
| `polar_rose_8` | 8-petal rose | Polar paths | 16.0 |
| `polar_rose_9` | 9-petal rose | Polar paths | 16.0 |
| `polar_rose_10` | 10-petal rose | Polar paths | 16.0 |
| `polar_rose_11` | 11-petal rose | Polar paths | 16.0 |
| `polar_rose_12` | 12-petal rose | Polar paths | 16.0 |
| `polar_scallop_2` | 2-scallop orbit | Polar paths | 16.0 |
| `polar_scallop_3` | 3-scallop orbit | Polar paths | 16.0 |
| `polar_scallop_4` | 4-scallop orbit | Polar paths | 16.0 |
| `polar_scallop_5` | 5-scallop orbit | Polar paths | 16.0 |
| `polar_scallop_6` | 6-scallop orbit | Polar paths | 16.0 |
| `polar_scallop_7` | 7-scallop orbit | Polar paths | 16.0 |
| `polar_scallop_8` | 8-scallop orbit | Polar paths | 16.0 |
| `polar_scallop_9` | 9-scallop orbit | Polar paths | 16.0 |
| `spiro_inside_3_1` | Inside roll 3:1 | Spirographs | 16.0 |
| `spiro_inside_4_1` | Inside roll 4:1 | Spirographs | 16.0 |
| `spiro_inside_5_2` | Inside roll 5:2 | Spirographs | 16.0 |
| `spiro_inside_5_1` | Inside roll 5:1 | Spirographs | 16.0 |
| `spiro_inside_7_2` | Inside roll 7:2 | Spirographs | 16.0 |
| `spiro_inside_7_3` | Inside roll 7:3 | Spirographs | 16.0 |
| `spiro_inside_8_3` | Inside roll 8:3 | Spirographs | 16.0 |
| `spiro_inside_9_4` | Inside roll 9:4 | Spirographs | 16.0 |
| `spiro_outside_3_1` | Outside roll 3:1 | Spirographs | 16.0 |
| `spiro_outside_4_1` | Outside roll 4:1 | Spirographs | 16.0 |
| `spiro_outside_5_2` | Outside roll 5:2 | Spirographs | 16.0 |
| `spiro_outside_5_1` | Outside roll 5:1 | Spirographs | 16.0 |
| `spiro_outside_7_2` | Outside roll 7:2 | Spirographs | 16.0 |
| `spiro_outside_7_3` | Outside roll 7:3 | Spirographs | 16.0 |
| `spiro_outside_8_3` | Outside roll 8:3 | Spirographs | 16.0 |
| `spiro_outside_9_4` | Outside roll 9:4 | Spirographs | 16.0 |
| `space_torus_2_5` | Torus knot 2:5 | Spatial loops | 16.0 |
| `space_torus_2_7` | Torus knot 2:7 | Spatial loops | 16.0 |
| `space_torus_3_4` | Torus knot 3:4 | Spatial loops | 16.0 |
| `space_torus_3_5` | Torus knot 3:5 | Spatial loops | 16.0 |
| `space_torus_3_7` | Torus knot 3:7 | Spatial loops | 16.0 |
| `space_torus_4_5` | Torus knot 4:5 | Spatial loops | 16.0 |
| `space_torus_4_7` | Torus knot 4:7 | Spatial loops | 16.0 |
| `space_torus_5_6` | Torus knot 5:6 | Spatial loops | 16.0 |
| `space_weave_1_2_3` | Spatial weave 1:2:3 | Spatial loops | 16.0 |
| `space_weave_1_3_4` | Spatial weave 1:3:4 | Spatial loops | 16.0 |
| `space_weave_2_3_4` | Spatial weave 2:3:4 | Spatial loops | 16.0 |
| `space_weave_2_3_7` | Spatial weave 2:3:7 | Spatial loops | 16.0 |
| `space_weave_2_5_7` | Spatial weave 2:5:7 | Spatial loops | 16.0 |
| `space_weave_3_4_5` | Spatial weave 3:4:5 | Spatial loops | 16.0 |
| `space_weave_3_5_7` | Spatial weave 3:5:7 | Spatial loops | 16.0 |
| `space_weave_4_5_7` | Spatial weave 4:5:7 | Spatial loops | 16.0 |
| `mech_piston_short` | Short-rod piston | Mechanisms | 8.0 |
| `mech_piston_long` | Long-rod piston | Mechanisms | 8.0 |
| `mech_offset_crank` | Offset crank | Mechanisms | 8.0 |
| `mech_scotch_yoke` | Yoke with rocking linkage | Mechanisms | 8.0 |
| `mech_whitworth` | Quick-return linkage study | Mechanisms | 8.0 |
| `mech_elliptic_cam` | Elliptic cam follower | Mechanisms | 8.0 |
| `mech_two_lobe_cam` | Two-lobe cam follower | Mechanisms | 8.0 |
| `mech_three_lobe_cam` | Three-lobe cam follower | Mechanisms | 8.0 |
| `mech_escapement` | Soft escapement study | Mechanisms | 8.0 |
| `mech_paddle` | Paddle-wheel tip | Mechanisms | 8.0 |
| `mech_wobble_plate` | Wobble-plate trace | Mechanisms | 8.0 |
| `mech_rocking_beam` | Rocking beam | Mechanisms | 8.0 |
| `mech_coupled_cranks` | Coupled cranks | Mechanisms | 8.0 |
| `mech_crank_rocker` | Crank and rocker study | Mechanisms | 8.0 |
| `mech_piston_balance` | Piston and balance mass | Mechanisms | 8.0 |
| `mech_cam_return` | Cam rise and return | Mechanisms | 8.0 |
| `euclid_2_5` | 2 accents in 5 eighths | Euclidean II | 2.5 |
| `euclid_3_7` | 3 accents in 7 eighths | Euclidean II | 3.5 |
| `euclid_3_10` | 3 accents in 10 eighths | Euclidean II | 5.0 |
| `euclid_4_9` | 4 accents in 9 eighths | Euclidean II | 4.5 |
| `euclid_4_11` | 4 accents in 11 eighths | Euclidean II | 5.5 |
| `euclid_5_9` | 5 accents in 9 eighths | Euclidean II | 4.5 |
| `euclid_5_11` | 5 accents in 11 eighths | Euclidean II | 5.5 |
| `euclid_5_13` | 5 accents in 13 eighths | Euclidean II | 6.5 |
| `euclid_5_14` | 5 accents in 14 eighths | Euclidean II | 7.0 |
| `euclid_6_13` | 6 accents in 13 eighths | Euclidean II | 6.5 |
| `euclid_7_12` | 7 accents in 12 eighths | Euclidean II | 6.0 |
| `euclid_7_15` | 7 accents in 15 eighths | Euclidean II | 7.5 |
| `euclid_7_17` | 7 accents in 17 eighths | Euclidean II | 8.5 |
| `euclid_8_19` | 8 accents in 19 eighths | Euclidean II | 9.5 |
| `euclid_9_20` | 9 accents in 20 eighths | Euclidean II | 10.0 |
| `euclid_11_24` | 11 accents in 24 eighths | Euclidean II | 12.0 |
| `poly_2_5` | 2 against 5 / spatial accents | Polyrhythms II | 8.0 |
| `poly_2_7` | 2 against 7 / spatial accents | Polyrhythms II | 8.0 |
| `poly_2_9` | 2 against 9 / spatial accents | Polyrhythms II | 8.0 |
| `poly_3_5` | 3 against 5 / spatial accents | Polyrhythms II | 8.0 |
| `poly_3_7` | 3 against 7 / spatial accents | Polyrhythms II | 8.0 |
| `poly_3_8` | 3 against 8 / spatial accents | Polyrhythms II | 8.0 |
| `poly_3_10` | 3 against 10 / spatial accents | Polyrhythms II | 8.0 |
| `poly_4_5` | 4 against 5 / spatial accents | Polyrhythms II | 8.0 |
| `poly_4_7` | 4 against 7 / spatial accents | Polyrhythms II | 8.0 |
| `poly_4_9` | 4 against 9 / spatial accents | Polyrhythms II | 8.0 |
| `poly_5_6` | 5 against 6 / spatial accents | Polyrhythms II | 8.0 |
| `poly_5_7` | 5 against 7 / spatial accents | Polyrhythms II | 8.0 |
| `poly_5_8` | 5 against 8 / spatial accents | Polyrhythms II | 8.0 |
| `poly_5_9` | 5 against 9 / spatial accents | Polyrhythms II | 8.0 |
| `poly_6_7` | 6 against 7 / spatial accents | Polyrhythms II | 8.0 |
| `poly_7_8` | 7 against 8 / spatial accents | Polyrhythms II | 8.0 |
| `meter_2_3` | 2 + 3 eighths | Additive meters | 2.5 |
| `meter_3_2` | 3 + 2 eighths | Additive meters | 2.5 |
| `meter_3_2_2` | 3 + 2 + 2 eighths | Additive meters | 3.5 |
| `meter_2_3_2` | 2 + 3 + 2 eighths | Additive meters | 3.5 |
| `meter_3_4` | 3 + 4 eighths | Additive meters | 3.5 |
| `meter_4_3` | 4 + 3 eighths | Additive meters | 3.5 |
| `meter_2_2_2_3` | 2 + 2 + 2 + 3 eighths | Additive meters | 4.5 |
| `meter_2_3_2_2` | 2 + 3 + 2 + 2 eighths | Additive meters | 4.5 |
| `meter_3_2_3_2` | 3 + 2 + 3 + 2 eighths | Additive meters | 5.0 |
| `meter_3_3_2_3` | 3 + 3 + 2 + 3 eighths | Additive meters | 5.5 |
| `meter_2_2_3_2_3` | 2 + 2 + 3 + 2 + 3 eighths | Additive meters | 6.0 |
| `meter_3_3_3_2` | 3 + 3 + 3 + 2 eighths | Additive meters | 5.5 |
| `meter_4_3_3` | 4 + 3 + 3 eighths | Additive meters | 5.0 |
| `meter_3_4_4` | 3 + 4 + 4 eighths | Additive meters | 5.5 |
| `meter_2_3_3_2_3` | 2 + 3 + 3 + 2 + 3 eighths | Additive meters | 6.5 |
| `meter_3_3_3_4` | 3 + 3 + 3 + 4 eighths | Additive meters | 6.5 |
| `swing_push_3_5` | Push swing 3/5 | Swing studies | 8.0 |
| `swing_answer_3_5` | Answer swing 3/5 | Swing studies | 8.0 |
| `swing_skip_3_5` | Skip swing 3/5 | Swing studies | 8.0 |
| `swing_shuffle_3_5` | Shuffle swing 3/5 | Swing studies | 8.0 |
| `swing_push_2_3` | Push swing 2/3 | Swing studies | 8.0 |
| `swing_answer_2_3` | Answer swing 2/3 | Swing studies | 8.0 |
| `swing_skip_2_3` | Skip swing 2/3 | Swing studies | 8.0 |
| `swing_shuffle_2_3` | Shuffle swing 2/3 | Swing studies | 8.0 |
| `swing_push_5_7` | Push swing 5/7 | Swing studies | 8.0 |
| `swing_answer_5_7` | Answer swing 5/7 | Swing studies | 8.0 |
| `swing_skip_5_7` | Skip swing 5/7 | Swing studies | 8.0 |
| `swing_shuffle_5_7` | Shuffle swing 5/7 | Swing studies | 8.0 |
| `swing_push_3_4` | Push swing 3/4 | Swing studies | 8.0 |
| `swing_answer_3_4` | Answer swing 3/4 | Swing studies | 8.0 |
| `swing_skip_3_4` | Skip swing 3/4 | Swing studies | 8.0 |
| `swing_shuffle_3_4` | Shuffle swing 3/4 | Swing studies | 8.0 |
| `stick_study_01` | RLRRLRLL / mirrored answer | Stick studies | 8.0 |
| `stick_study_02` | RRLRLLRL / mirrored answer | Stick studies | 8.0 |
| `stick_study_03` | RLLRLRRL / mirrored answer | Stick studies | 8.0 |
| `stick_study_04` | RRLLRLRL / mirrored answer | Stick studies | 8.0 |
| `stick_study_05` | RLRLRRLL / mirrored answer | Stick studies | 8.0 |
| `stick_study_06` | RRRLLLRL / mirrored answer | Stick studies | 8.0 |
| `stick_study_07` | RLLLRRRL / mirrored answer | Stick studies | 8.0 |
| `stick_study_08` | RRLRRLLL / mirrored answer | Stick studies | 8.0 |
| `stick_study_09` | RLRRLLRL / mirrored answer | Stick studies | 8.0 |
| `stick_study_10` | RRLLRLLR / mirrored answer | Stick studies | 8.0 |
| `stick_study_11` | RLRLLRRL / mirrored answer | Stick studies | 8.0 |
| `stick_study_12` | RRRLRLLL / mirrored answer | Stick studies | 8.0 |
| `stick_study_13` | RRRRLRLL / mirrored answer | Stick studies | 8.0 |
| `stick_study_14` | RRLLLRRL / mirrored answer | Stick studies | 8.0 |
| `stick_study_15` | RLRRRLLL / mirrored answer | Stick studies | 8.0 |
| `stick_study_16` | RRLRLLLR / mirrored answer | Stick studies | 8.0 |
| `gesture_side_reach` | Side reach | Gesture paths | 8.0 |
| `gesture_cross_reach` | Cross and reach | Gesture paths | 8.0 |
| `gesture_low_scoop` | Low scoop | Gesture paths | 8.0 |
| `gesture_high_arc` | High arc | Gesture paths | 8.0 |
| `gesture_corner_taps` | Corner taps | Gesture paths | 8.0 |
| `gesture_diagonal_touch` | Diagonal touch | Gesture paths | 8.0 |
| `gesture_box_return` | Box and centre | Gesture paths | 8.0 |
| `gesture_zigzag_lift` | Zigzag lift | Gesture paths | 8.0 |
| `gesture_duck_sway` | Duck and sway | Gesture paths | 8.0 |
| `gesture_push_pull` | Push and pull | Gesture paths | 8.0 |
| `gesture_reach_depth` | Reach through depth | Gesture paths | 8.0 |
| `gesture_bow_turn` | Bow and turn | Gesture paths | 8.0 |
| `gesture_heel_toe` | Heel-toe abstract | Gesture paths | 8.0 |
| `gesture_hop_answer` | Hop and answer | Gesture paths | 8.0 |
| `gesture_spiral_reach` | Spiral reach | Gesture paths | 8.0 |
| `gesture_diamond_depth` | Depth diamond | Gesture paths | 8.0 |

Copyright (c) 2026 Kieran Simkin. MIT; see the repository LICENSE.
