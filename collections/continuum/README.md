# Continuum 04: 320 new built-in movements

By [Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/).

320 original presets across 20 families, appended to the previous 323 defaults. Total: **643**.
No earlier pattern is removed, renamed, reordered or resampled. No new third-party data.

## Use

```python
import dancerudiments as d
position = d.sample("ribbon_2_5_deep", 48)
position = d.sample("surface_3_5_wide", -1)
```

C++ and TypeScript use their existing `sample(name, pip)` APIs. There is no pack-loading
requirement. `continuum_pack()` optionally exposes compiled authoring data for inspection.

## Families

| Family | Count |
| --- | ---: |
| Alternating bursts | 16 |
| Braided loops | 16 |
| Broken triplets | 16 |
| Corner tours | 16 |
| Dwell phrases | 16 |
| Echo conversations | 16 |
| Fourier silhouettes | 16 |
| Linkage portraits | 16 |
| Meter dialogues | 16 |
| Petal journeys | 16 |
| Resonant packets | 16 |
| Rhythm necklaces | 16 |
| Rhythmic canons | 16 |
| Ribbon sweeps | 16 |
| Rounded contours | 16 |
| Serpentine scans | 16 |
| Spline circuits | 16 |
| Subdivision ladders | 16 |
| Surface travels | 16 |
| Travelling accents | 16 |

## Regenerate

```sh
python tools/build_continuum_collection.py --check
python tools/build_default_catalogue.py --check
```

Omit `--check` to regenerate after intentional source edits, then explicitly update the
corresponding source hash in `collections/defaults.json`. Builders never silently unlock data.
Authoring uses Python standard-library code. Runtime positions come from C++17 tables.

## Interpretation and limits

All periods use quarter-note beats at 64 pips per beat. Rational event times survive until
the final pip sampling; the runtime grid still cannot represent every event peak exactly.
Geometry preserves relative XYZ scale. Source endpoints and oversampled values are checked
before baking; duplicate arrays, grid-aligned phase/gain copies, warnings and large steps
are rejected. Related variations may still look alike. The audit is not a perceptual metric.
Closed positions do not promise continuous acceleration at every cusp or corner.
Mechanism, arm and gesture names describe abstract trajectory studies, not validated
dynamics, robot controls, motion capture, or full-body dance choreography.

Use bounded local translations and respect reduced-motion preferences. Do not map these
curves to full-frame flashing. Fast/high-amplitude playback may remain uncomfortable.

## Pattern reference

| Identifier | Title | Family | Beats |
| --- | --- | --- | ---: |
| `ribbon_1_2_slim` | Ribbon 1:2 / slim | Ribbon sweeps | 16.0 |
| `ribbon_1_3_slim` | Ribbon 1:3 / slim | Ribbon sweeps | 16.0 |
| `ribbon_1_4_slim` | Ribbon 1:4 / slim | Ribbon sweeps | 16.0 |
| `ribbon_1_5_slim` | Ribbon 1:5 / slim | Ribbon sweeps | 16.0 |
| `ribbon_2_3_slim` | Ribbon 2:3 / slim | Ribbon sweeps | 16.0 |
| `ribbon_2_5_slim` | Ribbon 2:5 / slim | Ribbon sweeps | 16.0 |
| `ribbon_3_4_slim` | Ribbon 3:4 / slim | Ribbon sweeps | 16.0 |
| `ribbon_3_5_slim` | Ribbon 3:5 / slim | Ribbon sweeps | 16.0 |
| `ribbon_1_2_deep` | Ribbon 1:2 / deep | Ribbon sweeps | 16.0 |
| `ribbon_1_3_deep` | Ribbon 1:3 / deep | Ribbon sweeps | 16.0 |
| `ribbon_1_4_deep` | Ribbon 1:4 / deep | Ribbon sweeps | 16.0 |
| `ribbon_1_5_deep` | Ribbon 1:5 / deep | Ribbon sweeps | 16.0 |
| `ribbon_2_3_deep` | Ribbon 2:3 / deep | Ribbon sweeps | 16.0 |
| `ribbon_2_5_deep` | Ribbon 2:5 / deep | Ribbon sweeps | 16.0 |
| `ribbon_3_4_deep` | Ribbon 3:4 / deep | Ribbon sweeps | 16.0 |
| `ribbon_3_5_deep` | Ribbon 3:5 / deep | Ribbon sweeps | 16.0 |
| `contour_shaped_01` | Shaped contour / 01 | Rounded contours | 16.0 |
| `contour_shaped_02` | Shaped contour / 02 | Rounded contours | 16.0 |
| `contour_shaped_03` | Shaped contour / 03 | Rounded contours | 16.0 |
| `contour_shaped_04` | Shaped contour / 04 | Rounded contours | 16.0 |
| `contour_shaped_05` | Shaped contour / 05 | Rounded contours | 16.0 |
| `contour_shaped_06` | Shaped contour / 06 | Rounded contours | 16.0 |
| `contour_shaped_07` | Shaped contour / 07 | Rounded contours | 16.0 |
| `contour_shaped_08` | Shaped contour / 08 | Rounded contours | 16.0 |
| `contour_shaped_09` | Shaped contour / 09 | Rounded contours | 16.0 |
| `contour_shaped_10` | Shaped contour / 10 | Rounded contours | 16.0 |
| `contour_shaped_11` | Shaped contour / 11 | Rounded contours | 16.0 |
| `contour_shaped_12` | Shaped contour / 12 | Rounded contours | 16.0 |
| `contour_shaped_13` | Shaped contour / 13 | Rounded contours | 16.0 |
| `contour_shaped_14` | Shaped contour / 14 | Rounded contours | 16.0 |
| `contour_shaped_15` | Shaped contour / 15 | Rounded contours | 16.0 |
| `contour_shaped_16` | Shaped contour / 16 | Rounded contours | 16.0 |
| `silhouette_harmonic_01` | Harmonic silhouette / 1-2-3 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_02` | Harmonic silhouette / 1-3-5 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_03` | Harmonic silhouette / 2-3-4 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_04` | Harmonic silhouette / 2-5-7 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_05` | Harmonic silhouette / 1-4-7 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_06` | Harmonic silhouette / 3-4-5 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_07` | Harmonic silhouette / 2-7-9 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_08` | Harmonic silhouette / 3-5-8 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_09` | Harmonic silhouette / 1-2-5 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_10` | Harmonic silhouette / 1-5-8 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_11` | Harmonic silhouette / 2-3-7 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_12` | Harmonic silhouette / 3-7-10 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_13` | Harmonic silhouette / 2-4-9 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_14` | Harmonic silhouette / 3-4-9 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_15` | Harmonic silhouette / 4-5-7 | Fourier silhouettes | 16.0 |
| `silhouette_harmonic_16` | Harmonic silhouette / 4-7-11 | Fourier silhouettes | 16.0 |
| `spline_kite` | Kite / spline | Spline circuits | 8.0 |
| `spline_hourglass` | Hourglass / spline | Spline circuits | 8.0 |
| `spline_hook` | Hook / spline | Spline circuits | 8.0 |
| `spline_crown` | Crown / spline | Spline circuits | 8.0 |
| `spline_bow` | Bow / spline | Spline circuits | 8.0 |
| `spline_crooked_cross` | Crooked Cross / spline | Spline circuits | 8.0 |
| `spline_asymmetric_star` | Asymmetric Star / spline | Spline circuits | 8.0 |
| `spline_scoop` | Scoop / spline | Spline circuits | 8.0 |
| `spline_rising_kite` | Rising Kite / spline | Spline circuits | 8.0 |
| `spline_twisted_bow` | Twisted Bow / spline | Spline circuits | 8.0 |
| `spline_cup` | Cup / spline | Spline circuits | 8.0 |
| `spline_bridge` | Bridge / spline | Spline circuits | 8.0 |
| `spline_double_bay` | Double Bay / spline | Spline circuits | 8.0 |
| `spline_slanted_loop` | Slanted Loop / spline | Spline circuits | 8.0 |
| `spline_fork` | Fork / spline | Spline circuits | 8.0 |
| `spline_folded_crown` | Folded Crown / spline | Spline circuits | 8.0 |
| `tour_5_2` | 5-corner tour / stride 2 | Corner tours | 16.0 |
| `tour_7_2` | 7-corner tour / stride 2 | Corner tours | 16.0 |
| `tour_7_3` | 7-corner tour / stride 3 | Corner tours | 16.0 |
| `tour_8_3` | 8-corner tour / stride 3 | Corner tours | 16.0 |
| `tour_9_2` | 9-corner tour / stride 2 | Corner tours | 16.0 |
| `tour_9_4` | 9-corner tour / stride 4 | Corner tours | 16.0 |
| `tour_10_3` | 10-corner tour / stride 3 | Corner tours | 16.0 |
| `tour_11_2` | 11-corner tour / stride 2 | Corner tours | 16.0 |
| `tour_11_3` | 11-corner tour / stride 3 | Corner tours | 16.0 |
| `tour_11_4` | 11-corner tour / stride 4 | Corner tours | 16.0 |
| `tour_12_5` | 12-corner tour / stride 5 | Corner tours | 16.0 |
| `tour_13_2` | 13-corner tour / stride 2 | Corner tours | 16.0 |
| `tour_13_3` | 13-corner tour / stride 3 | Corner tours | 16.0 |
| `tour_13_4` | 13-corner tour / stride 4 | Corner tours | 16.0 |
| `tour_13_5` | 13-corner tour / stride 5 | Corner tours | 16.0 |
| `tour_14_3` | 14-corner tour / stride 3 | Corner tours | 16.0 |
| `scan_flat_3` | Flat scan / 3 rows | Serpentine scans | 16.0 |
| `scan_bowed_3` | Bowed scan / 3 rows | Serpentine scans | 16.0 |
| `scan_tilted_3` | Tilted scan / 3 rows | Serpentine scans | 16.0 |
| `scan_depth_3` | Depth scan / 3 rows | Serpentine scans | 16.0 |
| `scan_flat_4` | Flat scan / 4 rows | Serpentine scans | 16.0 |
| `scan_bowed_4` | Bowed scan / 4 rows | Serpentine scans | 16.0 |
| `scan_tilted_4` | Tilted scan / 4 rows | Serpentine scans | 16.0 |
| `scan_depth_4` | Depth scan / 4 rows | Serpentine scans | 16.0 |
| `scan_flat_5` | Flat scan / 5 rows | Serpentine scans | 16.0 |
| `scan_bowed_5` | Bowed scan / 5 rows | Serpentine scans | 16.0 |
| `scan_tilted_5` | Tilted scan / 5 rows | Serpentine scans | 16.0 |
| `scan_depth_5` | Depth scan / 5 rows | Serpentine scans | 16.0 |
| `scan_flat_6` | Flat scan / 6 rows | Serpentine scans | 16.0 |
| `scan_bowed_6` | Bowed scan / 6 rows | Serpentine scans | 16.0 |
| `scan_tilted_6` | Tilted scan / 6 rows | Serpentine scans | 16.0 |
| `scan_depth_6` | Depth scan / 6 rows | Serpentine scans | 16.0 |
| `reach_scoop_3` | 3-direction scoop | Petal journeys | 16.0 |
| `reach_hook_3` | 3-direction hook | Petal journeys | 16.0 |
| `reach_lift_3` | 3-direction lift | Petal journeys | 16.0 |
| `reach_recoil_3` | 3-direction recoil | Petal journeys | 16.0 |
| `reach_scoop_4` | 4-direction scoop | Petal journeys | 16.0 |
| `reach_hook_4` | 4-direction hook | Petal journeys | 16.0 |
| `reach_lift_4` | 4-direction lift | Petal journeys | 16.0 |
| `reach_recoil_4` | 4-direction recoil | Petal journeys | 16.0 |
| `reach_scoop_5` | 5-direction scoop | Petal journeys | 16.0 |
| `reach_hook_5` | 5-direction hook | Petal journeys | 16.0 |
| `reach_lift_5` | 5-direction lift | Petal journeys | 16.0 |
| `reach_recoil_5` | 5-direction recoil | Petal journeys | 16.0 |
| `reach_scoop_7` | 7-direction scoop | Petal journeys | 16.0 |
| `reach_hook_7` | 7-direction hook | Petal journeys | 16.0 |
| `reach_lift_7` | 7-direction lift | Petal journeys | 16.0 |
| `reach_recoil_7` | 7-direction recoil | Petal journeys | 16.0 |
| `surface_1_2_low` | Latitude 1:2 / low | Surface travels | 16.0 |
| `surface_1_3_low` | Latitude 1:3 / low | Surface travels | 16.0 |
| `surface_1_4_low` | Latitude 1:4 / low | Surface travels | 16.0 |
| `surface_1_5_low` | Latitude 1:5 / low | Surface travels | 16.0 |
| `surface_2_3_low` | Latitude 2:3 / low | Surface travels | 16.0 |
| `surface_2_5_low` | Latitude 2:5 / low | Surface travels | 16.0 |
| `surface_3_4_low` | Latitude 3:4 / low | Surface travels | 16.0 |
| `surface_3_5_low` | Latitude 3:5 / low | Surface travels | 16.0 |
| `surface_1_2_wide` | Latitude 1:2 / wide | Surface travels | 16.0 |
| `surface_1_3_wide` | Latitude 1:3 / wide | Surface travels | 16.0 |
| `surface_1_4_wide` | Latitude 1:4 / wide | Surface travels | 16.0 |
| `surface_1_5_wide` | Latitude 1:5 / wide | Surface travels | 16.0 |
| `surface_2_3_wide` | Latitude 2:3 / wide | Surface travels | 16.0 |
| `surface_2_5_wide` | Latitude 2:5 / wide | Surface travels | 16.0 |
| `surface_3_4_wide` | Latitude 3:4 / wide | Surface travels | 16.0 |
| `surface_3_5_wide` | Latitude 3:5 / wide | Surface travels | 16.0 |
| `braid_1_2` | Braided tube / 1:2 | Braided loops | 16.0 |
| `braid_1_3` | Braided tube / 1:3 | Braided loops | 16.0 |
| `braid_1_4` | Braided tube / 1:4 | Braided loops | 16.0 |
| `braid_1_5` | Braided tube / 1:5 | Braided loops | 16.0 |
| `braid_2_3` | Braided tube / 2:3 | Braided loops | 16.0 |
| `braid_2_5` | Braided tube / 2:5 | Braided loops | 16.0 |
| `braid_3_4` | Braided tube / 3:4 | Braided loops | 16.0 |
| `braid_3_5` | Braided tube / 3:5 | Braided loops | 16.0 |
| `braid_1_6` | Braided tube / 1:6 | Braided loops | 16.0 |
| `braid_2_7` | Braided tube / 2:7 | Braided loops | 16.0 |
| `braid_3_7` | Braided tube / 3:7 | Braided loops | 16.0 |
| `braid_4_5` | Braided tube / 4:5 | Braided loops | 16.0 |
| `braid_4_7` | Braided tube / 4:7 | Braided loops | 16.0 |
| `braid_5_6` | Braided tube / 5:6 | Braided loops | 16.0 |
| `braid_5_7` | Braided tube / 5:7 | Braided loops | 16.0 |
| `braid_5_8` | Braided tube / 5:8 | Braided loops | 16.0 |
| `arm_coupled_01` | Coupled arm / 1:2 / 01 | Linkage portraits | 16.0 |
| `arm_coupled_02` | Coupled arm / 1:3 / 02 | Linkage portraits | 16.0 |
| `arm_coupled_03` | Coupled arm / 2:3 / 03 | Linkage portraits | 16.0 |
| `arm_coupled_04` | Coupled arm / 2:5 / 04 | Linkage portraits | 16.0 |
| `arm_coupled_05` | Coupled arm / 1:4 / 05 | Linkage portraits | 16.0 |
| `arm_coupled_06` | Coupled arm / 3:4 / 06 | Linkage portraits | 16.0 |
| `arm_coupled_07` | Coupled arm / 3:5 / 07 | Linkage portraits | 16.0 |
| `arm_coupled_08` | Coupled arm / 2:7 / 08 | Linkage portraits | 16.0 |
| `arm_coupled_09` | Coupled arm / 1:2 / 09 | Linkage portraits | 16.0 |
| `arm_coupled_10` | Coupled arm / 1:3 / 10 | Linkage portraits | 16.0 |
| `arm_coupled_11` | Coupled arm / 2:3 / 11 | Linkage portraits | 16.0 |
| `arm_coupled_12` | Coupled arm / 2:5 / 12 | Linkage portraits | 16.0 |
| `arm_coupled_13` | Coupled arm / 1:4 / 13 | Linkage portraits | 16.0 |
| `arm_coupled_14` | Coupled arm / 3:4 / 14 | Linkage portraits | 16.0 |
| `arm_coupled_15` | Coupled arm / 3:5 / 15 | Linkage portraits | 16.0 |
| `arm_coupled_16` | Coupled arm / 2:7 / 16 | Linkage portraits | 16.0 |
| `dwell_phrase_01` | Dwell and transfer / 01 | Dwell phrases | 16.0 |
| `dwell_phrase_02` | Dwell and transfer / 02 | Dwell phrases | 16.0 |
| `dwell_phrase_03` | Dwell and transfer / 03 | Dwell phrases | 16.0 |
| `dwell_phrase_04` | Dwell and transfer / 04 | Dwell phrases | 16.0 |
| `dwell_phrase_05` | Dwell and transfer / 05 | Dwell phrases | 16.0 |
| `dwell_phrase_06` | Dwell and transfer / 06 | Dwell phrases | 16.0 |
| `dwell_phrase_07` | Dwell and transfer / 07 | Dwell phrases | 16.0 |
| `dwell_phrase_08` | Dwell and transfer / 08 | Dwell phrases | 16.0 |
| `dwell_phrase_09` | Dwell and transfer / 09 | Dwell phrases | 16.0 |
| `dwell_phrase_10` | Dwell and transfer / 10 | Dwell phrases | 16.0 |
| `dwell_phrase_11` | Dwell and transfer / 11 | Dwell phrases | 16.0 |
| `dwell_phrase_12` | Dwell and transfer / 12 | Dwell phrases | 16.0 |
| `dwell_phrase_13` | Dwell and transfer / 13 | Dwell phrases | 16.0 |
| `dwell_phrase_14` | Dwell and transfer / 14 | Dwell phrases | 16.0 |
| `dwell_phrase_15` | Dwell and transfer / 15 | Dwell phrases | 16.0 |
| `dwell_phrase_16` | Dwell and transfer / 16 | Dwell phrases | 16.0 |
| `packet_alternating_2` | 2-packet alternating | Resonant packets | 8.0 |
| `packet_cascading_2` | 2-packet cascading | Resonant packets | 8.0 |
| `packet_crossing_2` | 2-packet crossing | Resonant packets | 8.0 |
| `packet_depth_2` | 2-packet depth | Resonant packets | 8.0 |
| `packet_alternating_3` | 3-packet alternating | Resonant packets | 8.0 |
| `packet_cascading_3` | 3-packet cascading | Resonant packets | 8.0 |
| `packet_crossing_3` | 3-packet crossing | Resonant packets | 8.0 |
| `packet_depth_3` | 3-packet depth | Resonant packets | 8.0 |
| `packet_alternating_4` | 4-packet alternating | Resonant packets | 8.0 |
| `packet_cascading_4` | 4-packet cascading | Resonant packets | 8.0 |
| `packet_crossing_4` | 4-packet crossing | Resonant packets | 8.0 |
| `packet_depth_4` | 4-packet depth | Resonant packets | 8.0 |
| `packet_alternating_5` | 5-packet alternating | Resonant packets | 8.0 |
| `packet_cascading_5` | 5-packet cascading | Resonant packets | 8.0 |
| `packet_crossing_5` | 5-packet crossing | Resonant packets | 8.0 |
| `packet_depth_5` | 5-packet depth | Resonant packets | 8.0 |
| `canon_01_close` | Canon 01 / close | Rhythmic canons | 8.0 |
| `canon_01_late` | Canon 01 / late | Rhythmic canons | 8.0 |
| `canon_02_close` | Canon 02 / close | Rhythmic canons | 8.0 |
| `canon_02_late` | Canon 02 / late | Rhythmic canons | 8.0 |
| `canon_03_close` | Canon 03 / close | Rhythmic canons | 8.0 |
| `canon_03_late` | Canon 03 / late | Rhythmic canons | 8.0 |
| `canon_04_close` | Canon 04 / close | Rhythmic canons | 8.0 |
| `canon_04_late` | Canon 04 / late | Rhythmic canons | 8.0 |
| `canon_05_close` | Canon 05 / close | Rhythmic canons | 8.0 |
| `canon_05_late` | Canon 05 / late | Rhythmic canons | 8.0 |
| `canon_06_close` | Canon 06 / close | Rhythmic canons | 8.0 |
| `canon_06_late` | Canon 06 / late | Rhythmic canons | 8.0 |
| `canon_07_close` | Canon 07 / close | Rhythmic canons | 8.0 |
| `canon_07_late` | Canon 07 / late | Rhythmic canons | 8.0 |
| `canon_08_close` | Canon 08 / close | Rhythmic canons | 8.0 |
| `canon_08_late` | Canon 08 / late | Rhythmic canons | 8.0 |
| `echo_regular_3` | 3-answer regular echo | Echo conversations | 8.0 |
| `echo_shrinking_3` | 3-answer shrinking echo | Echo conversations | 8.0 |
| `echo_expanding_3` | 3-answer expanding echo | Echo conversations | 8.0 |
| `echo_crossed_3` | 3-answer crossed echo | Echo conversations | 8.0 |
| `echo_regular_4` | 4-answer regular echo | Echo conversations | 8.0 |
| `echo_shrinking_4` | 4-answer shrinking echo | Echo conversations | 8.0 |
| `echo_expanding_4` | 4-answer expanding echo | Echo conversations | 8.0 |
| `echo_crossed_4` | 4-answer crossed echo | Echo conversations | 8.0 |
| `echo_regular_5` | 5-answer regular echo | Echo conversations | 8.0 |
| `echo_shrinking_5` | 5-answer shrinking echo | Echo conversations | 8.0 |
| `echo_expanding_5` | 5-answer expanding echo | Echo conversations | 8.0 |
| `echo_crossed_5` | 5-answer crossed echo | Echo conversations | 8.0 |
| `echo_regular_6` | 6-answer regular echo | Echo conversations | 8.0 |
| `echo_shrinking_6` | 6-answer shrinking echo | Echo conversations | 8.0 |
| `echo_expanding_6` | 6-answer expanding echo | Echo conversations | 8.0 |
| `echo_crossed_6` | 6-answer crossed echo | Echo conversations | 8.0 |
| `ladder_2_3_4_6` | Subdivision ladder / 2:3:4:6 | Subdivision ladders | 8.0 |
| `ladder_3_5_4_2` | Subdivision ladder / 3:5:4:2 | Subdivision ladders | 8.0 |
| `ladder_2_5_3_7` | Subdivision ladder / 2:5:3:7 | Subdivision ladders | 8.0 |
| `ladder_4_3_6_5` | Subdivision ladder / 4:3:6:5 | Subdivision ladders | 8.0 |
| `ladder_2_4_7_3` | Subdivision ladder / 2:4:7:3 | Subdivision ladders | 8.0 |
| `ladder_3_6_2_5` | Subdivision ladder / 3:6:2:5 | Subdivision ladders | 8.0 |
| `ladder_5_3_7_4` | Subdivision ladder / 5:3:7:4 | Subdivision ladders | 8.0 |
| `ladder_6_4_3_2` | Subdivision ladder / 6:4:3:2 | Subdivision ladders | 8.0 |
| `ladder_2_7_4_5` | Subdivision ladder / 2:7:4:5 | Subdivision ladders | 8.0 |
| `ladder_7_3_5_2` | Subdivision ladder / 7:3:5:2 | Subdivision ladders | 8.0 |
| `ladder_4_7_3_6` | Subdivision ladder / 4:7:3:6 | Subdivision ladders | 8.0 |
| `ladder_5_2_6_3` | Subdivision ladder / 5:2:6:3 | Subdivision ladders | 8.0 |
| `ladder_3_4_5_7` | Subdivision ladder / 3:4:5:7 | Subdivision ladders | 8.0 |
| `ladder_6_5_4_3` | Subdivision ladder / 6:5:4:3 | Subdivision ladders | 8.0 |
| `ladder_7_5_3_4` | Subdivision ladder / 7:5:3:4 | Subdivision ladders | 8.0 |
| `ladder_4_6_7_5` | Subdivision ladder / 4:6:7:5 | Subdivision ladders | 8.0 |
| `necklace_01` | Complementary necklace / 01 | Rhythm necklaces | 8.0 |
| `necklace_02` | Complementary necklace / 02 | Rhythm necklaces | 8.0 |
| `necklace_03` | Complementary necklace / 03 | Rhythm necklaces | 8.0 |
| `necklace_04` | Complementary necklace / 04 | Rhythm necklaces | 8.0 |
| `necklace_05` | Complementary necklace / 05 | Rhythm necklaces | 8.0 |
| `necklace_06` | Complementary necklace / 06 | Rhythm necklaces | 8.0 |
| `necklace_07` | Complementary necklace / 07 | Rhythm necklaces | 8.0 |
| `necklace_08` | Complementary necklace / 08 | Rhythm necklaces | 8.0 |
| `necklace_09` | Complementary necklace / 09 | Rhythm necklaces | 8.0 |
| `necklace_10` | Complementary necklace / 10 | Rhythm necklaces | 8.0 |
| `necklace_11` | Complementary necklace / 11 | Rhythm necklaces | 8.0 |
| `necklace_12` | Complementary necklace / 12 | Rhythm necklaces | 8.0 |
| `necklace_13` | Complementary necklace / 13 | Rhythm necklaces | 8.0 |
| `necklace_14` | Complementary necklace / 14 | Rhythm necklaces | 8.0 |
| `necklace_15` | Complementary necklace / 15 | Rhythm necklaces | 8.0 |
| `necklace_16` | Complementary necklace / 16 | Rhythm necklaces | 8.0 |
| `accent_walk_5_1` | Accent walk / 5 steps / stride 1 | Travelling accents | 16.0 |
| `accent_walk_5_2` | Accent walk / 5 steps / stride 2 | Travelling accents | 16.0 |
| `accent_walk_7_1` | Accent walk / 7 steps / stride 1 | Travelling accents | 16.0 |
| `accent_walk_7_2` | Accent walk / 7 steps / stride 2 | Travelling accents | 16.0 |
| `accent_walk_7_3` | Accent walk / 7 steps / stride 3 | Travelling accents | 16.0 |
| `accent_walk_8_1` | Accent walk / 8 steps / stride 1 | Travelling accents | 16.0 |
| `accent_walk_8_3` | Accent walk / 8 steps / stride 3 | Travelling accents | 16.0 |
| `accent_walk_9_1` | Accent walk / 9 steps / stride 1 | Travelling accents | 16.0 |
| `accent_walk_9_2` | Accent walk / 9 steps / stride 2 | Travelling accents | 16.0 |
| `accent_walk_9_4` | Accent walk / 9 steps / stride 4 | Travelling accents | 16.0 |
| `accent_walk_10_3` | Accent walk / 10 steps / stride 3 | Travelling accents | 16.0 |
| `accent_walk_11_2` | Accent walk / 11 steps / stride 2 | Travelling accents | 16.0 |
| `accent_walk_11_3` | Accent walk / 11 steps / stride 3 | Travelling accents | 16.0 |
| `accent_walk_12_5` | Accent walk / 12 steps / stride 5 | Travelling accents | 16.0 |
| `accent_walk_13_3` | Accent walk / 13 steps / stride 3 | Travelling accents | 16.0 |
| `accent_walk_13_5` | Accent walk / 13 steps / stride 5 | Travelling accents | 16.0 |
| `triplet_01_answer` | Broken triplets 01 / answer | Broken triplets | 8.0 |
| `triplet_01_turnaround` | Broken triplets 01 / turnaround | Broken triplets | 8.0 |
| `triplet_02_answer` | Broken triplets 02 / answer | Broken triplets | 8.0 |
| `triplet_02_turnaround` | Broken triplets 02 / turnaround | Broken triplets | 8.0 |
| `triplet_03_answer` | Broken triplets 03 / answer | Broken triplets | 8.0 |
| `triplet_03_turnaround` | Broken triplets 03 / turnaround | Broken triplets | 8.0 |
| `triplet_04_answer` | Broken triplets 04 / answer | Broken triplets | 8.0 |
| `triplet_04_turnaround` | Broken triplets 04 / turnaround | Broken triplets | 8.0 |
| `triplet_05_answer` | Broken triplets 05 / answer | Broken triplets | 8.0 |
| `triplet_05_turnaround` | Broken triplets 05 / turnaround | Broken triplets | 8.0 |
| `triplet_06_answer` | Broken triplets 06 / answer | Broken triplets | 8.0 |
| `triplet_06_turnaround` | Broken triplets 06 / turnaround | Broken triplets | 8.0 |
| `triplet_07_answer` | Broken triplets 07 / answer | Broken triplets | 8.0 |
| `triplet_07_turnaround` | Broken triplets 07 / turnaround | Broken triplets | 8.0 |
| `triplet_08_answer` | Broken triplets 08 / answer | Broken triplets | 8.0 |
| `triplet_08_turnaround` | Broken triplets 08 / turnaround | Broken triplets | 8.0 |
| `dialogue_3_4_5` | Meter dialogue / 3+4+5 | Meter dialogues | 6.0 |
| `dialogue_5_3_4` | Meter dialogue / 5+3+4 | Meter dialogues | 6.0 |
| `dialogue_3_5_2` | Meter dialogue / 3+5+2 | Meter dialogues | 5.0 |
| `dialogue_2_5_4` | Meter dialogue / 2+5+4 | Meter dialogues | 5.5 |
| `dialogue_4_3_2` | Meter dialogue / 4+3+2 | Meter dialogues | 4.5 |
| `dialogue_3_2_4_5` | Meter dialogue / 3+2+4+5 | Meter dialogues | 7.0 |
| `dialogue_5_2_3_4` | Meter dialogue / 5+2+3+4 | Meter dialogues | 7.0 |
| `dialogue_2_3_5_3` | Meter dialogue / 2+3+5+3 | Meter dialogues | 6.5 |
| `dialogue_3_4_3_5` | Meter dialogue / 3+4+3+5 | Meter dialogues | 7.5 |
| `dialogue_5_4_2_3` | Meter dialogue / 5+4+2+3 | Meter dialogues | 7.0 |
| `dialogue_2_4_5_2` | Meter dialogue / 2+4+5+2 | Meter dialogues | 6.5 |
| `dialogue_4_5_3_2` | Meter dialogue / 4+5+3+2 | Meter dialogues | 7.0 |
| `dialogue_3_5_4_3` | Meter dialogue / 3+5+4+3 | Meter dialogues | 7.5 |
| `dialogue_5_3_2_5` | Meter dialogue / 5+3+2+5 | Meter dialogues | 7.5 |
| `dialogue_2_5_3_5` | Meter dialogue / 2+5+3+5 | Meter dialogues | 7.5 |
| `dialogue_4_3_5_4` | Meter dialogue / 4+3+5+4 | Meter dialogues | 8.0 |
| `burst_3_5_2` | Alternating bursts / 3:5:2 | Alternating bursts | 8.0 |
| `burst_4_3_6` | Alternating bursts / 4:3:6 | Alternating bursts | 8.0 |
| `burst_5_2_4` | Alternating bursts / 5:2:4 | Alternating bursts | 8.0 |
| `burst_2_7_3` | Alternating bursts / 2:7:3 | Alternating bursts | 8.0 |
| `burst_3_4_5` | Alternating bursts / 3:4:5 | Alternating bursts | 8.0 |
| `burst_5_3_7` | Alternating bursts / 5:3:7 | Alternating bursts | 8.0 |
| `burst_6_2_5` | Alternating bursts / 6:2:5 | Alternating bursts | 8.0 |
| `burst_4_7_2` | Alternating bursts / 4:7:2 | Alternating bursts | 8.0 |
| `burst_7_3_4` | Alternating bursts / 7:3:4 | Alternating bursts | 8.0 |
| `burst_2_5_6` | Alternating bursts / 2:5:6 | Alternating bursts | 8.0 |
| `burst_5_7_3` | Alternating bursts / 5:7:3 | Alternating bursts | 8.0 |
| `burst_3_6_4` | Alternating bursts / 3:6:4 | Alternating bursts | 8.0 |
| `burst_4_5_7` | Alternating bursts / 4:5:7 | Alternating bursts | 8.0 |
| `burst_6_3_5` | Alternating bursts / 6:3:5 | Alternating bursts | 8.0 |
| `burst_7_4_3` | Alternating bursts / 7:4:3 | Alternating bursts | 8.0 |
| `burst_5_6_2` | Alternating bursts / 5:6:2 | Alternating bursts | 8.0 |

Copyright (c) 2026 Kieran Simkin. MIT; see repository LICENSE.
