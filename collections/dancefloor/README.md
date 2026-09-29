# Dancefloor 06: rhythm and movement reference

**32 new studies; 68 rhythms each with 16 motion interpretations. 944 additions, 1,731 defaults.**

The original Club 05 scores and 144 motions are retained exactly. This collection adds twelve
mappings for each old rhythm and all sixteen mappings for each new rhythm. Use the ordinary
`sample(name, pip_count)` API; no separate pack load. See `docs/dancefloor.md` for use and scope.

## Movement mappings

| Suffix | Mapping | What changes | Timing anchor |
| --- | --- | --- | --- |
| `_bounce` | Kick-led bounce | Original Club 05 kick-led downstroke and side accents. | anticipatory peak |
| `_step` | Snare side-step | Original Club 05 alternating lateral kick and snare gestures. | anticipatory peak |
| `_orbit` | Percussion orbit | Original Club 05 event-weighted orbital speed, radius and depth. | phase modulation |
| `_glide` | Bass / phrase glide | Original Club 05 continuous phrase path with bass excursions. | mixed |
| `_surge` | Forward surge | Kick thrust through depth with contrasting snare lift and hat detail. | anticipatory peak |
| `_recoil` | Backbeat recoil | Snare pushes sideways; kick counters downward; delayed echo draws back. | peak and delayed response |
| `_flutter` | Upper-percussion flutter | Hat and shaker tremors over a wider kick/snare arc. | anticipatory peak |
| `_dive` | Bass-led dive | Bass drives a broad depth plunge with alternating drum counterweight. | anticipatory peak |
| `_pendulum` | Weighted pendulum | A hanging arc whose amplitude and angular speed respond to the score. | phase modulation |
| `_figure8` | Woven figure eight | Two crossing lobes expand at kicks with a lifted snare crossing. | phase modulation |
| `_box` | Rounded corner tour | Rhythm-weighted phase travels around four softened corners. | phase modulation |
| `_corkscrew` | Closed corkscrew | Two orbital turns ride a depth wave with percussion-driven radius. | phase modulation |
| `_spiral` | Breathing spiral | A contracting and expanding double-turn path with a continuous seam. | phase modulation |
| `_slalom` | Drum slalom | S-shaped travel with kick lift, snare cutbacks and depth counter-motion. | mixed |
| `_spring` | Causal spring | An event starts at rest, then drives a damped ringing excursion. | causal onset; peaks after hit |
| `_ricochet` | Directional ricochet | Successive onsets send smooth excursions toward a cyclic series of targets. | anticipatory peak |

## New rhythm studies

| Base identifier | Study | Family | BPM |
| --- | --- | --- | ---: |
| `beat_jersey_five` | Jersey / five-kick foundation | Jersey club | 142 |
| `beat_jersey_call` | Jersey / call and turnaround | Jersey club | 144 |
| `beat_footwork_triplet` | Footwork / triplet bass reply | Footwork | 160 |
| `beat_footwork_sparse` | Footwork / interrupted half-time | Footwork | 160 |
| `beat_funky_toms` | UK funky / tom-led skips | UK funky | 130 |
| `beat_funky_syncopated` | UK funky / broken response | UK funky | 132 |
| `beat_broken_push` | Broken beat / early-and-late answers | Broken beat | 124 |
| `beat_broken_shuffle` | Broken beat / shuffled rim circuit | Broken beat | 126 |
| `beat_afro_bell` | Afro house / bell and kick weave | Afro house | 120 |
| `beat_afro_cross` | Afro house / three-over-four percussion | Afro house | 122 |
| `beat_gqom_space` | Gqom / broken-kick space study | Gqom | 124 |
| `beat_gqom_exchange` | Gqom / staggered drum exchange | Gqom | 126 |
| `beat_baile_toms` | Baile funk / low-drum conversation | Brazilian funk | 132 |
| `beat_baile_response` | Baile funk / syncopated answer | Brazilian funk | 140 |
| `beat_reggae_one_drop` | Reggae / one-drop foundation | Reggae and dub | 76 |
| `beat_reggae_steppers` | Dub / steppers foundation | Reggae and dub | 80 |
| `beat_reggae_rockers` | Reggae / kick-on-one-and-three study | Reggae and dub | 82 |
| `beat_son_clave_32` | Latin club / 3-2 son clave | Latin clave hybrids | 120 |
| `beat_son_clave_23` | Latin club / 2-3 son clave | Latin clave hybrids | 120 |
| `beat_psy_rolling` | Psy / straight rolling bass gaps | Trance and hard dance | 145 |
| `beat_psy_offbeat` | Trance / offbeat bass exchange | Trance and hard dance | 140 |
| `beat_hard_reverse` | Hard dance / delayed bass swell cues | Trance and hard dance | 150 |
| `beat_italo_machine` | Italo / machine rim conversation | Disco and electro | 118 |
| `beat_electro_robot` | Electro / asymmetric machine break | Disco and electro | 128 |
| `beat_acid_percussion` | Acid house / syncopated machine accents | House and techno II | 126 |
| `beat_techno_rumble` | Techno / delayed low-end answer | House and techno II | 140 |
| `beat_ukg_rim_shuffle` | Garage / rim-led skipping pocket | UK garage II | 133 |
| `beat_dnb_push` | DnB / kick pickup and ghost reply | Jungle and DnB II | 172 |
| `beat_jungle_switchback` | Jungle / two-bar switchback | Jungle and DnB II | 168 |
| `beat_amapiano_answer` | Amapiano / log-like bass answer | Amapiano II | 112 |
| `beat_dancehall_space` | Dancehall / spacious offbeat replies | Dancehall and reggaeton | 96 |
| `beat_dembow_push` | Reggaeton / dembow with pickup answer | Dancehall and reggaeton | 98 |

## Interpretation notes

**Jersey / five-kick foundation:** Kick on zero-based sixteenths 0,4,8,11,14: two quarters then 3+3+2 sixteenths. Not triplets. Accompaniment is authored.
**Jersey / call and turnaround:** Same signature kick cycle, original two-bar response and quiet snare pickup; not a new canonical kick pattern.
**Footwork / triplet bass reply:** Authored sparse drum/bass conversation. Bass replies include genuine thirds of a beat; not a genre-wide transcription.
**Footwork / interrupted half-time:** An original interrupted 808-style study; the suggested tempo is an audition setting, not a classification rule.
**UK funky / tom-led skips:** Tom/rim motion is an original response to Roska’s discussion of skippy, travelling percussion, not one of his tracks.
**UK funky / broken response:** Kick gaps and percussion answers produce a different phrase without applying swing to the main anchors.
**Broken beat / early-and-late answers:** Original broken-beat study: the first-bar closing snare is displaced by half a beat. Not a universal broken-beat grid.
**Broken beat / shuffled rim circuit:** Only selected upper-percussion off-sixteenths swing; bass and main drums keep their authored positions.
**Afro house / bell and kick weave:** Four-floor foundation with an original interlocking bell/tom arrangement. Rim synthesises a bell-like timing cue only.
**Afro house / three-over-four percussion:** Three equal tom accents per four-beat bar are retained as exact fractions over the quarter-kick layer.
**Gqom / broken-kick space study:** Original sparse broken-kick design informed by DJ Lag’s description; no named Gqom track is transcribed.
**Gqom / staggered drum exchange:** A second authored conversation between low drums. Synthetic toms are timing cues, not authentic sample reconstruction.
**Baile funk / low-drum conversation:** Original low-drum/syncopation study, not a definitive tamborzão transcription. Distinct from drift phonk.
**Baile funk / syncopated answer:** Original programmed variation using contrasting low/percussive answers; not a recording or scene-complete model.
**Reggae / one-drop foundation:** Kick and cross-stick coincide on beat 3 with beat 1 left empty in those lanes; bass is an original accompaniment.
**Dub / steppers foundation:** Quarter-note kick with beat-3 cross-stick; the same four-floor kick has a different surrounding rhythmic context.
**Reggae / kick-on-one-and-three study:** Illustrative rockers-style kick on 1 and 3; variants exist. Not every rockers groove uses this exact grid.
**Latin club / 3-2 son clave:** Two-bar 3-2 son clave: 1, & of 2, 4 | 2, 3. Club kick/shaker orchestration is original.
**Latin club / 2-3 son clave:** Two-bar 2-3 son clave reverses the two sides. Not interchangeable against an unchanged melodic phrase.
**Psy / straight rolling bass gaps:** Original kick-bass-bass-bass sixteenth arrangement: three straight subdivisions, not a triplet. Short synth cues stand in for bass articulation.
**Trance / offbeat bass exchange:** Quarter kicks alternate with offbeat eighth-note bass; supporting hats and claps are authored.
**Hard dance / delayed bass swell cues:** Late-beat bass onsets cue a swelling response. Audio is simple bass synthesis, not a complete reverse-bass sound-design recreation.
**Italo / machine rim conversation:** Original machine-style arrangement: straight kick/backbeat beneath a busy rim part and subtly shuffled hats.
**Electro / asymmetric machine break:** Original broken electro study using a drum-machine backbeat and syncopated kick/bass; no sampled break.
**Acid house / syncopated machine accents:** Original house grid with an asymmetric bass rhythm. This is not a 303 timbre emulator; acid character cannot be encoded by rhythm alone.
**Techno / delayed low-end answer:** Explicit delayed low-end cues approximate a kick-tail conversation, not acoustic convolution or a canonical techno beat.
**Garage / rim-led skipping pocket:** An original rim-led two-step variant; selected upper-percussion subdivisions use 5:3 swing.
**DnB / kick pickup and ghost reply:** Original rolling break with a late first-bar pickup and quieter internal snares; not another recorded break transcription.
**Jungle / two-bar switchback:** Original break rearrangement with changing second-bar snare placement. Amen 05 remains unchanged as a separate study.
**Amapiano / log-like bass answer:** An original low-end/percussion call-and-response. Synth bass marks log-drum events but is not an authentic log-drum instrument model.
**Dancehall / spacious offbeat replies:** An original sparse dancehall-influenced arrangement with displaced rim replies; not a historical riddim transcription.
**Reggaeton / dembow with pickup answer:** Common dembow-style snare displacement under quarter kicks with an original second-bar pickup and bass phrase.

## Extended existing rhythms

`four_floor`, `house_classic`, `house_shuffle`, `house_jack`, `techno_drive`, `techno_toms`, `techno_broken`, `techno_polymeter`, `ukg_two_step`, `ukg_skip`, `ukg_four_four`, `speed_garage`, `bassline`, `grime_sparse`, `grime_syncopated`, `grime_half`, `drill_tresillo`, `drill_displaced`, `drill_rolls`, `amen_four_bar`, `amen_no_ghosts`, `jungle_chops`, `jungle_ghosts`, `jungle_switch`, `dnb_two_step`, `dnb_rolling`, `dnb_half`, `dubstep_half`, `dubstep_skip`, `trap_trills`, `electro`, `trance`, `rave_breaks`, `dembow`, `disco`, `amapiano`

## Sources

Checked 29 September 2026. References support the stated features, not every
authored event. No third-party recordings, MIDI, charts, presets or code are bundled.

- Native Instruments / Tim Cant: What is amapiano music? Its history and how to make it — https://blog.native-instruments.com/amapiano-music/
  Scope: Slower house-adjacent percussive grooves, shakers and substantial bass activity. Our log-drum-style bass rhythm is an original study.
- DrumsTheWord: Amen Break drum lesson — https://www.drumstheword.com/free-drum-lesson-amen-break-best-drum-beats-ever-amen-brother-gregory-coleman/
  Scope: Four-bar structure, repeated opening bars, internal snares, displaced closing backbeats and fourth-bar crash.
- Computer Music / MusicRadar: How to program an Amen-style break — https://www.musicradar.com/tuition/tech/how-to-program-an-amen-style-break-637374
  Scope: Ride eighths, kick doubles, dynamic contrast, later displaced snares, pedal hat; manually programmed timing is not the original performance.
- Native Instruments / Tim Cant: What is reggaeton? How to make reggaeton beats that move you — https://blog.native-instruments.com/reggaeton/
  Scope: Dembow quarter kicks and displaced snare answers at 0.75/1.5/2.75/3.5 beats in a 4/4 bar.
- Attack Magazine: Nu-Disco: Live Groove — https://www.attackmagazine.com/technique/beat-dissected/nu-disco-live-groove/
  Scope: Disco-related acoustic groove possibilities include four-on-floor or a looser first/third-beat kick.
- Native Instruments / Tim Cant: 7 drum patterns every producer should know — https://blog.native-instruments.com/drum-patterns/
  Scope: DnB two-step kick on first/sixth eighths, snare on 2/4, eighth hats with lighter in-between notes; house and funk examples.
- Native Instruments / Tim Cant: How to make a drill beat with haunting, dark undertones — https://blog.native-instruments.com/drill/
  Scope: UK drill grouped 3+3+2 hats, moving snare, sparse kicks and portamento bass; not a universal rule for all drill.
- Native Instruments: How to make electronic music: the ultimate guide — https://blog.native-instruments.com/electronic-music/
  Scope: Straight house/disco, broken electro, rapid jungle/DnB and spacious dubstep half-time; synthesis and arrangement also define genre.
- Ableton Learning Music: Beat and tempo; Backbeats — https://learningmusic.ableton.com/make-beats/backbeats.html
  Scope: Quarter-note kicks with second/fourth-beat backbeats; common house/techno foundation.
- Native Instruments / Tim Cant: Everything you need to know about UK garage music and how to make it — https://blog.native-instruments.com/uk-garage-music/
  Scope: Both four-to-the-floor and 2-step; syncopated kicks, backbeats and delayed sixteenth hats.
- Future Music / MusicRadar: How to program 6 classic hip-hop, trap and grime beats — https://www.musicradar.com/how-to/how-to-program-6-classic-hip-hop-trap-and-grime-beats
  Scope: Grime's approximately 140 BPM grids, displaced/repeated/syncopated snares; trap hat subdivisions.
- Attack Magazine: Drum programming: Jackin' House — https://www.attackmagazine.com/technique/beat-dissected/jackin-house/
  Scope: Four-on-floor with swing, ghost kicks and additional clap/snare activity.
- Native Instruments / Sully: Sully: Sketches — https://blog.native-instruments.com/sketches-sully/
  Scope: Chopped breaks, pitched percussive dialogue and jungle rhythmic composition.
- Attack Magazine: Lo-Fi House & Breaks Fusion — https://www.attackmagazine.com/technique/beat-dissected/lo-fi-house-breaks-fusion-in-the-style-of-jamesjamesjames/
  Scope: Combining break fragments with a four-on-floor kick, without importing that recording or tutorial MIDI.
- Attack Magazine: Hypnotic Techno Inspired by Phase Fatale's Love Is Destructive — https://www.attackmagazine.com/technique/beat-dissected/hypnotic-techno-inspired-by-phase-fatales-love-is-destructive/
  Scope: Percussion-heavy repetitive techno production; our grids are independent studies, not the article's exact pattern.
- Native Instruments / Tim Cant: How to make a Jersey club track — https://blog.native-instruments.com/jersey-club/
  Scope: Five-kick foundation at zero-based sixteenth positions 0,4,8,11,14; dotted-eighth spacing, not triplets. Our other lanes are independently arranged.
- Attack Magazine: Creating 808-style basslines for jungle, trap and footwork — https://www.attackmagazine.com/technique/tutorials/creating-808-style-basslines-for-jungle-trap-and-footwork/
  Scope: Bass/drum interplay and 808-style sound design in these styles. Our exact triplet and sparse scores are authored examples, not a transcription or universally prescribed grid.
- Red Bull Music Academy / Roska: Roska lecture — https://www.redbullmusicacademy.com/lectures/roska-the-kiss-factor/
  Scope: The producer describes skippy, travelling percussion and contrasts rolling/broken approaches; exact event placements here are original.
- Native Instruments / Tim Cant: Afro house production 101 — https://blog.native-instruments.com/afro-house-production-101/
  Scope: Four-floor foundation with prominent syncopated percussion. Does not prescribe our exact bell/tom score.
- Native Instruments / AMEME: AMEME interview — https://blog.native-instruments.com/ameme/
  Scope: Producer discussion of polyrhythms and offbeat sequencing; our three-over-four score is an original demonstration.
- Four Four / DJ Lag: DJ Lag talks South African music, his global rise and more — https://fourfour.co/dj-lag-talks-south-african-music-pride-his-global-rise-more-interview/
  Scope: Artist perspective on Gqom and broken rhythms. Supports stylistic context only; our two-bar grids are not artist transcriptions.
- Splice / interviewed Brazilian producers: Brazilian funk vs. phonk — https://splice.com/blog/brazilian-funk-vs-phonk/
  Scope: Producer perspectives on different Brazilian funk styles and their distinction from phonk; exact low-drum arrangements are our own.
- Hudson Music / Lerryns Hernandez: Reggae for Drumset — https://hudsonmusic.com/product/reggae-for-drumset/
  Scope: Teacher-published method distinguishes one-drop, rockers and steppers and multiple variations. It is not the source of copied charts or media.
- DrumFaster: Reggae one-drop lesson — https://drumfaster.com/play/classics/reggae-one-drop/
  Scope: Kick and cross-stick on beat three; the supplied bass and tom embellishments are original. Text/search verification only, page fetch unavailable during this pass.
- Veena Studio: Make reggae music — https://www.veena.studio/make/reggae-music
  Scope: Authored tutorial distinguishes beat-3 one-drop, quarter-kick steppers and a beat-1/3 rockers study. Other rockers forms exist.
- Total Drummer / Matthew Dean: Son clave drum pattern — https://www.totaldrummer.com/son-clave-drum-pattern/
  Scope: Five-stroke two-bar clave with reversible 3-side/2-side ordering. Our drum-kit orchestration is independently authored.
- Soundbrenner: Son clave — https://www.soundbrenner.com/blogs/articles/son-clave
  Scope: Explicit 3-2 placements: 1, & of 2, 4 | 2,3 and reversed 2-3. We preserve the full two-bar cycle.
- Psytrance Blueprint / MoRsei: Triplets into rolling bass — https://www.psytrance-blueprint.com/tutorials/morsei-triplets-rolling-bass/
  Scope: Producer tutorial distinguishes triplet and straight rolling grooves. Our KBBB straight-sixteenth score is an illustrative arrangement, not its track transcription.
- Native Instruments / Kilbourne: Patch and play: Kilbourne — https://blog.native-instruments.com/patch-and-play-kilbourne/
  Scope: Producer describes late-beat bass emphasis, reverse-bass swells and modulation within each beat. We import no preset or audio.
- Attack Magazine: Italo-disco beat construction — https://www.attackmagazine.com/technique/beat-dissected/make-a-beat-inspired-by-alexander-robotnicks-problemes-damour/
  Scope: Four-floor/backbeat and machine percussion vocabulary. Our rim/bass placements are not the named track or tutorial MIDI.
- Attack Magazine: Organic tech-house drum programming — https://www.attackmagazine.com/technique/beat-dissected/organic-tech-house/
  Scope: Selective shuffle, organic percussion and layered backbeat practice; not a license to reproduce supplied samples.
- Native Instruments / Tim Cant: What is trance music? — https://blog.native-instruments.com/trance-music/
  Scope: Quarter-kick trance foundation and offbeat bass context. Our grid is an authored study.
- Native Instruments / Tim Cant: What is reggaeton? — https://blog.native-instruments.com/reggaeton/
  Scope: Dembow quarter-kick/displaced-snare foundation. Our pickups, bass and dancehall-influenced variant are independent arrangements.
- Drumeo / Peter Szendofi: Drum and bass / jungle beats — https://www.drumeo.com/beat/drum-bass-jungle-beats/
  Scope: A drummer demonstrates multiple approaches rather than one universal drum-and-bass pattern.
