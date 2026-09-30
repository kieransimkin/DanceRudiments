"""Package-structure tests use deliberately synthetic headers, never distributable binaries.
Actual native execution is covered by CTest and the managed contract suite.
Music: https://kieransimkin.co.uk/my-songs/
"""
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('csharp_package',ROOT/'tools/csharp_package.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
COMMIT='918c43d725b3ed91b663930430079c37cd6d3a25'


def synthetic_header(rid):
    """Minimum fixture recognized by the inspector, NOT an executable library."""
    b=bytearray(256);arm=rid.endswith('arm64')
    if rid.startswith('linux'):
        b[:6]=b'\x7fELF\x02\x01';struct.pack_into('<HH',b,16,3,183 if arm else 62)
    elif rid.startswith('win'):
        b[:2]=b'MZ';struct.pack_into('<I',b,60,64);b[64:68]=b'PE\0\0'
        struct.pack_into('<H',b,68,0xaa64 if arm else 0x8664);struct.pack_into('<H',b,86,0x2000)
    else:
        b[:4]=b'\xcf\xfa\xed\xfe';struct.pack_into('<I',b,4,0x0100000c if arm else 0x01000007)
        struct.pack_into('<I',b,12,6)
    return bytes(b)


def write_zip(path,members):
    with zipfile.ZipFile(path,'w') as z:
        for key,value in members.items():z.writestr(key,value)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
    def native_tree(self):
        for p in package.PLATFORMS:
            build=self.folder/('build-'+p['rid'])/'csharp-native';build.mkdir(parents=True)
            (build/p['file']).write_bytes(synthetic_header(p['rid']))
            package.stage(build.parent,p['rid'],self.folder/'staged',COMMIT)
        return self.folder/'staged'
    def members(self):
        folder=self.native_tree()
        members={p.relative_to(folder).as_posix().replace('manifests/','build-info/'):p.read_bytes()
                 for p in folder.rglob('*') if p.is_file()}
        for name in ('README.md','AUTHORS.md','docs/csharp.md'):
            members[name]=package.MUSIC_URL.encode()
        for name in ('licenses/LICENSE','licenses/THIRD_PARTY_NOTICES.md','licenses/D3-ease-LICENSE',
                     'lib/net8.0/DanceRudiments.dll','lib/net8.0/DanceRudiments.xml',
                     'examples/bindings/csharp/Program.cs',
                     'docs/images/visualizer-amen-desktop.png','docs/images/visualizer-midi-score.png',
                     'docs/images/visualizer-mobile.png'):
            members[name]=b'unit-test fixture only'
        members['build-info/platforms.json']=(ROOT/'bindings/csharp/platforms.json').read_bytes()
        root=ET.Element('package',xmlns='http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd')
        meta=ET.SubElement(root,'metadata')
        for k,v in dict(id='DanceRudiments',version=package.version(),authors='Kieran Simkin',
                        readme='README.md',description='Music: '+package.MUSIC_URL,projectUrl=package.MUSIC_URL).items():
            ET.SubElement(meta,k).text=v
        ET.SubElement(meta,'repository',type='git',url=package.REPOSITORY,commit=COMMIT)
        members['DanceRudiments.nuspec']=ET.tostring(root)
        return members
    def test_six_named_native_targets(self):
        self.assertEqual(set(package.BY_RID),{'linux-x64','linux-arm64','win-x64','win-arm64','osx-x64','osx-arm64'})
        self.assertEqual(len(package.PLATFORMS),6)
    def test_headers_reject_cross_architecture_and_truncation(self):
        for rid in package.BY_RID:
            with self.subTest(rid=rid):
                data=synthetic_header(rid);package.check_binary(data,rid)
                opposite=rid.replace('arm64','x64') if rid.endswith('arm64') else rid.replace('x64','arm64')
                with self.assertRaises(ValueError):package.check_binary(data,opposite)
                with self.assertRaises(ValueError):package.check_binary(data[:20],rid)
    def test_executables_are_not_native_library_assets(self):
        for rid in package.BY_RID:
            b=bytearray(synthetic_header(rid))
            if rid.startswith('linux'):struct.pack_into('<H',b,16,2)
            elif rid.startswith('win'):struct.pack_into('<H',b,86,0)
            else:struct.pack_into('<I',b,12,2)
            with self.assertRaises(ValueError):package.check_binary(bytes(b),rid)
    def test_bad_pe_offset_is_rejected(self):
        b=bytearray(synthetic_header('win-x64'));struct.pack_into('<I',b,60,2**32-1)
        with self.assertRaises(ValueError):package.check_binary(bytes(b),'win-x64')
    def test_staged_six_platform_set_verifies(self):
        package.verify_tree(self.native_tree(),COMMIT)
    def test_missing_native_rejected(self):
        folder=self.native_tree();(folder/'runtimes/linux-arm64/native/libdancerudiments_native.so').unlink()
        with self.assertRaises(OSError):package.verify_tree(folder,COMMIT)
    def test_extra_native_rejected(self):
        folder=self.native_tree();(folder/'runtimes/unexpected.txt').write_text('wrong')
        with self.assertRaises(ValueError):package.verify_tree(folder,COMMIT)
    def test_native_changes_after_staging_rejected(self):
        folder=self.native_tree();p=folder/'runtimes/linux-x64/native/libdancerudiments_native.so'
        p.write_bytes(p.read_bytes()+b'tampered')
        with self.assertRaises(ValueError):package.verify_tree(folder,COMMIT)
    def test_native_mixed_revision_rejected(self):
        folder=self.native_tree()
        with self.assertRaises(ValueError):package.verify_tree(folder,'a'*40)
    def test_stage_requires_full_revision(self):
        with self.assertRaises(ValueError):package.stage(self.folder,'linux-x64',self.folder/'out','main')
    def test_archive_structure_and_signature_normalization(self):
        members=self.members();a=self.folder/'expected.zip';b=self.folder/'signed.zip'
        write_zip(a,members);package.check_archive(a,COMMIT)
        write_zip(b,{**members,'.signature.p7s':b'synthetic repository signature'})
        package.compare_packages(a,b)
    def test_docs_credits_and_runtime_are_required(self):
        members=self.members()
        for name in ('README.md','licenses/THIRD_PARTY_NOTICES.md','docs/images/visualizer-mobile.png',
                     'runtimes/osx-arm64/native/libdancerudiments_native.dylib'):
            with self.subTest(name=name):
                copy=dict(members);copy.pop(name);p=self.folder/'missing.zip';write_zip(p,copy)
                with self.assertRaises((ValueError,KeyError)):package.check_archive(p,COMMIT)
    def test_music_link_is_required(self):
        members=self.members();members['README.md']=b'No credit here';p=self.folder/'bad.zip';write_zip(p,members)
        with self.assertRaises(ValueError):package.check_archive(p,COMMIT)
    def test_package_commit_is_required(self):
        members=self.members();members['DanceRudiments.nuspec']=members['DanceRudiments.nuspec'].replace(COMMIT.encode(),b'')
        p=self.folder/'bad.zip';write_zip(p,members)
        with self.assertRaises(ValueError):package.check_archive(p)
    def test_package_native_source_must_match_managed_source(self):
        members=self.members();name='build-info/win-arm64.json';m=json.loads(members[name]);m['source_commit']='b'*40
        members[name]=json.dumps(m).encode();p=self.folder/'bad.zip';write_zip(p,members)
        with self.assertRaises(ValueError):package.check_archive(p,COMMIT)
    def test_package_native_hash_checked(self):
        members=self.members();members['runtimes/win-x64/native/dancerudiments_native.dll']+=b'changed'
        p=self.folder/'bad.zip';write_zip(p,members)
        with self.assertRaises(ValueError):package.check_archive(p,COMMIT)
    def test_zip_path_and_private_data_rejected(self):
        members=self.members()
        for name in ('../escape','C:/absolute','x\\..\\escape','npm_recovery_codes.txt','old.patch'):
            with self.subTest(name=name):
                p=self.folder/'bad.zip';write_zip(p,{**members,name:b'x'})
                with self.assertRaises(ValueError):package.check_archive(p,COMMIT)
    def test_runtime_label_or_manifest_change_rejected(self):
        members=self.members();members['build-info/platforms.json']=b'{}'
        p=self.folder/'bad.zip';write_zip(p,members)
        with self.assertRaises(ValueError):package.check_archive(p,COMMIT)
    def test_restored_different_same_version_rejected(self):
        a=self.folder/'a.zip';b=self.folder/'b.zip';write_zip(a,{'file':b'a'});write_zip(b,{'file':b'b'})
        with self.assertRaises(ValueError):package.compare_packages(a,b)
    def test_duplicate_zip_member_rejected(self):
        import warnings
        p=self.folder/'bad.zip'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(p,'w') as z:z.writestr('duplicate','a');z.writestr('duplicate','b')
        with self.assertRaises(ValueError):package.package_payload(p)
        with self.assertRaises(ValueError):package.check_archive(p)
    def test_consumer_binding_source_is_local_only(self):
        source=self.folder/'artifacts & more';source.mkdir();p=self.folder/'nuget.config'
        package.consumer_config(source,p);root=ET.parse(p)
        sources={n.get('key'):n.get('value') for n in root.findall('./packageSources/add')}
        self.assertEqual(sources['local-binding'],str(source.resolve()))
        local=root.findall('./packageSourceMapping/packageSource[@key="local-binding"]/package')
        public=root.findall('./packageSourceMapping/packageSource[@key="nuget.org"]/package')
        self.assertEqual([n.get('pattern') for n in local],['DanceRudiments'])
        self.assertEqual([n.get('pattern') for n in public],['Microsoft.*'])
    def test_version_source_and_documentation(self):
        self.assertRegex(package.version(),r'^\d+\.\d+\.\d+$');package.check_source()
    def test_release_validator_detects_csharp_mismatch(self):
        # A fully isolated fixture; never changes the working tree.
        root=self.folder/'checkout';(root/'tools').mkdir(parents=True)
        (root/'tools/check_release_version.py').write_bytes((ROOT/'tools/check_release_version.py').read_bytes())
        for n in ('CMakeLists.txt','package.json','pyproject.toml'):(root/n).write_bytes((ROOT/n).read_bytes())
        project=root/'bindings/csharp/DanceRudiments/DanceRudiments.csproj';project.parent.mkdir(parents=True)
        project.write_text('<Project><PropertyGroup><Version>99.0.0</Version></PropertyGroup></Project>')
        r=subprocess.run([sys.executable,str(root/'tools/check_release_version.py'),'v'+package.version()],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('C# NuGet=99.0.0',r.stderr)
    def test_managed_imports_cover_exported_c_abi(self):
        header=(ROOT/'include/dancerudiments/c_api.h').read_text()
        imports=(ROOT/'bindings/csharp/DanceRudiments/NativeMethods.cs').read_text()
        exports=set(re.findall(r'DR_CALL (dr_\w+)\(',header));entrypoints=re.findall(r'EntryPoint="(dr_\w+)"',imports)
        self.assertEqual(exports,set(entrypoints));self.assertEqual(len(entrypoints),14)
        self.assertEqual(imports.count('CallingConvention=CallingConvention.Cdecl'),14)
        self.assertIn('SafeHandleZeroOrMinusOneIsInvalid',imports)
    def test_pack_has_complete_native_guard_and_author_metadata(self):
        root=ET.parse(package.PROJECT)
        self.assertEqual(root.findtext('./PropertyGroup/TargetFramework'),'net8.0')
        errors=root.findall('./Target[@Name="RequireAllNativeRuntimes"]/Error');self.assertEqual(len(errors),6)
        self.assertEqual(root.findtext('./PropertyGroup/PackageReadmeFile'),'README.md')
        self.assertEqual(root.findtext('./PropertyGroup/RepositoryUrl'),package.REPOSITORY)
    def test_workflow_publish_is_release_only_and_after_consumers(self):
        text=(ROOT/'.github/workflows/csharp.yml').read_text()
        for name in ('publish-nuget','publish-github-packages','attach-release'):
            body=text.split('  '+name+':',1)[1]
            self.assertTrue(body.lstrip().startswith('needs: [validate, pack, consume]\n    if: github.event_name == \'release\''))
        self.assertIn('unset DANCERUDIMENTS_NATIVE_LIBRARY',text)
        self.assertIn('--configfile artifacts/consume.config',text)
        self.assertIn('-p:UsePackedBinding=true',text)
        self.assertIn('NuGet/login@v1',text)
        self.assertIn('python tools/csharp_package.py compare',text)
        self.assertNotIn('pull_request_target:',text)
    def test_original_core_is_not_a_managed_motion_mirror(self):
        native=(ROOT/'bindings/csharp/native/CMakeLists.txt').read_text()
        self.assertIn('${PROJECT_SOURCE_DIR}/src/dance_rudiments.cpp',native)
        self.assertIn('${PROJECT_SOURCE_DIR}/src/sampled_pattern.cpp',native)
        methods=(ROOT/'bindings/csharp/DanceRudiments/Rudiments.cs').read_text()
        self.assertIn('NativeMethods.Sample(',methods);self.assertIn('NativeMethods.SampleMany(',methods)
        self.assertNotIn('Math.Sin',methods)

if __name__=='__main__':unittest.main()
