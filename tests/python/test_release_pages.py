"""Focused immutable site assembly/integrity tests; no downloaded media."""
from functools import partial
import errno
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('release_pages', ROOT / 'tools/package_release_pages.py')
pages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pages)
VERSION, COMMIT = '1.2.3', 'a' * 40


class ReleasePagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.html'
        self.source.write_text('<!doctype html><header>Visualizer</header><script id="native">unchanged()</script>')
        self.source.with_suffix('.json').write_text(json.dumps(dict(version=VERSION, source_commit=COMMIT,
            html_sha256=pages.sha256(self.source.read_bytes()).hexdigest(), pattern_count=2)))
        self.site = self.root / 'site'
        self.output = self.root / 'attachments'
        pages.prepare(self.source, self.site, VERSION, COMMIT)
        mesh = self.site / 'meshes'
        mesh.mkdir()
        for name in ('index.html', 'app.js', 'style.css', 'recording.wasm'):
            (mesh / name).write_bytes(('fixture:' + name).encode('ascii'))
        (mesh / 'build.json').write_text(json.dumps(dict(format='dancerudiments.mesh-demo-build',
            schema_version=1, version=VERSION, commit=COMMIT, sceneIds=['boxbot', 'prism'])))
        (mesh / 'catalogue.json').write_text(json.dumps(dict(format='dancerudiments.mesh-demo-catalogue',
            schema_version=1, scenes=[dict(id='boxbot'), dict(id='prism')])))
        self.report = self.root / 'browser.json'
        self.write_report()

    def write_report(self):
        self.report.write_text(json.dumps(dict(format=pages.QA_FORMAT, schema_version=1,
            status='PASS', scope='complete-site', version=VERSION, source_commit=COMMIT,
            scenes=[dict(id='boxbot'), dict(id='prism')], tested_assets=[
                pages.file_identity(p, p.relative_to(self.site).as_posix())
                for p in pages.site_files(self.site)
                if p not in (self.site / 'site-manifest.json', self.site / 'meshes/validation.json')])))

    def seal(self):
        return pages.seal(self.site, self.output, self.report, VERSION, COMMIT)

    def test_complete_site_zip_preserves_visualizer_and_all_mesh_assets(self):
        original = self.source.read_bytes()
        manifest = self.seal()
        self.assertEqual(self.source.read_bytes(), original)
        self.assertIn(b'<script id="native">unchanged()</script>', (self.site / 'index.html').read_bytes())
        self.assertEqual((self.site / 'index.html').read_text().count('id="mesh-demos-link"'), 1)
        self.assertEqual(manifest['source_commit'], COMMIT)
        with zipfile.ZipFile(self.output / f'DanceRudiments-pages-v{VERSION}.zip') as archive:
            names = set(archive.namelist())
            self.assertTrue({'index.html', 'meshes/index.html', 'meshes/recording.wasm', 'site-manifest.json'} <= names)
            self.assertFalse(any(name.endswith('.zip') for name in names))
        with zipfile.ZipFile(self.output / f'DanceRudiments-mesh-demos-v{VERSION}.zip') as archive:
            self.assertTrue(all(name.startswith('meshes/') for name in archive.namelist()))

    def test_post_browser_asset_change_requires_new_test(self):
        (self.site / 'meshes/app.js').write_text('changed after browser test')
        with self.assertRaisesRegex(ValueError, 'changed after browser'):
            self.seal()
        self.assertFalse(self.output.exists())

    def test_unchecked_stale_asset_is_not_silently_packaged(self):
        (self.site / 'meshes/old-motion.json').write_text('stale fixture')
        with self.assertRaisesRegex(ValueError, 'entire current site'):
            self.seal()

    def test_archive_destination_cannot_include_itself(self):
        with self.assertRaisesRegex(ValueError, 'separate directories'):
            pages.seal(self.site, self.site / 'downloads', self.report, VERSION, COMMIT)

    def test_symlink_assets_are_rejected(self):
        try:
            (self.site / 'meshes/linked').symlink_to(self.source)
        except OSError as error:
            if (error.errno in (errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP)
                    or getattr(error, 'winerror', None) == 1314):
                self.skipTest(f'Symlink creation is unavailable in this environment: {error}')
            raise
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.seal()

    def test_wrong_release_identity_or_failed_report_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            pages.seal(self.site, self.output, self.report, VERSION, 'b' * 40)
        report = json.loads(self.report.read_text())
        report['status'] = 'FAIL'
        self.report.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'passing mesh browser report'):
            self.seal()

    def test_only_complete_site_reports_with_the_exact_schema_can_seal(self):
        original = json.loads(self.report.read_text())
        for field, value in (('format', 'unrelated'), ('schema_version', 2),
                             ('scope', 'mesh-gallery-only')):
            with self.subTest(field=field):
                report = {**original, field: value}
                self.report.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, 'passing mesh browser report'):
                    self.seal()
        self.assertFalse(self.output.exists())

    def test_both_actual_scene_ids_must_be_distinct_and_verified(self):
        original = json.loads(self.report.read_text())
        for ids in (('boxbot', 'boxbot'), ('boxbot', 'unrelated'), ('prism',)):
            with self.subTest(ids=ids):
                report = {**original, 'scenes': [dict(id=value) for value in ids]}
                self.report.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, 'distinct boxbot and prism'):
                    self.seal()
        self.assertFalse(self.output.exists())

    def test_live_directory_routes_and_all_public_hashes(self):
        self.seal()
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(self.site)))
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/'
        result = pages.verify(url, self.site / 'site-manifest.json')
        self.assertEqual(result['status'], 'PASS')
        (self.site / 'meshes/recording.wasm').write_bytes(b'wrong deployed bytes')
        with self.assertRaisesRegex(ValueError, 'Deployed'):
            pages.verify(url, self.site / 'site-manifest.json')

    def test_precompressed_asset_rejects_browser_transport_decompression(self):
        (self.site / 'meshes/motion.json.gz').write_bytes(b'original stored gzip bytes')
        self.write_report()
        self.seal()
        class FakeResponse(io.BytesIO):
            status = 200
            def __init__(self, payload, encoded):
                super().__init__(payload)
                self.headers = {'Content-Encoding': 'gzip'} if encoded else {}
        def response(request, timeout):
            relative = urlsplit(request.full_url).path.removeprefix('/')
            if not relative or relative.endswith('/'):
                relative += 'index.html'
            return FakeResponse((self.site / relative).read_bytes(), relative.endswith('.gz'))
        with patch.object(pages, 'urlopen', side_effect=response):
            with self.assertRaisesRegex(ValueError, 'identity Content-Encoding'):
                pages.verify('https://example.invalid/', self.site / 'site-manifest.json')


if __name__ == '__main__':
    unittest.main()
