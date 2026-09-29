#!/usr/bin/env python3
"""Rebuild/check the optional audition collection; no network access required."""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python'))
from dancerudiments_authoring import emit_cpp, emit_json
from dancerudiments_authoring._reproducibility import checked_score


def compact(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def build(rebuild_wasm=False, check=False, compiler='clang++'):
    spec=importlib.util.spec_from_file_location('initial_definitions',ROOT/'collections/initial/definitions.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    score=module.document()
    score,pack=checked_score(score,ROOT,"initial",check)
    if any(p.diagnostics['warnings'] for p in pack.patterns):
        raise ValueError('Initial candidates must compile without warnings')
    data=pack.to_dict()
    digest=sha256(compact(data).encode()).hexdigest()
    cpp=emit_cpp(pack,namespace='dancerudiments_initial')
    lines=['// Generated source data. Source notices: initial.hpp / THIRD_PARTY_NOTICES.md.',
           'struct PreviewPattern { const double (*samples)[3]; int count; };',
           f'constexpr int kPatternCount = {len(pack.patterns)};']
    for i,p in enumerate(pack.patterns):
        lines.append(f'constexpr double data_{i}[{p.period_pips}][3] = {{')
        lines.extend('  {'+', '.join(format(v,'.17g') for v in row)+'},' for row in p.samples)
        lines.append('};')
    lines.append('constexpr PreviewPattern kPatterns[] = {')
    lines.extend(f'  {{data_{i}, {p.period_pips}}},' for i,p in enumerate(pack.patterns))
    lines.extend(['};',''])
    inc='\n'.join(lines)
    sampler=(ROOT/'collections/initial/preview_sampler.cpp').read_bytes()
    wasm_path=ROOT/'collections/initial/preview_wasm.json'
    expected=dict(data_sha256=sha256(inc.encode()).hexdigest(),
                  sampler_sha256=sha256(sampler).hexdigest())
    if rebuild_wasm:
        if check:
            raise ValueError('--check and --rebuild-wasm are mutually exclusive')
        if not shutil.which(compiler):
            raise ValueError('WASM compiler not found: '+compiler)
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            with (folder/'preview_data.inc').open('w', encoding='utf-8', newline='\n') as stream:
                stream.write(inc)
            (folder/'preview_sampler.cpp').write_bytes(sampler)
            output=folder/'preview.wasm'
            command=[compiler,'--target=wasm32','-std=c++17','-O2','-nostdlib',
                     '-fno-exceptions','-fno-rtti',str(folder/'preview_sampler.cpp'),
                     '-Wl,--no-entry','-Wl,--export=pattern_count',
                     '-Wl,--export=pattern_period','-Wl,--export=sample_component',
                     '-Wl,--strip-all','-o',str(output)]
            subprocess.run(command,check=True)
            raw=output.read_bytes()
            wasm=dict(**expected,wasm_sha256=sha256(raw).hexdigest(),
                      compiler=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],
                      format='dancerudiments.audition-wasm',schema_version=1,
                      data=base64.b64encode(raw).decode('ascii'))
    else:
        if not wasm_path.exists():
            raise ValueError('No bundled WASM. Run with --rebuild-wasm using LLVM clang++ with wasm-ld.')
        wasm=json.loads(wasm_path.read_text(encoding='utf-8'))
        if any(wasm.get(k)!=v for k,v in expected.items()):
            raise ValueError('WASM does not match generated data or C++ source; use --rebuild-wasm')
        raw=base64.b64decode(wasm['data'],validate=True)
        if sha256(raw).hexdigest()!=wasm['wasm_sha256'] or raw[:4]!=b'\0asm':
            raise ValueError('Bundled WASM failed integrity validation')
    notices=(ROOT/'collections/initial/THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
    payload=dict(collection_id=module.COLLECTION_ID,pack_sha256=digest,
                 pack=data,score=score,notices=notices,wasm=wasm['data'])
    # JSON is inert text. Escape '<' to prevent a source note closing the script element.
    html=(ROOT/'harness/initial/template.html').read_text(encoding='utf-8')
    html=html.replace('/*__STYLE__*/',(ROOT/'harness/initial/style.css').read_text(encoding='utf-8'))
    html=html.replace('/*__APP__*/',(ROOT/'harness/initial/app.js').read_text(encoding='utf-8'))
    html=html.replace('__PAYLOAD__',compact(payload).replace('<','\\u003c'))
    manifest=dict(collection_id=module.COLLECTION_ID,pack_sha256=digest,
          pattern_count=len(pack.patterns),sample_count=sum(p.period_pips for p in pack.patterns),
          pips_per_quarter_note=64,wasm_sha256=wasm['wasm_sha256'],
          candidates=[dict(name=p.name,source_sha256=p.source_sha256,period_pips=p.period_pips,
                           title=p.provenance['title'],family=p.provenance['family'],
                           license=p.provenance['license']) for p in pack.patterns])
    outputs={
        ROOT/'collections/initial/initial.score.json':json.dumps(score,indent=2,ensure_ascii=True)+'\n',
        ROOT/'python/dancerudiments_authoring/packs/initial.json':emit_json(pack),
        ROOT/'python/dancerudiments_authoring/packs/THIRD_PARTY_NOTICES.md':notices,
        ROOT/'include/dancerudiments/collections/initial.hpp':cpp,
        ROOT/'collections/initial/preview_data.inc':inc,
        wasm_path:json.dumps(wasm,indent=2,sort_keys=True)+'\n',
        ROOT/'collections/initial/manifest.json':json.dumps(manifest,indent=2,sort_keys=True)+'\n',
        ROOT/'harness/initial-collection.html':html,
    }
    stale=[]
    for path,text in outputs.items():
        if check:
            # Source text may have CRLF in Windows worktrees; normalise only line endings.
            if not path.exists() or path.read_text(encoding='utf-8') != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('w',encoding='utf-8',newline='\n') as stream:
                stream.write(text)
    if stale:
        raise ValueError('Generated files differ: '+', '.join(stale))
    print(('Checked' if check else 'Built')+f' {len(pack.patterns)} candidates / {manifest["sample_count"]} samples; '+digest)
    return pack


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--rebuild-wasm',action='store_true')
    parser.add_argument('--compiler',default='clang++')
    args=parser.parse_args()
    try:
        build(args.rebuild_wasm,args.check,args.compiler)
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        parser.exit(1,str(exc)+'\n')


if __name__=='__main__':
    main()
