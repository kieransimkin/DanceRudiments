#!/usr/bin/env python3
"""Build/check Continuum 04: original closed paths and rational-beat phrases."""
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
sys.path.insert(0,str(ROOT/'tools'))
from dancerudiments_authoring import emit_cpp, load_pack
from dancerudiments_authoring._reproducibility import checked_score
from build_atlas_collection import audit, canonical


def definitions():
    spec=importlib.util.spec_from_file_location('continuum_definitions',ROOT/'collections/continuum/definitions.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def rows_document(value):
    head={k:v for k,v in value.items() if k!='patterns'}
    return canonical(head)[:-1]+',"patterns":[\n'+',\n'.join(canonical(p) for p in value['patterns'])+'\n]}\n'


def build(check=False):
    module=definitions();score=module.document();score,pack=checked_score(score,ROOT,"continuum",check)
    if len(pack.patterns)!=module.PATTERN_COUNT:raise ValueError('Continuum count mismatch')
    previous=[]
    for file in ('initial.json','expansion.json','atlas.json'):
        previous.extend(load_pack(ROOT/'python/dancerudiments_authoring/packs'/file).patterns)
    audit(pack,previous)
    families=dict(sorted(Counter(p.provenance['family'] for p in pack.patterns).items()))
    if len(families)!=20 or set(families.values())!={16}:raise ValueError('Family balance mismatch')
    manifest=dict(collection_id=module.COLLECTION_ID,pattern_count=len(pack.patterns),
        sample_count=sum(p.period_pips for p in pack.patterns),
        table_payload_bytes=sum(p.period_pips for p in pack.patterns)*3*8,
        definitions_sha256=sha256((ROOT/'collections/continuum/definitions.py').read_bytes()).hexdigest(),
        pack_sha256=sha256(canonical(pack.to_dict()).encode()).hexdigest(),license='MIT',families=families,
        names=[p.name for p in pack.patterns],max_step=max(p.diagnostics['max_step'] for p in pack.patterns),
        distinctness_check='Exact arrays plus 256-point uniformly amplitude-normalized, cyclic phase signatures; not perceptual uniqueness')
    guide=['# Continuum 04: 320 new built-in movements','',
        '320 original presets across 20 families, appended to the previous 323 defaults. Total: **643**.',
        'No earlier pattern is removed, renamed, reordered or resampled. No new third-party data.',
        '', '## Use','', '```python','import dancerudiments as d',
        'position = d.sample("ribbon_2_5_deep", 48)','position = d.sample("surface_3_5_wide", -1)','```','',
        'C++ and TypeScript use their existing `sample(name, pip)` APIs. There is no pack-loading',
        'requirement. `continuum_pack()` optionally exposes compiled authoring data for inspection.',
        '', '## Families','', '| Family | Count |','| --- | ---: |']
    guide += ['| '+f+' | '+str(n)+' |' for f,n in families.items()]
    guide += ['', '## Regenerate','', '```sh','python tools/build_continuum_collection.py --check',
        'python tools/build_default_catalogue.py --check','```','',
        'Omit `--check` to regenerate after intentional source edits, then explicitly update the',
        'corresponding source hash in `collections/defaults.json`. Builders never silently unlock data.',
        'Authoring uses Python standard-library code. Runtime positions come from C++17 tables.',
        '', '## Interpretation and limits','',
        'All periods use quarter-note beats at 64 pips per beat. Rational event times survive until',
        'the final pip sampling; the runtime grid still cannot represent every event peak exactly.',
        'Geometry preserves relative XYZ scale. Source endpoints and oversampled values are checked',
        'before baking; duplicate arrays, grid-aligned phase/gain copies, warnings and large steps',
        'are rejected. Related variations may still look alike. The audit is not a perceptual metric.',
        'Closed positions do not promise continuous acceleration at every cusp or corner.',
        'Mechanism, arm and gesture names describe abstract trajectory studies, not validated',
        'dynamics, robot controls, motion capture, or full-body dance choreography.',
        '', 'Use bounded local translations and respect reduced-motion preferences. Do not map these',
        'curves to full-frame flashing. Fast/high-amplitude playback may remain uncomfortable.',
        '', '## Pattern reference','', '| Identifier | Title | Family | Beats |','| --- | --- | --- | ---: |']
    guide += ['| `'+p.name+'` | '+p.provenance['title']+' | '+p.provenance['family']+' | '+str(p.period_pips/64)+' |' for p in pack.patterns]
    guide += ['', 'Copyright (c) 2026 Kieran Simkin. MIT; see repository LICENSE.','']
    outputs={
        'collections/continuum/continuum.score.json':rows_document(score),
        'python/dancerudiments_authoring/packs/continuum.json':rows_document(pack.to_dict()),
        'include/dancerudiments/collections/continuum.hpp':emit_cpp(pack,'dancerudiments_continuum'),
        'collections/continuum/manifest.json':json.dumps(manifest,sort_keys=True,indent=2)+'\n',
        'collections/continuum/README.md':'\n'.join(guide)}
    for name,text in outputs.items():
        path=ROOT/name
        if check:
            if not path.is_file() or path.read_text(encoding='utf-8')!=text:raise ValueError('Missing/stale generated file: '+name)
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('w',encoding='utf-8',newline='\n') as f:f.write(text)
    print(('Checked' if check else 'Built')+f' {len(pack.patterns)} Continuum presets; '+
          f'{manifest["sample_count"]} samples; maximum step {manifest["max_step"]:.6f}')
    return pack


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:build(args.check)
    except (ValueError,OSError,KeyError,TypeError) as e:parser.exit(1,str(e)+'\n')
