#!/usr/bin/env python3
"""Build/check Expansion 03 / Motion Atlas. Offline, Python standard library only."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python'))
from dancerudiments_authoring import emit_cpp, load_pack
from dancerudiments_authoring._reproducibility import checked_score


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)


def phase_signature(pattern):
    """256 phase samples, one uniform amplitude scale, cyclic phase canonicalized.

    Detects copies that merely change period, uniform gain, or grid-aligned phase.
    It is not a perceptual-similarity or arbitrary time-warp equivalence test.
    """
    n=len(pattern.samples);rows=[]
    for i in range(256):
        q,r=divmod(i*n,256);a=pattern.samples[q];b=pattern.samples[(q+1)%n]
        rows.append(tuple(a[k]+(b[k]-a[k])*r/256 for k in range(3)))
    peak=max(abs(v) for row in rows for v in row)
    if peak<1e-10:raise ValueError('Stationary pattern: '+pattern.name)
    rows=tuple(tuple(round(v/peak,7) for v in row) for row in rows)
    return min(rows[i:]+rows[:i] for i in range(256))


def audit(pack, previous=()):
    exact={canonical(p.samples):p.name for p in previous}
    phase={phase_signature(p):p.name for p in previous}
    for p in pack.patterns:
        if p.diagnostics['warnings']:
            raise ValueError(p.name+': '+str(p.diagnostics['warnings']))
        if p.diagnostics['max_step']>.25:
            raise ValueError('Excessive per-pip displacement: '+p.name)
        if p.diagnostics['seam_position_error']>1e-7:
            raise ValueError('Loop reset: '+p.name)
        if any(not math.isfinite(v) or abs(v)>1 for row in p.samples for v in row):
            raise ValueError('Invalid position: '+p.name)
        e=canonical(p.samples);s=phase_signature(p)
        if e in exact or s in phase:
            raise ValueError('Duplicate motion: '+p.name+' / '+exact.get(e,phase.get(s,'')))
        exact[e]=p.name;phase[s]=p.name


def build(check=False):
    source=ROOT/'collections/atlas/definitions.py'
    spec=importlib.util.spec_from_file_location('atlas_definitions',source)
    definitions=importlib.util.module_from_spec(spec);spec.loader.exec_module(definitions)
    score=definitions.document();score,pack=checked_score(score,ROOT,"atlas",check)
    if len(pack.patterns)!=definitions.PATTERN_COUNT:
        raise ValueError('Atlas count mismatch')
    previous=[]
    for filename in ('initial.json','expansion.json'):
        previous.extend(load_pack(ROOT/'python/dancerudiments_authoring/packs'/filename).patterns)
    audit(pack,previous)
    families=dict(sorted(Counter(p.provenance['family'] for p in pack.patterns).items()))
    manifest=dict(collection_id=definitions.COLLECTION_ID,pattern_count=len(pack.patterns),
        sample_count=sum(p.period_pips for p in pack.patterns),
        pack_sha256=sha256(canonical(pack.to_dict()).encode()).hexdigest(),
        definitions_sha256=sha256(source.read_bytes()).hexdigest(),
        names=[p.name for p in pack.patterns],families=families,license='MIT',
        distinctness_check='Exact table and 256-point phase/gain-normalized cyclic signatures; not perceptual uniqueness',
        max_step=max(p.diagnostics['max_step'] for p in pack.patterns))
    # Compact JSON keeps a large pack small; one pattern per line permits useful diffs.
    def rows_document(value):
        head={k:v for k,v in value.items() if k!='patterns'}
        return canonical(head)[:-1]+',"patterns":[\n'+',\n'.join(canonical(p) for p in value['patterns'])+'\n]}\n'
    guide=['# Expansion 03: Motion Atlas','',
        '256 original presets in 16 families. All are registered as native defaults.',
        'The complete default catalogue contains 323 movements. No new third-party data.',
        '', 'Authoring is Python; movement playback is generated C++17. Every period is',
        'expressed in quarter-note beats at 64 pips per beat. No runtime Python,',
        'random-state evolution, network access, or JavaScript motion fallback is required.',
        '', '## Families','', '| Family | Count |','| --- | ---: |']
    guide.extend('| '+f+' | '+str(n)+' |' for f,n in families.items())
    guide += ['', '## Rebuild and inspect','', '```sh',
        'python tools/build_atlas_collection.py --check',
        'python tools/build_default_catalogue.py --check',
        '```','', 'Omit `--check` to regenerate tables after editing definitions. An intentional',
        'table change also requires updating its hash in `collections/defaults.json`.',
        'The hash lock is not silently rewritten by the builder.', '',
        'The release demo enumerates the native catalogue, including these defaults.',
        'Use its collection filter to isolate Motion Atlas, then choose a family.',
        'Use `atlas_pack()` only for inspection/export; `sample(name, pip)` needs no pack load.',
        '', '## Scope and interpretation','',
        'These are original preset studies, not extracted synth presets, official drum',
        'rudiment transcriptions, motion-capture data, or full-body choreography. Related',
        'presets deliberately explore ratios, event grids, geometry and curve shape.',
        'Duplicate checks do not promise that every related preset looks unrelated.',
        'Position closure is checked, but continuous acceleration is not guaranteed for',
        'piecewise or cusped curves. Apply bounded amplitudes and respect reduced motion.',
        '', '## Pattern reference','', '| Name | Title | Family | Beats |', '| --- | --- | --- | ---: |']
    guide.extend('| `'+p.name+'` | '+p.provenance['title']+' | '+p.provenance['family']+' | '+str(p.period_pips/64)+' |' for p in pack.patterns)
    guide += ['','Copyright (c) 2026 Kieran Simkin. MIT; see the repository LICENSE.','']
    outputs={
        'collections/atlas/atlas.score.json':rows_document(score),
        'python/dancerudiments_authoring/packs/atlas.json':rows_document(pack.to_dict()),
        'include/dancerudiments/collections/atlas.hpp':emit_cpp(pack,'dancerudiments_atlas'),
        'collections/atlas/manifest.json':json.dumps(manifest,sort_keys=True,indent=2)+'\n',
        'collections/atlas/README.md':'\n'.join(guide)}
    # Compute and validate all outputs before replacing any file.
    for name,text in outputs.items():
        path=ROOT/name
        if check:
            if not path.is_file() or path.read_text(encoding='utf-8')!=text:
                raise ValueError('Missing/stale generated file: '+name)
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('w',encoding='utf-8',newline='\n') as f:f.write(text)
    print(('Checked' if check else 'Built')+f' {len(pack.patterns)} atlas presets; '
          f'{manifest["sample_count"]} samples; maximum step {manifest["max_step"]:.6f}')
    return pack


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:build(args.check)
    except (ValueError,OSError,KeyError,TypeError) as exc:parser.exit(1,str(exc)+'\n')
