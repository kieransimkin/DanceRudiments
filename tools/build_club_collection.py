#!/usr/bin/env python3
"""Build or verify 36 rhythm studies and their 144 C++ movement interpretations."""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from dancerudiments_authoring import emit_cpp, load_pack
from dancerudiments_authoring._reproducibility import checked_score

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)

def definitions():
    spec=importlib.util.spec_from_file_location('club_definitions',ROOT/'collections/club/definitions.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def rows_document(value):
    head={k:v for k,v in value.items() if k!='patterns'}
    return canonical(head)[:-1]+',"patterns":[\n'+',\n'.join(canonical(p) for p in value['patterns'])+'\n]}\n'

def build(check=False):
    module=definitions();rhythms=module.rhythm_scores();score=module.document();score,pack=checked_score(score,ROOT,"club",check)
    if len(rhythms)!=36 or len(pack.patterns)!=144:raise ValueError('Unexpected Club Rhythms count')
    seen={}
    for p in pack.patterns:
        digest=sha256(canonical(p.samples).encode()).hexdigest()
        if digest in seen:raise ValueError('Exact duplicate: '+p.name+' / '+seen[digest])
        seen[digest]=p.name
        if p.diagnostics['max_step']>.35 or p.diagnostics['seam_position_error']>1e-6:
            raise ValueError('Invalid movement boundary: '+p.name)
    for filename in ('initial','expansion','atlas','continuum'):
        for p in load_pack(ROOT/f'python/dancerudiments_authoring/packs/{filename}.json').patterns:
            if sha256(canonical(p.samples).encode()).hexdigest() in seen:
                raise ValueError('Exact duplicate of earlier default '+p.name)
    manifest=dict(collection_id=module.COLLECTION_ID,rhythm_count=36,pattern_count=144,
        sample_count=sum(p.period_pips for p in pack.patterns),
        table_payload_bytes=sum(p.period_pips for p in pack.patterns)*24,
        definitions_sha256=sha256((ROOT/'collections/club/definitions.py').read_bytes()).hexdigest(),
        sources_sha256=sha256((ROOT/'collections/club/sources.json').read_bytes()).hexdigest(),
        pack_sha256=sha256(canonical(pack.to_dict()).encode()).hexdigest(),
        names=[p.name for p in pack.patterns],families=dict(sorted(Counter(p.provenance['family'] for p in pack.patterns).items())),
        max_step=max(p.diagnostics['max_step'] for p in pack.patterns),
        warnings={p.name:p.diagnostics['warnings'] for p in pack.patterns if p.diagnostics['warnings']},
        license='MIT',distinctness_check='Exact arrays only. Related genre variants and four mappings per rhythm are intentional.')
    guide=['# Club Rhythms 05','',
        '**36 beat studies × four movement interpretations = 144 built-in movements.**',
        'Appended to 643 existing defaults: total **787**. Existing tables and their order are unchanged.',
        '', '## Listen and watch','',
        'The focused offline HTML plays newly synthesised percussion and bass cues, not sampled recordings.',
        'Select a rhythm to compare its four mappings on one clock. Audio starts only after your action.',
        'The full release demo also includes all defaults, including these new entries.',
        '', '## Four mappings','',
        '| Suffix | Interpretation |','| --- | --- |',
        '| `_bounce` | Kick-led downstroke, snare side accent and small hat detail. |',
        '| `_step` | Alternating lateral kick/snare gestures with lighter upper-body-like detail. |',
        '| `_orbit` | Percussion changes radius and angular speed; snare/bass also shape depth. |',
        '| `_glide` | A slower, continuous phrase path with bass and drum excursions. |','',
        'These are abstract object trajectories, **not captured dancers, skeletal choreography, or',
        'authoritative reconstructions of jacking, shuffling, skanking or other dance techniques**.',
        'Positions use the existing native C++ sampler. Positive Y is drawn downward in the demo.',
        '', '## Musical accuracy and interpretation','',
        '- “Four to the floor” is a quarter-note kick foundation, not a synonym for every EDM genre.',
        '- Garage includes both four-four and broken two-step examples. Selected hats/rims swing;',
        '  kick/snare anchors are not automatically dragged onto a global swing grid.',
        '- The four-bar Amen study preserves the repeated opening, internal ghost snares, late',
        '  closing backbeats and fourth-bar cymbal change. It is quantised and newly programmed:',
        '  **not a sample, a sample-exact transcription, or the drummer’s original microtiming**.',
        '  “Amen / no ghost snares” is a deliberately simplified comparison, not another canonical break.',
        '- Drill distinguishes straight-grid 3+3+2 hat groups from actual triplet fills. Sparse and',
        '  displaced snares are examples, not a definition of all drill. Grime has several contrasting grids.',
        '- Jungle variants deliberately rearrange events. DnB two-step and half-time alternatives',
        '  are not just the Amen with the BPM changed.',
        '- Every BPM is an audition suggestion. Genre also involves sound, harmony, bass, arrangement',
        '  and context; rhythm alone does not classify a recording. This collection is not exhaustive.',
        '- Quarter-note beat is explicit. Fractions are retained in the event score until sampling.',
        '  Runtime positions are 64 pips per beat: some swung/tuplet onsets lie between pips.',
        '- Event gesture envelopes reach their peak at the musical onset, with short anticipatory',
        '  motion. Simultaneous lanes sum, so the combined position need not have a peak at every hit.',
        '- All overlaps are summed and uniformly scaled if needed, not individually hard-clipped.',
        '', '## Build and use','', '```sh','python tools/build_club_collection.py --check',
        'python tools/build_default_catalogue.py --check','python -m pip install .',
        'python tools/build_club_demo.py --output dist/club-demo.html','```','',
        'The demo builder also requires clang++/wasm-ld. Playback requires only a WebAssembly-capable',
        'browser. Python builds the data; C++ samples movement both in native consumers and the demo.',
        '', '```python','import dancerudiments as d','p = d.sample("beat_amen_four_bar_bounce", 48)',
        'p = d.sample("beat_ukg_two_step_glide", -1)','```','',
        'Optional authoring inspection: `from dancerudiments_authoring.collections import club_pack`.',
        'The native defaults are already loaded; `club_pack()` is not a playback requirement.',
        '', '## Rhythms and identifiers','',
        'Append `_bounce`, `_step`, `_orbit` or `_glide` to the base identifier below.',
        '', '| Base identifier | Study | Genre/family | Bars | BPM |','| --- | --- | --- | ---: | ---: |']
    guide += [f"| `beat_{r['id']}` | {r['title']} | {r['genre']} | {r['bars']} | {r['bpm']} |" for r in rhythms]
    guide += ['', '## Sources and rights','',
        'The sources explain musical structures; none of their audio, images, MIDI downloads or code',
        'is bundled. The new encoding and movement mappings are MIT-licensed. That does not grant',
        'rights to any original recording or imply that the underlying song is in the public domain.',
        'Existing third-party notices from earlier collections remain unchanged.',
        'Research references were checked on 29 September 2026. See `sources.json` for claim scope.','']
    guide += [f"- {s['publisher']}: {s['title']} — {s['url']}" for s in module.SOURCES.values()]
    guide += ['', '## Motion and audio comfort','',
        'Start at low volume. Keep translations bounded and small, especially at jungle/drill tempos.',
        'The page starts paused, suspends on a hidden tab and reacts to reduced-motion preferences.',
        'No full-frame brightness pulses, autoplay audio or third-party network requests are used.','']
    data=dict(format='dancerudiments.rhythm-studies',schema_version=1,beat_unit='quarter_note',
              collection_id=module.COLLECTION_ID,mappings=list(module.MAPPINGS),rhythms=rhythms,sources=module.SOURCES)
    outputs={'collections/club/club.score.json':rows_document(score),
        'collections/club/rhythms.json':json.dumps(data,sort_keys=True,indent=2)+'\n',
        'python/dancerudiments_authoring/packs/club.json':rows_document(pack.to_dict()),
        'include/dancerudiments/collections/club.hpp':emit_cpp(pack,'dancerudiments_club'),
        'collections/club/manifest.json':json.dumps(manifest,sort_keys=True,indent=2)+'\n',
        'collections/club/README.md':'\n'.join(guide)}
    for name,text in outputs.items():
        path=ROOT/name
        if check:
            if not path.is_file() or path.read_text(encoding='utf-8')!=text:raise ValueError('Missing/stale generated file: '+name)
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('w',encoding='utf-8',newline='\n') as f:f.write(text)
    print(('Checked' if check else 'Built')+f' 36 rhythms / 144 movements; {manifest["sample_count"]} samples; max step {manifest["max_step"]:.6f}')
    return pack

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:build(args.check)
    except (ValueError,OSError,TypeError,KeyError) as e:parser.exit(1,str(e)+'\n')
