# Club Rhythms 05

**36 beat studies × four movement interpretations = 144 built-in movements.**
Appended to 643 existing defaults: total **787**. Existing tables and their order are unchanged.

## Listen and watch

The focused offline HTML plays newly synthesised percussion and bass cues, not sampled recordings.
Select a rhythm to compare its four mappings on one clock. Audio starts only after your action.
The full release demo also includes all defaults, including these new entries.

## Four mappings

| Suffix | Interpretation |
| --- | --- |
| `_bounce` | Kick-led downstroke, snare side accent and small hat detail. |
| `_step` | Alternating lateral kick/snare gestures with lighter upper-body-like detail. |
| `_orbit` | Percussion changes radius and angular speed; snare/bass also shape depth. |
| `_glide` | A slower, continuous phrase path with bass and drum excursions. |

These are abstract object trajectories, **not captured dancers, skeletal choreography, or
authoritative reconstructions of jacking, shuffling, skanking or other dance techniques**.
Positions use the existing native C++ sampler. Positive Y is drawn downward in the demo.

## Musical accuracy and interpretation

- “Four to the floor” is a quarter-note kick foundation, not a synonym for every EDM genre.
- Garage includes both four-four and broken two-step examples. Selected hats/rims swing;
  kick/snare anchors are not automatically dragged onto a global swing grid.
- The four-bar Amen study preserves the repeated opening, internal ghost snares, late
  closing backbeats and fourth-bar cymbal change. It is quantised and newly programmed:
  **not a sample, a sample-exact transcription, or the drummer’s original microtiming**.
  “Amen / no ghost snares” is a deliberately simplified comparison, not another canonical break.
- Drill distinguishes straight-grid 3+3+2 hat groups from actual triplet fills. Sparse and
  displaced snares are examples, not a definition of all drill. Grime has several contrasting grids.
- Jungle variants deliberately rearrange events. DnB two-step and half-time alternatives
  are not just the Amen with the BPM changed.
- Every BPM is an audition suggestion. Genre also involves sound, harmony, bass, arrangement
  and context; rhythm alone does not classify a recording. This collection is not exhaustive.
- Quarter-note beat is explicit. Fractions are retained in the event score until sampling.
  Runtime positions are 64 pips per beat: some swung/tuplet onsets lie between pips.
- Event gesture envelopes reach their peak at the musical onset, with short anticipatory
  motion. Simultaneous lanes sum, so the combined position need not have a peak at every hit.
- All overlaps are summed and uniformly scaled if needed, not individually hard-clipped.

## Build and use

```sh
python tools/build_club_collection.py --check
python tools/build_default_catalogue.py --check
python -m pip install .
python tools/build_club_demo.py --output dist/club-demo.html
```

The demo builder also requires clang++/wasm-ld. Playback requires only a WebAssembly-capable
browser. Python builds the data; C++ samples movement both in native consumers and the demo.

```python
import dancerudiments as d
p = d.sample("beat_amen_four_bar_bounce", 48)
p = d.sample("beat_ukg_two_step_glide", -1)
```

Optional authoring inspection: `from dancerudiments_authoring.collections import club_pack`.
The native defaults are already loaded; `club_pack()` is not a playback requirement.

## Rhythms and identifiers

Append `_bounce`, `_step`, `_orbit` or `_glide` to the base identifier below.

| Base identifier | Study | Genre/family | Bars | BPM |
| --- | --- | --- | ---: | ---: |
| `beat_four_floor` | Four to the floor / bare pulse | Four to the floor | 1 | 124 |
| `beat_house_classic` | House / kick-clap-offbeat hat | House | 2 | 124 |
| `beat_house_shuffle` | House / shuffled hats | House | 2 | 122 |
| `beat_house_jack` | Jackin house / ghost-kick turnaround | House | 2 | 126 |
| `beat_techno_drive` | Techno / straight driving pulse | Techno | 2 | 138 |
| `beat_techno_toms` | Techno / tom conversation | Techno | 2 | 134 |
| `beat_techno_broken` | Techno / broken kick study | Techno | 2 | 136 |
| `beat_techno_polymeter` | Techno / three-step percussion cycle | Techno | 3 | 140 |
| `beat_ukg_two_step` | UK garage / two-step foundation | UK garage | 2 | 132 |
| `beat_ukg_skip` | UK garage / skipping answer | UK garage | 2 | 132 |
| `beat_ukg_four_four` | UK garage / four-four shuffle | UK garage | 2 | 130 |
| `beat_speed_garage` | Speed garage / offbeat bass answers | UK garage | 2 | 136 |
| `beat_bassline` | Bassline / syncopated low-end hooks | Bassline | 2 | 138 |
| `beat_grime_sparse` | Grime / sparse square-cut backbeat | Grime | 2 | 140 |
| `beat_grime_syncopated` | Grime / displaced snare conversation | Grime | 2 | 140 |
| `beat_grime_half` | Grime / half-time negative space | Grime | 2 | 140 |
| `beat_drill_tresillo` | UK drill / grouped hats | UK drill | 2 | 144 |
| `beat_drill_displaced` | UK drill / moving second-bar snare | UK drill | 2 | 146 |
| `beat_drill_rolls` | UK drill / true triplet hat fill | UK drill | 2 | 144 |
| `beat_amen_four_bar` | Amen / four-bar structural study | Amen & jungle | 4 | 136 |
| `beat_amen_no_ghosts` | Amen / remove the ghost snares | Amen & jungle | 4 | 136 |
| `beat_jungle_chops` | Jungle / rearranged break fragments | Amen & jungle | 2 | 168 |
| `beat_jungle_ghosts` | Jungle / ghosts and snare rolls | Amen & jungle | 2 | 172 |
| `beat_jungle_switch` | Jungle / full-time to half-time answer | Amen & jungle | 4 | 170 |
| `beat_dnb_two_step` | Drum & bass / two-step foundation | Drum & bass | 2 | 174 |
| `beat_dnb_rolling` | Drum & bass / rolling ghosts | Drum & bass | 2 | 174 |
| `beat_dnb_half` | Drum & bass / half-time space | Drum & bass | 2 | 172 |
| `beat_dubstep_half` | Dubstep / half-step anchor | Dubstep | 2 | 140 |
| `beat_dubstep_skip` | Dubstep / skippy half-step | Dubstep | 2 | 140 |
| `beat_trap_trills` | Trap / half-time and hat trills | Trap | 2 | 140 |
| `beat_electro` | Electro / broken machine groove | Electro | 2 | 128 |
| `beat_trance` | Trance / offbeat lift | Trance | 2 | 138 |
| `beat_rave_breaks` | Rave / four-floor plus break layer | Breakbeat | 2 | 144 |
| `beat_dembow` | Reggaeton / dembow answer | Reggaeton | 2 | 96 |
| `beat_disco` | Disco / lively hat accents | Disco | 2 | 118 |
| `beat_amapiano` | Amapiano / shaker and bass-percussion study | Amapiano | 2 | 112 |

## Sources and rights

The sources explain musical structures; none of their audio, images, MIDI downloads or code
is bundled. The new encoding and movement mappings are MIT-licensed. That does not grant
rights to any original recording or imply that the underlying song is in the public domain.
Existing third-party notices from earlier collections remain unchanged.
Research references were checked on 29 September 2026. See `sources.json` for claim scope.

- Ableton Learning Music: Beat and tempo; Backbeats — https://learningmusic.ableton.com/make-beats/backbeats.html
- DrumsTheWord: Amen Break drum lesson — https://www.drumstheword.com/free-drum-lesson-amen-break-best-drum-beats-ever-amen-brother-gregory-coleman/
- Computer Music / MusicRadar: How to program an Amen-style break — https://www.musicradar.com/tuition/tech/how-to-program-an-amen-style-break-637374
- Native Instruments / Tim Cant: Everything you need to know about UK garage music and how to make it — https://blog.native-instruments.com/uk-garage-music/
- Attack Magazine: Drum programming: Jackin' House — https://www.attackmagazine.com/technique/beat-dissected/jackin-house/
- Attack Magazine: Hypnotic Techno Inspired by Phase Fatale's Love Is Destructive — https://www.attackmagazine.com/technique/beat-dissected/hypnotic-techno-inspired-by-phase-fatales-love-is-destructive/
- Future Music / MusicRadar: How to program 6 classic hip-hop, trap and grime beats — https://www.musicradar.com/how-to/how-to-program-6-classic-hip-hop-trap-and-grime-beats
- Native Instruments / Tim Cant: How to make a drill beat with haunting, dark undertones — https://blog.native-instruments.com/drill/
- Native Instruments / Tim Cant: 7 drum patterns every producer should know — https://blog.native-instruments.com/drum-patterns/
- Native Instruments / Sully: Sully: Sketches — https://blog.native-instruments.com/sketches-sully/
- Native Instruments: How to make electronic music: the ultimate guide — https://blog.native-instruments.com/electronic-music/
- Attack Magazine: Lo-Fi House & Breaks Fusion — https://www.attackmagazine.com/technique/beat-dissected/lo-fi-house-breaks-fusion-in-the-style-of-jamesjamesjames/
- Native Instruments / Tim Cant: What is reggaeton? How to make reggaeton beats that move you — https://blog.native-instruments.com/reggaeton/
- Attack Magazine: Nu-Disco: Live Groove — https://www.attackmagazine.com/technique/beat-dissected/nu-disco-live-groove/
- Native Instruments / Tim Cant: What is amapiano music? Its history and how to make it — https://blog.native-instruments.com/amapiano-music/

## Motion and audio comfort

Start at low volume. Keep translations bounded and small, especially at jungle/drill tempos.
The page starts paused, suspends on a hidden tab and reacts to reduced-motion preferences.
No full-frame brightness pulses, autoplay audio or third-party network requests are used.
