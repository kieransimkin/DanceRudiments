#!/usr/bin/env python3
"""Build a self-contained demo from the installed C++ catalogue of this checkout.

First: python -m pip install .
Then:  python tools/release_demo.py --version X.Y.Z --commit COMMIT --output-dir dist/demo
Python assembles assets; every live movement position comes from C++/WebAssembly.
"""
from __future__ import annotations
import argparse
import base64
from hashlib import sha256
import html
import importlib.metadata
import json
import math
from pathlib import Path
import re
import subprocess
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'tools/release_demo_assets'
SAMPLER = r'''
#include "data.inc"
extern "C" {
int pattern_count() { return kCount; }
int pattern_period(int i) { return i>=0 && i<kCount ? kPatterns[i].count : 0; }
double sample_component(int i,int pip,int axis) {
  if(i<0 || i>=kCount || axis<0 || axis>2) return __builtin_nan("");
  const auto& p=kPatterns[i];int n=pip%p.count;if(n<0)n+=p.count;
  return p.values[n][axis];
}
}
'''

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)

def native_snapshot():
    import dancerudiments as d
    provenance={}
    for path in sorted((ROOT/'python/dancerudiments_authoring/packs').glob('*.json')):
        pack=json.loads(path.read_text(encoding='utf-8'))
        for item in pack.get('patterns',[]):
            if isinstance(item,dict) and 'name' in item: provenance[item['name']]=item
    catalogue = d.catalogue()
    lock_path = ROOT/'collections/defaults.json'
    if lock_path.is_file():
        lock = json.loads(lock_path.read_text(encoding='utf-8'))
        required = {name for source in lock['collections'] for name in source['patterns']}
        missing = required - {item['name'] for item in catalogue}
        if missing:
            raise ValueError('Native library is stale; missing defaults: '+', '.join(sorted(missing)))
    rows=[]
    for info in catalogue:
        name=info['name'];period=info['period_pips']
        values=[list(d.sample(name,pip).as_tuple()) for pip in range(period)]
        source=provenance.get(name,{})
        if source and (source.get('samples')!=values or source.get('period_pips')!=period):
            raise ValueError('Native/source table mismatch: '+name)
        metadata=dict(source.get('provenance',{}))
        metadata.setdefault('title',name.replace('_',' ').capitalize())
        metadata.setdefault('family','Core')
        metadata.setdefault('author','Kieran Simkin / DanceRudiments')
        metadata.setdefault('license','See embedded release notices')
        metadata.setdefault('source_kind','native-catalogue-export')
        row=dict(name=name,description=info['description'],period_pips=period,samples=values,
                 source_sha256=source.get('source_sha256') or sha256(canonical([info,values]).encode()).hexdigest(),
                 provenance=metadata,diagnostics=source.get('diagnostics',{}))
        rows.append(row)
    return rows

def validate(patterns):
    if not isinstance(patterns,list) or not 1<=len(patterns)<=4096: raise ValueError('Invalid pattern count')
    names=set();total=0
    for p in patterns:
        name=p.get('name')
        if not isinstance(name,str) or not re.fullmatch('[a-z][a-z0-9_]{0,127}',name) or name in names:
            raise ValueError('Invalid/duplicate pattern name')
        names.add(name);n=p['period_pips']
        if type(n) is not int or not 1<=n<=65535 or len(p['samples'])!=n:raise ValueError('Invalid period')
        total+=n
        if total>4194304:raise ValueError('Demo exceeds sample limit')
        for row in p['samples']:
            if len(row)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>1 for x in row):
                raise ValueError('Invalid position')
    return total

def build_page(patterns, version, commit, output_dir, compiler='clang++', *, native=True, notices=''):
    """The CLI always exports native defaults. Explicit fixture calls are labelled previews."""
    total=validate(patterns)
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+.][A-Za-z0-9.-]+)?',version):raise ValueError('Unsafe version')
    if not re.fullmatch('[A-Za-z0-9+._-]{1,100}',commit):raise ValueError('Unsafe commit identifier')
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        folder=Path(temp);lines=['struct Pattern { const double (*values)[3]; int count; };',f'constexpr int kCount={len(patterns)};']
        for i,p in enumerate(patterns):
            lines.append(f'constexpr double values_{i}[{p["period_pips"]}][3]={{')
            lines.extend('{'+','.join(format(v,'.17g') for v in row)+'},' for row in p['samples']);lines.append('};')
        lines.append('constexpr Pattern kPatterns[]={')
        lines.extend('{values_'+str(i)+','+str(p['period_pips'])+'},' for i,p in enumerate(patterns));lines.append('};')
        (folder/'data.inc').write_text('\n'.join(lines),encoding='utf-8')
        (folder/'sampler.cpp').write_text(SAMPLER,encoding='utf-8')
        wasm=folder/'demo.wasm'
        subprocess.run([compiler,'--target=wasm32','-std=c++17','-O2','-nostdlib','-fno-exceptions','-fno-rtti',
                        str(folder/'sampler.cpp'),'-Wl,--no-entry','-Wl,--strip-all','-Wl,--export=pattern_count',
                        '-Wl,--export=pattern_period','-Wl,--export=sample_component','-o',str(wasm)],check=True)
        raw=wasm.read_bytes()
    kind='native-default-catalogue' if native else 'renderer-preview-fixture'
    # Runtime tables are already in WASM. Do not embed a second, much larger
    # decimal JSON copy; retain independent native-export hashes for validation.
    compact = []
    for pattern in patterns:
        row = {key: value for key, value in pattern.items() if key != 'samples'}
        # Numeric equality treats -0.0 as 0.0, as does the existing sampler audit.
        digest = sha256()
        for xyz in pattern['samples']:
            digest.update(struct.pack('<ddd', *(float(v) + 0.0 for v in xyz)))
        row['samples_f64le_sha256'] = digest.hexdigest()
        compact.append(row)
    payload=dict(collection_id='release-'+version,version=version,source_commit=commit,source_kind=kind,
                 pack=dict(format='dancerudiments.demo-snapshot',schema_version=2,pips_per_beat=64,patterns=compact),
                 score=dict(patterns=[]),notices=notices,wasm=base64.b64encode(raw).decode())
    payload['pack_sha256']=sha256(canonical(payload['pack']).encode()).hexdigest()
    note=('All movements in the default catalogue of this release. Personal review choices do not change the library.' if native else
          'Renderer preview using the previously delivered 28-pattern collection; not a claim about the current default catalogue.')
    page=(ASSETS/'template.html').read_text(encoding='utf-8')
    for key,val in [('__VERSION__',version),('__COUNT__',str(len(patterns))),('__COMMIT__',commit),('__BUILD_NOTE__',note)]:
        page=page.replace(key,html.escape(val))
    page=page.replace('/*__STYLE__*/',(ASSETS/'style.css').read_text(encoding='utf-8'))
    page=page.replace('/*__APP__*/',(ASSETS/'app.js').read_text(encoding='utf-8'))
    page=page.replace('__PAYLOAD__',canonical(payload).replace('<','\\u003c'))
    path=output_dir/('DanceRudiments-demo-v'+version+'.html');path.write_text(page,encoding='utf-8')
    manifest=dict(version=version,source_commit=commit,source_kind=kind,pattern_count=len(patterns),sample_count=total,
                  names=[p['name'] for p in patterns],sample_encoding='WASM tables; SHA-256 of signed-zero-normalized f64le XYZ',
                  sample_hashes=[p['samples_f64le_sha256'] for p in compact],pack_sha256=payload['pack_sha256'],wasm_sha256=sha256(raw).hexdigest(),
                  html_sha256=sha256(path.read_bytes()).hexdigest())
    path.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(str(path));return path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',required=True);parser.add_argument('--commit',required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'dist/demo');parser.add_argument('--compiler',default='clang++')
    args=parser.parse_args()
    try:
        if importlib.metadata.version('dancerudiments')!=args.version:raise ValueError('Installed package version does not match release')
        files=[ROOT/'LICENSE']+sorted((ROOT/'collections').glob('**/THIRD_PARTY_NOTICES.md'))+sorted((ROOT/'collections').glob('**/sources/*/LICENSE'))
        notices='\n\n'.join('# '+str(p.relative_to(ROOT))+'\n\n'+p.read_text(encoding='utf-8') for p in files if p.is_file())
        build_page(native_snapshot(),args.version,args.commit,args.output_dir,args.compiler,notices=notices)
    except (ValueError,OSError,ImportError,subprocess.CalledProcessError) as exc:parser.exit(1,str(exc)+'\n')
if __name__=='__main__':main()
