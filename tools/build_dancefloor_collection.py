#!/usr/bin/env python3
"""Build 944 default additions: 32 new rhythms plus 12 extra mappings for all 68."""
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
from dancerudiments_authoring.model import CompiledPack, CompiledPattern


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def definitions():
    spec=importlib.util.spec_from_file_location('dancefloor_definitions', ROOT/'collections/dancefloor/definitions.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def build(check=False):
    module=definitions(); rhythms=module.all_rhythms()
    source_path=ROOT/'collections/dancefloor/sources.json'
    old_data=json.loads((ROOT/'collections/club/rhythms.json').read_text(encoding='utf-8'))
    sources=dict(old_data['sources']); sources.update(json.loads(source_path.read_text(encoding='utf-8'))['sources'])
    defs_sha=sha256((ROOT/'collections/dancefloor/definitions.py').read_bytes()).hexdigest()
    legacy_sha=sha256((ROOT/'collections/club/definitions.py').read_bytes()).hexdigest()
    base_sha=sha256((ROOT/'collections/club/rhythms.json').read_bytes()).hexdigest()
    old_ids={r['id'] for r in old_data['rhythms']}; patterns=[]; recipe_rows=[]
    for r in rhythms:
        if any(key not in sources for key in r['reference_ids']):raise ValueError('Missing source for '+r['id'])
        tables,fallback=module.motion_tables(r)
        mappings=module.MAPPINGS[4:] if r['id'] in old_ids else module.MAPPINGS
        for m in mappings:
            rows=tables[m]; n=len(rows)
            max_step=max(math.dist(rows[i-1],rows[i]) for i in range(n))
            if max_step>.35:raise ValueError('Excessive step: '+r['id']+'/'+m+': '+str(max_step))
            recipe=dict(rhythm=r, mapping=m, mapping_version=module.MAPPING_VERSION,
                        definitions_sha256=defs_sha, legacy_definitions_sha256=legacy_sha)
            name='beat_'+r['id']+'_'+m
            title,meaning,anchor=module.MAPPING_INFO[m]
            provenance=dict(collection_id=module.COLLECTION_ID, title=r['title']+' / '+title,
                family=r['genre'],author='Kieran Simkin / DanceRudiments',license='MIT',
                source_kind=r['interpretation'],source_format='dancerudiments.dancefloor-recipes',
                source_url='https://github.com/kieransimkin/DanceRudiments',
                reference_urls=[sources[k]['url'] for k in r['reference_ids']],
                rhythm_id=r['id'],mapping=m,bpm=r['bpm'],beat_unit='quarter_note',
                event_anchor=anchor,missing_lane_fallbacks=fallback if m not in module.MAPPINGS[:4] else [],
                interpretation_notes=r['notes'],mapping_notes=meaning,
                transformation='Original abstract position mapping; no recording, MIDI download, factory preset, choreography or third-party code imported.',
                parameters=dict(position_resolution=64,mapping_version=module.MAPPING_VERSION))
            diagnostic=dict(max_step=max_step, seam_position_error=0.0,
                seam_last_to_first_distance=math.dist(rows[-1],rows[0]),
                loop_validation='Periodic kernels and full-cycle phase; last sample precedes the endpoint. No forced last=first rewrite.',
                warnings=['Some rational onsets fall between native pips.'] if any((module.F(e['beat'])*64).denominator!=1 for e in r['events']) else [])
            patterns.append(CompiledPattern(name,r['title']+' — '+title+'. '+meaning,n,rows,
                            sha256(canonical(recipe).encode()).hexdigest(),canonical(provenance),canonical(diagnostic)))
            recipe_rows.append(dict(name=name,rhythm_id=r['id'],mapping=m,source_sha256=patterns[-1].source_sha256))
    pack=CompiledPack(tuple(patterns))
    if len(rhythms)!=68 or len(pack.patterns)!=944:raise ValueError('Unexpected coverage')
    seen={}; duplicates=[]
    for p in pack.patterns:
        key=sha256(canonical(p.samples).encode()).hexdigest()
        if key in seen:duplicates.append([seen[key],p.name])
        seen[key]=p.name
    if duplicates:raise ValueError('Exact duplicates: '+canonical(duplicates))
    for source in ('initial','expansion','atlas','continuum','club'):
        for p in load_pack(ROOT/f'python/dancerudiments_authoring/packs/{source}.json').patterns:
            if sha256(canonical(p.samples).encode()).hexdigest() in seen:
                raise ValueError('Exact copy of previous default: '+p.name)
    pack_sha=sha256(canonical(pack.to_dict()).encode()).hexdigest()
    manifest=dict(collection_id=module.COLLECTION_ID,pattern_count=len(patterns),new_rhythm_count=32,
        retained_rhythm_count=36,rhythm_count=68,mappings_per_rhythm=16,
        existing_club_patterns_preserved=144,added_mappings_for_existing=432,added_patterns_for_new=512,
        total_default_count=1731,definitions_sha256=defs_sha,club_rhythms_sha256=base_sha,
        sources_sha256=sha256(source_path.read_bytes()).hexdigest(),pack_sha256=pack_sha,
        sample_count=sum(p.period_pips for p in patterns),table_payload_bytes=sum(p.period_pips for p in patterns)*24,
        max_step=max(p.diagnostics['max_step'] for p in patterns),license='MIT',
        distinctness_check='Exact sample arrays only. Related rhythms and mappings are intentional, not perceptual uniqueness.',
        families=dict(sorted(Counter(r['genre'] for r in rhythms).items())),names=[p.name for p in patterns])
    rhythm_data=dict(format='dancerudiments.rhythm-studies',schema_version=1,collection_id=module.COLLECTION_ID,
        beat_unit='quarter_note',mappings=list(module.MAPPINGS),
        mapping_info={k:dict(title=v[0],description=v[1],anchor=v[2]) for k,v in module.MAPPING_INFO.items()},
        legacy_rhythm_ids=sorted(old_ids),rhythms=rhythms,sources=sources)
    recipes=dict(format='dancerudiments.dancefloor-recipes',schema_version=1,
        definitions_sha256=defs_sha,club_rhythms_sha256=base_sha,mapping_version=module.MAPPING_VERSION,
        note='Rebuild with tools/build_dancefloor_collection.py; a recipe index, not a dancerudiments.score-pack.',patterns=recipe_rows)
    pack_text=canonical({k:v for k,v in pack.to_dict().items() if k!='patterns'})[:-1]+',"patterns":[\n'+',\n'.join(canonical(p.to_dict()) for p in patterns)+'\n]}\n'
    guide=['# Dancefloor 06: rhythm and movement reference','',
        '**32 new studies; 68 rhythms each with 16 motion interpretations. 944 additions, 1,731 defaults.**','',
        'The original Club 05 scores and 144 motions are retained exactly. This collection adds twelve',
        'mappings for each old rhythm and all sixteen mappings for each new rhythm. Use the ordinary',
        '`sample(name, pip_count)` API; no separate pack load. See `docs/dancefloor.md` for use and scope.','',
        '## Movement mappings','', '| Suffix | Mapping | What changes | Timing anchor |','| --- | --- | --- | --- |']
    guide += [f'| `_{k}` | {v[0]} | {v[1]} | {v[2]} |' for k,v in module.MAPPING_INFO.items()]
    guide += ['', '## New rhythm studies','', '| Base identifier | Study | Family | BPM |', '| --- | --- | --- | ---: |']
    guide += [f'| `beat_{r["id"]}` | {r["title"]} | {r["genre"]} | {r["bpm"]} |' for r in rhythms if r['id'] not in old_ids]
    guide += ['', '## Interpretation notes','']
    guide += [f'**{r["title"]}:** {r["notes"]}' for r in rhythms if r['id'] not in old_ids]
    guide += ['', '## Extended existing rhythms','', ', '.join('`'+r['id']+'`' for r in rhythms if r['id'] in old_ids),
        '', '## Sources','', 'Checked 29 September 2026. References support the stated features, not every',
        'authored event. No third-party recordings, MIDI, charts, presets or code are bundled.','']
    guide += [f'- {s["publisher"]}: {s["title"]} — {s["url"]}\n  Scope: {s["supports"]}' for s in sources.values()]
    guide.append('')
    outputs={
        'collections/dancefloor/recipes.json':json.dumps(recipes,indent=2)+'\n',
        'collections/dancefloor/rhythms.json':json.dumps(rhythm_data,sort_keys=True,indent=2)+'\n',
        'python/dancerudiments_authoring/packs/dancefloor.json':pack_text,
        'include/dancerudiments/collections/dancefloor.hpp':emit_cpp(pack,'dancerudiments_dancefloor'),
        'collections/dancefloor/manifest.json':json.dumps(manifest,sort_keys=True,indent=2)+'\n',
        'collections/dancefloor/README.md':'\n'.join(guide)}
    for name,text in outputs.items():
        path=ROOT/name
        if check:
            if not path.is_file() or path.read_text(encoding='utf-8')!=text:raise ValueError('Stale generated output: '+name)
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('w',encoding='utf-8',newline='\n') as stream:stream.write(text)
    print(('Checked' if check else 'Built')+f' {len(patterns)} additions, {len(rhythms)} rhythms ×16; {manifest["sample_count"]} samples; max step {manifest["max_step"]:.6f}')
    return pack


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:build(args.check)
    except (ValueError,OSError,TypeError,KeyError) as exc:parser.exit(1,str(exc)+'\n')
