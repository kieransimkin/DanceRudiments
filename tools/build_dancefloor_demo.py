#!/usr/bin/env python3
"""Build the offline Dancefloor 06 audition page from this checkout's native defaults."""
from __future__ import annotations
import argparse
import base64
from hashlib import sha256
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from dancerudiments_authoring.collections import club_pack, dancefloor_pack
from release_demo import SAMPLER, canonical

def build(output,compiler='clang++',commit=None,version=None):
    import dancerudiments as native
    if version is None:
        version=re.search(r'^version = "([^"]+)"', (ROOT/'pyproject.toml').read_text(), re.M).group(1)
    compiled_patterns=club_pack().patterns + dancefloor_pack().patterns;patterns=[];checks=0
    for p in compiled_patterns:
        values=[list(native.sample(p.name,i).as_tuple()) for i in range(p.period_pips)]
        if values!=[list(v) for v in p.samples]:raise ValueError('Native/default data mismatch: '+p.name)
        checks+=len(values)*3
        patterns.append(dict(name=p.name,period_pips=p.period_pips,samples=values))
    rhythm_data=json.loads((ROOT/'collections/dancefloor/rhythms.json').read_text(encoding='utf-8'))
    if commit is None:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp);lines=['struct Pattern { const double (*values)[3]; int count; };',f'constexpr int kCount={len(patterns)};']
        for i,p in enumerate(patterns):
            lines.append(f'constexpr double values_{i}[{p["period_pips"]}][3]={{')
            lines.extend('{'+','.join(format(v,'.17g') for v in row)+'},' for row in p['samples']);lines.append('};')
        lines.append('constexpr Pattern kPatterns[]={')
        lines.extend('{values_'+str(i)+','+str(p['period_pips'])+'},' for i,p in enumerate(patterns));lines.append('};')
        (folder/'data.inc').write_text('\n'.join(lines),encoding='utf-8');(folder/'sampler.cpp').write_text(SAMPLER,encoding='utf-8')
        wasm=folder/'club.wasm'
        subprocess.run([compiler,'--target=wasm32','-std=c++17','-O2','-nostdlib','-fno-exceptions','-fno-rtti',
          str(folder/'sampler.cpp'),'-Wl,--no-entry','-Wl,--strip-all','-Wl,--export=pattern_count',
          '-Wl,--export=pattern_period','-Wl,--export=sample_component','-o',str(wasm)],check=True)
        raw=wasm.read_bytes()
    payload=dict(rhythm_data,patterns=patterns,wasm=base64.b64encode(raw).decode(),source_commit=commit,version=version)
    assets=ROOT/'tools/dancefloor_demo_assets';page=(assets/'template.html').read_text(encoding='utf-8')
    page=page.replace('/*__STYLE__*/',(assets/'style.css').read_text(encoding='utf-8'))
    page=page.replace('/*__APP__*/',(assets/'app.js').read_text(encoding='utf-8'))
    page=page.replace('__PAYLOAD__',canonical(payload).replace('<','\\u003c'))
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(page,encoding='utf-8')
    report=dict(version=version,source_commit=commit,rhythm_count=len(payload['rhythms']),pattern_count=len(patterns),
                native_component_matches=checks,wasm_sha256=sha256(raw).hexdigest(),html_sha256=sha256(output.read_bytes()).hexdigest())
    output.with_suffix('.manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'{output}: {len(patterns)} native movements, {checks} exact native/source scalar checks')
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist/dancefloor-demo.html');parser.add_argument('--compiler',default='clang++');parser.add_argument('--commit');parser.add_argument('--version')
    args=parser.parse_args()
    try:build(args.output,args.compiler,args.commit,args.version)
    except (ImportError,ValueError,OSError,subprocess.CalledProcessError) as e:parser.exit(1,str(e)+'\n')
