# Dancefloor 06 — more rhythms, more ways to move

This update appends **944 built-in movements**, bringing the native default library
from 787 to **1,731**. The two beat collections together expose **68 rhythmic
studies × 16 movement interpretations = 1,088 beat-based movements**. These are
not 1,088 different beats: 432 additions extend the existing 36 rhythms, and 512
apply all sixteen mappings to 32 new rhythms. The 144 existing Club 05 movements
and their source scores remain unchanged.

## Use the ordinary API

```python
import dancerudiments as d
assert len(d.catalogue()) == 1731
print(d.sample('beat_amen_four_bar_spring', -1).as_tuple())
print(d.sample('beat_four_floor_corkscrew', 64).as_tuple())
print(d.sample('beat_jersey_five_pendulum', 128).as_tuple())
```

```cpp
#include <dancerudiments/dance_rudiments.hpp>
auto p = dancerudiments::sample("beat_son_clave_32_figure8", pip_count);
```

```ts
import { bindNative, sample } from '@kieransimkin/dance-rudiments';
import createNative from '@kieransimkin/dance-rudiments/wasm';
bindNative(await createNative());
const p = sample('beat_reggae_one_drop_dive', 64);
```

No additional runtime pack load is required. Python is used for offline authoring;
all live movement sampling is C++, including the preview's embedded WASM sampler.
Generated C++ tables are committed, so normal C++ builds do not require Python.

## What is being modelled

The [collection reference](../collections/dancefloor/README.md) documents all 32
new scores, the 36 extended scores, sixteen mapping suffixes and source scopes.
Each new score is an original arrangement using documented rhythmic features,
not a sample-exact transcription, complete song, or definition of an entire genre.
Interviews support stylistic principles, not every authored note placement.

The Jersey foundation keeps its straight-grid five-kick cycle; it is not called
a triplet pattern. The son-clave examples preserve both bars and distinguish 3-2
from 2-3 direction. Straight rolling bass and true triplets remain separate.
Reggae one-drop, steppers and the illustrated rockers variant have different kick
placements. Suggested BPMs are audition settings, not tempo classification rules.

No audio recordings, tutorial MIDI files, notation images, factory synth presets
or third-party implementation code are imported. The new encoding/mapping code is
MIT; that does not grant rights to the referenced music. Existing source notices
in earlier collections remain applicable and unchanged.

## Sixteen interpretations

The retained mappings are **bounce, step, orbit and glide**. New mappings are
**surge, recoil, flutter, dive, pendulum, figure8, box, corkscrew, spiral, slalom,
spring and ricochet**. They redistribute instrument influence, use different path
geometries and change response timing. They are not merely gain/rate/axis copies.
Nevertheless, related scores can look similar; exact-array duplicate screening
is not perceptual uniqueness and sixteen mappings are not all conceivable motions.

Impact kernels generally begin before their hit so the isolated gesture peaks
at its musical onset. The **spring is causal**: it starts at the event and peaks
later. Phase-driven paths react via speed, radius and depth; they do not promise
a positional maximum at each drum hit. Overlapping kernels change the combined
extrema. These distinctions are visible on each demo card.

For a bare kick-only score, absent backbeat, high percussion and bass roles use
explicit kick fallbacks (0.70, 0.45 and 0.60 respectively). Fallbacks are recorded
in each new pattern's provenance. Synth bass is a timing cue, not a full 808
slide, log-drum, acid oscillator or reverse-bass instrument model.

Trajectories are bounded XYZ object offsets, not human joints, motion capture,
authentic dance instruction or physical linkage simulation. Positive Y is drawn
downwards. Alternative XY, XZ and YZ projections reveal genuine depth movement.

## Precise timing and deterministic loops

Source event times remain rational quarter-note beats. The final movement table
is sampled at 64 pips per beat; triplet/swing events can lie between two pips.
Audio retains those fractional timestamps. Changing BPM changes playback speed,
not a movement's samples or source grid.

Response tails wrap periodically. Integrated positive phase weights are evaluated
offline over one enclosing loop, never incrementally at runtime. Any seek order
returns the same sample. Tables have no forced last-equals-first rewrite: the last
stored sample is one pip before the endpoint. Uniform scaling bounds the whole
trajectory, rather than clipping axes independently.

## Reproduce and inspect

```sh
python tools/build_dancefloor_collection.py --check
python tools/build_default_catalogue.py --check
python -m pip install .
python tools/build_dancefloor_demo.py --output dist/dancefloor-demo.html
```

The collection builder uses only the Python standard library. Demo generation also
requires the rebuilt native extension plus clang++/wasm-ld. Browser checks require
Playwright/Chromium. No network access is needed for regeneration or playback.

`collections/dancefloor/recipes.json` is a compact recipe index tied to exact
rhythm objects, a mapping revision and definition hashes. It is **not** a generic
`dancerudiments.score-pack`; use the dedicated builder. `rhythms.json` retains
all source events, sixteen mapping descriptions and research references.

```python
from dancerudiments_authoring.collections import club_pack, dancefloor_pack
retained = club_pack()       # 144 original mappings
additions = dancefloor_pack() # 944 new defaults
subset = dancefloor_pack(['beat_amen_four_bar_spring'])
```

Per-pack safety limits remain unchanged. The general native release snapshot has
separate higher limits so it can enumerate the expanded default catalogue.

## Audition and release demos

The focused page exposes all 68 rhythms and all sixteen mappings. Choose any four
simultaneously, or use four mapping-bank buttons. Changing a mapping keeps the
musical clock running. Selecting a rhythm resets to its start and suggested tempo.
An already selected mapping swaps slots instead of silently duplicating a card.

The page starts paused. Press Play to enable synthetic percussion; lower the
volume before listening. No original Amen or other sample is embedded. The audio
stays on the same beat clock as the integer-pip visuals. The upper grid shows event
strength and exact fractional onset placement. Hidden tabs and changes to reduced
motion pause playback. Keep movement amplitude modest at fast tempos.

Every published release containing these tools additionally generates and renders
this page, screenshots, manifest, validation result, ZIP and checksums. The existing
full-catalogue and Club 05 demo assets are retained. Local `--in-memory` rendering
exists only for environments blocking file navigation, and is recorded distinctly
from the normal release workflow's `file://` loading test.
