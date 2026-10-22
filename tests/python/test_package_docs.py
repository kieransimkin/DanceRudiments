"""Documentation/author-link regression checks. Music: https://kieransimkin.co.uk/my-songs/"""
from pathlib import Path
import importlib.util
import io
import json
import re
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('package_docs_check', ROOT/'tools/check_package_docs.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class PackageDocumentationTests(unittest.TestCase):
    def test_source_metadata(self):
        check.check_source(ROOT)

    def fixture(self):
        link = check.MUSIC_URL.encode()
        return {
            'package/README.md': link,
            'package/AUTHORS.md': link,
            'package/docs/bindings.md': link,
            'package/examples/bindings/python/quickstart.py': b'# test example',
            **{'package/docs/images/'+name: b'PNG fixture' for name in check.IMAGES},
            **{'package/docs/branding/'+name: link for name in check.BRANDING},
            'package/package.json': json.dumps({'homepage':check.MUSIC_URL}).encode(),
        }

    def check_zip(self, files, suffix='.zip'):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/('fixture'+suffix)
            with zipfile.ZipFile(path,'w') as archive:
                for name, data in files.items(): archive.writestr(name,data)
            check.check_archive(path)

    def write_source_fixture(self, root):
        files = {name.removeprefix('package/'): data
                 for name, data in self.fixture().items()}
        link = check.MUSIC_URL.encode()
        files.update({name: link for name in (
            'pyproject.toml', 'package-lock.json', 'CMakeLists.txt',
            'conanfile.py', 'packaging/CPP_BINARY_README.md')})
        files['package.json'] = json.dumps({
            'homepage': check.MUSIC_URL,
            'author': {'url': check.MUSIC_URL},
            'description': 'Synthetic package '+check.MUSIC_URL,
        }).encode()
        for family in ('atlas', 'continuum', 'club', 'dancefloor'):
            files['tools/build_'+family+'_collection.py'] = link
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def test_source_preflight_rejects_new_nested_readme_without_credit(self):
        # A new README must fail before an archive is built, even without a
        # hand-maintained entry in the metadata list or a Git index.
        for name in ('examples/rig-motion/README.md', 'motion-packages/README.md',
                     'tools/new-tool/deep/ReadMe.md', 'bindings/new/README.md'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.write_source_fixture(root)
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('New first-party documentation', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, re.escape(name)+': missing author music link'):
                    check.check_source(root)
                path.write_text('By Kieran Simkin: '+check.MUSIC_URL, encoding='utf-8')
                check.check_source(root)

    def test_source_preflight_preserves_upstream_attribution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_source_fixture(root)
            path = root / 'collections/initial/sources/upstream/README.md'
            path.parent.mkdir(parents=True)
            original = b'Original upstream authors and licence'
            path.write_bytes(original)
            check.check_source(root)
            self.assertEqual(path.read_bytes(), original)

    def test_source_exception_is_exact_sources_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_source_fixture(root)
            path = root / 'docs/sources-guide/README.md'
            path.parent.mkdir(parents=True)
            path.write_text('First-party source guide', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'missing author music link'):
                check.check_source(root)

    def test_nested_packaged_readmes_keep_strict_archive_check(self):
        for name in ('examples/rig-motion/README.md', 'motion-packages/README.md'):
            with self.subTest(name=name):
                files = self.fixture()
                files['package/'+name] = b'Missing author link'
                with self.assertRaisesRegex(ValueError, re.escape(name)+': missing author music link'):
                    self.check_zip(files)
                files['package/'+name] += ('\n'+check.MUSIC_URL).encode()
                self.check_zip(files)

    def test_zip_contract(self):
        self.check_zip(self.fixture())

    def test_missing_readme_credit_rejected(self):
        files=self.fixture();files['package/README.md']=b'No music link'
        with self.assertRaisesRegex(ValueError,'missing author music link'): self.check_zip(files)

    def test_missing_screenshot_rejected(self):
        files=self.fixture();del files['package/docs/images/'+check.IMAGES[0]]
        with self.assertRaisesRegex(ValueError,'missing docs/images'): self.check_zip(files)

    def test_missing_examples_rejected(self):
        files=self.fixture();del files['package/examples/bindings/python/quickstart.py']
        with self.assertRaisesRegex(ValueError,'runnable binding examples'): self.check_zip(files)

    def test_missing_logo_rejected(self):
        files=self.fixture();del files['package/docs/branding/logo.svg']
        with self.assertRaisesRegex(ValueError,'missing docs/branding/logo.svg'): self.check_zip(files)

    def test_branding_readme_requires_canonical_author_link(self):
        files=self.fixture();files['package/docs/branding/README.md']=b'https://kieransimkin.co.uk/'
        with self.assertRaisesRegex(ValueError,'missing author music link'): self.check_zip(files)

    def test_wheel_metadata_required(self):
        with self.assertRaisesRegex(ValueError,'distribution metadata'): self.check_zip(self.fixture(),'.whl')

    def test_wheel_metadata_credit_required(self):
        files=self.fixture();files['dancerudiments-0.1.3.dist-info/METADATA']=b'Name: dancerudiments'
        with self.assertRaisesRegex(ValueError,'missing author music link'): self.check_zip(files,'.whl')

    def test_wheel_contract(self):
        files=self.fixture();files['dancerudiments-0.1.3.dist-info/METADATA']=('Project-URL: Music, '+check.MUSIC_URL).encode()
        self.check_zip(files,'.whl')

    def test_third_party_readme_not_rebranded(self):
        files=self.fixture();files['package/collections/initial/sources/upstream/README.md']=b'Upstream attribution'
        self.check_zip(files)

    def test_tar_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'fixture.tgz'
            with tarfile.open(path,'w:gz') as archive:
                for name,data in self.fixture().items():
                    item=tarfile.TarInfo(name);item.size=len(data);archive.addfile(item,io.BytesIO(data))
            check.check_archive(path)

    def test_unsupported_archive_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unsupported archive'):check.check_archive(Path('x.exe'))

    def test_package_versions_unchanged(self):
        self.assertEqual(json.loads((ROOT/'package.json').read_text())['version'],
                         json.loads((ROOT/'package-lock.json').read_text())['version'])


if __name__ == '__main__':unittest.main()
