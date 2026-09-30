#!/usr/bin/env python3
"""Build/inspect native-backed NuGet packages. No registry access except explicit verify-published.
Music: https://kieransimkin.co.uk/my-songs/
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'bindings/csharp/DanceRudiments/DanceRudiments.csproj'
MUSIC_URL = 'https://kieransimkin.co.uk/my-songs/'
REPOSITORY = 'https://github.com/kieransimkin/DanceRudiments'
PLATFORMS = json.loads((ROOT / 'bindings/csharp/platforms.json').read_text(encoding='utf-8'))['include']
BY_RID = {p['rid']: p for p in PLATFORMS}


def version() -> str:
    value = ET.parse(PROJECT).findtext('./PropertyGroup/Version') or ''
    if not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('C# project must declare a release version MAJOR.MINOR.PATCH')
    return value


def check_source() -> None:
    project = ET.parse(PROJECT)
    if project.findtext('./PropertyGroup/PackageId') != 'DanceRudiments':
        raise ValueError('Unexpected NuGet package ID')
    for tag in ('Description', 'PackageProjectUrl'):
        if MUSIC_URL not in (project.findtext('./PropertyGroup/' + tag) or ''):
            raise ValueError(f'C# {tag} is missing the author music URL')
    for name in ('bindings/csharp/README.md', 'docs/csharp.md', 'examples/bindings/csharp/Program.cs'):
        if MUSIC_URL not in (ROOT / name).read_text(encoding='utf-8'):
            raise ValueError('Missing author link: ' + name)
    subprocess.run([sys.executable, str(ROOT/'tools/check_release_version.py'), 'v'+version()], check=True)
    print('C# source, author links and cross-language versions verified')


def check_binary(data: bytes, rid: str) -> None:
    """Reject incorrectly labelled x64/ARM64 or non-library artifacts before packaging."""
    expected = BY_RID[rid]
    arch = expected['architecture']
    if rid.startswith('linux-'):
        if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01':
            raise ValueError(f'{rid}: not a little-endian ELF64 library')
        kind, machine = struct.unpack_from('<HH', data, 16)
        if kind != 3 or machine != {'x64':62, 'arm64':183}[arch]:
            raise ValueError(f'{rid}: wrong ELF type or machine')
    elif rid.startswith('win-'):
        if len(data) < 64 or data[:2] != b'MZ':
            raise ValueError(f'{rid}: not a PE library')
        offset = struct.unpack_from('<I', data, 60)[0]
        if offset+26 > len(data) or data[offset:offset+4] != b'PE\0\0':
            raise ValueError(f'{rid}: invalid PE header')
        machine = struct.unpack_from('<H', data, offset+4)[0]
        flags = struct.unpack_from('<H', data, offset+22)[0]
        if machine != {'x64':0x8664, 'arm64':0xaa64}[arch] or not flags & 0x2000:
            raise ValueError(f'{rid}: wrong PE machine or missing DLL flag')
    else:
        if len(data) < 32 or data[:4] != b'\xcf\xfa\xed\xfe':
            raise ValueError(f'{rid}: not a thin little-endian Mach-O 64 library')
        cpu = struct.unpack_from('<I', data, 4)[0]
        kind = struct.unpack_from('<I', data, 12)[0]
        if cpu != {'x64':0x01000007, 'arm64':0x0100000c}[arch] or kind != 6:
            raise ValueError(f'{rid}: wrong Mach-O CPU or file type')


def consumer_config(source: Path, output: Path) -> None:
    """Permit framework-pack downloads without ever using a public binding as a test substitute."""
    if not source.is_dir(): raise ValueError('Local NuGet artifact directory is missing')
    root=ET.Element('configuration')
    sources=ET.SubElement(root,'packageSources');ET.SubElement(sources,'clear')
    ET.SubElement(sources,'add',key='local-binding',value=str(source.resolve()))
    ET.SubElement(sources,'add',key='nuget.org',value='https://api.nuget.org/v3/index.json')
    mapping=ET.SubElement(root,'packageSourceMapping');ET.SubElement(mapping,'clear')
    local=ET.SubElement(mapping,'packageSource',key='local-binding')
    ET.SubElement(local,'package',pattern='DanceRudiments')
    public=ET.SubElement(mapping,'packageSource',key='nuget.org')
    ET.SubElement(public,'package',pattern='Microsoft.*')
    output.parent.mkdir(parents=True,exist_ok=True)
    ET.ElementTree(root).write(output,encoding='utf-8',xml_declaration=True)


def package_payload(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate package members')
        return {n:sha256(z.read(n)).digest() for n in names if n!='.signature.p7s'}


def compare_packages(expected: Path, actual: Path) -> None:
    if package_payload(expected)!=package_payload(actual):
        raise ValueError('Restored package differs from the tested package')
    print('Restored package matches every non-signature package member')


def stage(build: Path, rid: str, destination: Path, commit: str) -> None:
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Native provenance requires a full Git commit')
    p = BY_RID[rid]
    source = build/'csharp-native'/p['file']
    data = source.read_bytes(); check_binary(data,rid)
    output = destination/'runtimes'/rid/'native'/p['file']
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(data)
    manifest = dict(package='DanceRudiments',version=version(),source_commit=commit,
                    abi_version=1,rid=rid,file=p['file'],sha256=sha256(data).hexdigest(),
                    size=len(data),baseline=p['baseline'],music_url=MUSIC_URL)
    folder = destination/'manifests';folder.mkdir(parents=True,exist_ok=True)
    (folder/(rid+'.json')).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(f'Staged {rid}: {len(data)} bytes')


def verify_tree(folder: Path, commit: str) -> None:
    expected_files = set()
    for p in PLATFORMS:
        relative = Path('runtimes')/p['rid']/'native'/p['file']
        expected_files.add(relative.as_posix())
        data=(folder/relative).read_bytes();check_binary(data,p['rid'])
        manifest=json.loads((folder/'manifests'/(p['rid']+'.json')).read_text(encoding='utf-8'))
        expected=dict(package='DanceRudiments',version=version(),source_commit=commit,abi_version=1,
                      rid=p['rid'],file=p['file'],sha256=sha256(data).hexdigest(),size=len(data),
                      baseline=p['baseline'],music_url=MUSIC_URL)
        if manifest != expected: raise ValueError('Stale or mixed native artifact: '+p['rid'])
    actual={p.relative_to(folder).as_posix() for p in (folder/'runtimes').rglob('*') if p.is_file()}
    if actual!=expected_files:raise ValueError('Unexpected/missing native runtime file')


def native_reference(exporter: Path, output: Path) -> None:
    # This executable links the original static C++ core, NOT the C ABI bridge.
    result=subprocess.run([str(exporter.resolve())],check=True,stdout=subprocess.PIPE)
    doc=json.loads(result.stdout)
    rows=[]
    for row in doc['patterns']:
        h=sha256()
        for xyz in row['samples']:h.update(struct.pack('<ddd',*(float(v)+0.0 for v in xyz)))
        rows.append({**{k:v for k,v in row.items() if k!='samples'},'samples_f64le_sha256':h.hexdigest()})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(pips_per_beat=64,patterns=rows),ensure_ascii=True)+'\n',encoding='utf-8')
    print(f'Independent reference: {len(rows)} patterns')


def check_archive(path: Path, commit: str | None = None) -> None:
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP members')
        if any(n.startswith('/') or '\\' in n or ':' in n.split('/')[0] or '..' in n.split('/') for n in names):raise ValueError('Unsafe ZIP member')
        required=['README.md','AUTHORS.md','docs/csharp.md','licenses/LICENSE',
                  'licenses/THIRD_PARTY_NOTICES.md','licenses/d3-ease/LICENSE',
                  'lib/net8.0/DanceRudiments.dll','lib/net8.0/DanceRudiments.xml',
                  'examples/bindings/csharp/Program.cs', 'build-info/platforms.json']
        required += ['docs/images/'+x for x in ('visualizer-amen-desktop.png','visualizer-midi-score.png','visualizer-mobile.png')]
        for name in required:
            if name not in names or not z.read(name):raise ValueError('Missing/empty NuGet asset: '+name)
        for name in ('README.md','AUTHORS.md','docs/csharp.md'):
            if MUSIC_URL not in z.read(name).decode('utf-8'):raise ValueError('Author URL missing from '+name)
        nuspecs=[n for n in names if n.endswith('.nuspec')]
        if len(nuspecs)!=1:raise ValueError('Expected exactly one nuspec')
        document=ET.fromstring(z.read(nuspecs[0]));metadata=document.find('{*}metadata')
        if metadata is None:raise ValueError('No NuGet metadata')
        def text(tag):return metadata.findtext('{*}'+tag) or ''
        if text('id')!='DanceRudiments' or text('version')!=version():raise ValueError('NuGet identity mismatch')
        if text('readme')!='README.md' or text('authors')!='Kieran Simkin':raise ValueError('NuGet README/author mismatch')
        if text('projectUrl')!=MUSIC_URL or MUSIC_URL not in text('description'):raise ValueError('NuGet music URL missing')
        repository=metadata.find('{*}repository')
        if repository is None or repository.get('url')!=REPOSITORY:raise ValueError('Missing repository association')
        if not re.fullmatch('[0-9a-f]{40}', repository.get('commit') or ''):raise ValueError('Missing full package source commit')
        if commit and repository.get('commit')!=commit:raise ValueError('Package commit mismatch')
        seen_commits=set()
        for p in PLATFORMS:
            member=f'runtimes/{p["rid"]}/native/{p["file"]}'
            data=z.read(member);check_binary(data,p['rid'])
            m=json.loads(z.read('build-info/'+p['rid']+'.json'))
            if m.get('sha256')!=sha256(data).hexdigest() or m.get('size')!=len(data):raise ValueError('Native payload hash mismatch: '+member)
            if m.get('package')!='DanceRudiments' or m.get('baseline')!=p['baseline'] or m.get('rid')!=p['rid'] or m.get('file')!=p['file'] or m.get('abi_version')!=1 or m.get('version')!=version() or m.get('music_url')!=MUSIC_URL:
                raise ValueError('Native payload metadata mismatch: '+member)
            seen_commits.add(m.get('source_commit'))
        if seen_commits!={repository.get('commit')} or (commit and seen_commits!={commit}):
            raise ValueError('Mixed native source revisions')
        if json.loads(z.read('build-info/platforms.json')) != json.loads((ROOT/'bindings/csharp/platforms.json').read_text(encoding='utf-8')):
            raise ValueError('Platform manifest differs from source')
        expected_runtime={f'runtimes/{p["rid"]}/native/{p["file"]}' for p in PLATFORMS}
        if {n for n in names if n.startswith('runtimes/') and not n.endswith('/')}!=expected_runtime:
            raise ValueError('Unexpected runtime files')
        if any(n.endswith(('.patch','.pyd','.so.debug')) or '/obj/' in n or 'recovery_codes' in n for n in names):
            raise ValueError('Unwanted development/private data in package')
    print(path.name+': six architectures, native hashes, versions, author links and documentation verified')


def pack(folder: Path, output: Path, commit: str) -> None:
    check_source();verify_tree(folder,commit)
    output.mkdir(parents=True,exist_ok=True)
    subprocess.run(['dotnet','pack',str(PROJECT),'-c','Release','-o',str(output.resolve()),
                    '-p:ContinuousIntegrationBuild=true','-p:RepositoryCommit='+commit,
                    '-p:NativeArtifactsDir='+str(folder.resolve())],check=True)
    target=output/('DanceRudiments.'+version()+'.nupkg')
    check_archive(target,commit)
    symbols=output/('DanceRudiments.'+version()+'.snupkg')
    if not symbols.is_file():raise ValueError('Managed symbol package was not produced')
    files=[target,symbols]
    (output/'SHA256SUMS-csharp.txt').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files),encoding='utf-8')


def verify_published(path: Path, feed: str, attempts: int = 12) -> None:
    """NuGet.org adds a repository signature: compare ZIP payloads, not raw ZIP bytes.
    GitHub feed verification uses an isolated dotnet restore in the workflow.
    """
    if feed!='nuget.org':raise ValueError('Only the public NuGet.org feed is supported here')
    url=f'https://api.nuget.org/v3-flatcontainer/dancerudiments/{version()}/dancerudiments.{version()}.nupkg'
    with zipfile.ZipFile(path) as local:
        expected={n:sha256(local.read(n)).digest() for n in local.namelist() if n!='.signature.p7s'}
    last=None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url,timeout=60) as response: data=response.read(256*1024*1024+1)
            if len(data)>256*1024*1024:raise ValueError('Published package exceeds verification size limit')
            with zipfile.ZipFile(BytesIO(data)) as remote:
                actual={n:sha256(remote.read(n)).digest() for n in remote.namelist() if n!='.signature.p7s'}
            if expected!=actual:raise ValueError('Published package payload differs; refusing to treat a different same-version upload as success')
            print('NuGet.org download matches every non-signature package member');return
        except (urllib.error.URLError,zipfile.BadZipFile) as error:
            last=error
            if attempt+1<attempts:time.sleep(15)
    raise RuntimeError('Upload/download verification did not complete: '+str(last))


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('version');sub.add_parser('matrix');sub.add_parser('check-source')
    s=sub.add_parser('consumer-config');s.add_argument('--source',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('compare');s.add_argument('expected',type=Path);s.add_argument('actual',type=Path)
    s=sub.add_parser('stage');s.add_argument('--build',type=Path,required=True);s.add_argument('--rid',choices=BY_RID,required=True)
    s.add_argument('--output',type=Path,required=True);s.add_argument('--commit',required=True)
    s=sub.add_parser('reference');s.add_argument('--exporter',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('pack');s.add_argument('--native',type=Path,required=True);s.add_argument('--output',type=Path,required=True);s.add_argument('--commit',required=True)
    s=sub.add_parser('check');s.add_argument('package',type=Path);s.add_argument('--commit')
    s=sub.add_parser('verify-published');s.add_argument('package',type=Path);s.add_argument('--feed',default='nuget.org')
    a=p.parse_args()
    try:
        if a.command=='version':print(version())
        elif a.command=='matrix':print(json.dumps({'include':PLATFORMS},separators=(',',':')))
        elif a.command=='check-source':check_source()
        elif a.command=='consumer-config':consumer_config(a.source,a.output)
        elif a.command=='compare':compare_packages(a.expected,a.actual)
        elif a.command=='stage':stage(a.build,a.rid,a.output,a.commit)
        elif a.command=='reference':native_reference(a.exporter,a.output)
        elif a.command=='pack':pack(a.native,a.output,a.commit)
        elif a.command=='check':check_archive(a.package,a.commit)
        elif a.command=='verify-published':verify_published(a.package,a.feed)
    except (OSError,ValueError,KeyError,ET.ParseError,subprocess.CalledProcessError,RuntimeError,zipfile.BadZipFile) as error:
        p.exit(1,str(error)+'\n')
if __name__=='__main__':main()
