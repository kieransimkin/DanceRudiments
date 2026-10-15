"""Display capabilities are packaged with the official shared harness."""
from pathlib import Path
import tempfile
import unittest

from dancerudiments_authoring.harness import (HARNESS_DISPLAY_API_VERSION, DISPLAY_MODES,
    ASSETS, build_recording_harness, render_template)
from dancerudiments_authoring.recording import Recording, RecordingClock


class DisplayTests(unittest.TestCase):
    def test_capability_and_export_report(self):
        self.assertEqual(HARNESS_DISPLAY_API_VERSION, 1)
        self.assertEqual(DISPLAY_MODES, ('xy', 'bars'))
        record = Recording('display_fixture', ('drums', 'bass', 'treble', 'other'),
            ((-.5, .2, 0., .8), (.3, -.4, .5, 0.)), RecordingClock(120, 'synthetic test'))
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'index.html'
            report = build_recording_harness([record], out)
            self.assertEqual(report['display_modes'], ['xy', 'bars'])
            page = out.read_text()
            self.assertIn('id="view-mode"', page)
            self.assertIn('value="bars"', page)
            self.assertIn('role', page)
            self.assertFalse(report['audio_included'])

    def test_catalogue_uses_same_switch_and_renderer(self):
        payload = dict(version='test', source_commit='test', pack={'patterns': []},
                       source_kind='native-default-catalogue')
        page = render_template(payload)
        self.assertIn('Movement view', page)
        self.assertIn('channel-bars', page)
        self.assertIn("sample(plot.i,pip)", (ASSETS / 'app.js').read_text())

    def test_packaged_checks_do_not_import_playwright_at_module_import(self):
        from dancerudiments_authoring import harness_checks
        self.assertTrue(callable(harness_checks.check_display_modes))
        self.assertTrue(callable(harness_checks.check_running_view_switch))
