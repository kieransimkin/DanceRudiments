# Initial 01 — source attribution and licences

The new code and original motions are MIT, as is DanceRudiments. This does not
relicense the imported data. Every generated pattern retains its own provenance.
Do not strip provenance from selected JSON exports or C++ headers.

## Adventure Kid Waveforms (four source tables)

Kristoffer Karl Axel Ekstrand / Adventure Kid. Teensy conversion by Marcelo Valeria.
CC0-1.0: https://creativecommons.org/publicdomain/zero/1.0/
Source repository: https://github.com/KristofferKarlAxelEkstrand/AKWF-FREE
Original CC0 notices are retained verbatim in sources/akwf/*.h.
Four 256-sample int16 tables are checksum-verified, circularly smoothed eight times
with [1/4, 1/2, 1/4], DC-centred and peak-scaled to .85. Musical periods and movement
interpretations are new. No MASSIVE, Serum, Vital or other factory preset bank is copied.

## Groove MIDI Dataset (one performance, two excerpts)

Groove MIDI Dataset (GMD), Google LLC. Gillick, Roberts, Engel, Eck and Bamman (2019),
Learning to Groove with Inverse Sequence Transformations. Anonymous drummer 1,
session 1, performance 1_funk_80_beat_4-4.mid, source tempo 80 BPM, 4/4.
Original source and drum mapping: https://magenta.withgoogle.com/datasets/groove
CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
Legal code: https://creativecommons.org/licenses/by/4.0/legalcode

The exact MIDI was retrieved from this mirror, which identifies it as original GMD data:
https://github.com/florento/MEI-GMD/blob/main/D1S1_001/1_funk_80_beat_4-4.mid
MIDI blob: 4d4889860dea1b6ed9b65ee395aff3eb75c76ad1
Decoded SHA-256: cd8ed5d6c2564221e7d53c6a5b80d67f229c29a9558203d743418950b9fa3355
No MEI transcription, engraved score, or original audio is included.

Changes: excerpts at source quarter-note beats 4–12 and 36–44; event ownership is
chosen by nearest-sixteenth time so early downbeats are retained. Played variants
preserve tick/480 fractions modulo the loop. Grid variants quantise the same hits to
quarter-beat positions, ties towards +infinity, without merging. Velocities are kept;
MIDI controllers and pedal note 44 are omitted. Each note is assigned an original,
peak-anchored movement gesture; the result is not a captured dancer or drumstick.
These four candidates are TWO excerpt pairs from ONE performance, not four recordings.
CC BY 4.0 requires attribution, a licence link and an indication of changes when shared.

## D3-ease (three easing loops)

Mike Bostock and Robert Penner; BSD-3-Clause. Selected bounce/back equations were
ported to offline Python and combined with new return curves to make closed loops.
Source file Git blob identities are embedded in the individual pattern metadata:
https://github.com/d3/d3-ease/blob/main/src/bounce.js
https://github.com/d3/d3-ease/blob/main/src/back.js
The full BSD-3-Clause notice in sources/d3-ease/LICENSE is also embedded in each
D3-derived pattern, so JSON and generated C++ subset exports retain it.
The separate Elastic ring pattern is an original equation, not a D3 import.

No endorsement by any source author or performer is implied. These notices describe
the inspected source licences, not a blanket licence for other assets from those projects.
