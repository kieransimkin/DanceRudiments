"""Browser smoke test of the committed Kandi Boom Three.js proof of concept.

Requires npm ci (three) and python -m pip install playwright, plus Chromium.
Imports are rewritten in a temporary local copy only: the source demo remains
unchanged. The test never depends on jsDelivr or a network connection.

python tools/test_kandi_boom_browser.py --output-dir generated/kandi-browser-qa
"""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import pathlib
import shutil
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def run(output_dir, browser_path=None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError('Install playwright first: python -m pip install playwright==1.64.0') from exc

    source_html = (ROOT / 'harness/kandi-boom/index.html').read_text(encoding='utf-8')
    from_cdn = 'https://cdn.jsdelivr.net/npm/three@0.160.1/'
    if from_cdn not in source_html:
        raise RuntimeError('Three.js import map changed; update local test fixture')
    local_html = source_html.replace(from_cdn, '/vendor/three/')
    three = ROOT / 'node_modules/three'
    if not (three / 'build/three.module.js').is_file():
        raise RuntimeError('Missing node_modules/three; run npm ci in repository root')

    with tempfile.TemporaryDirectory(prefix='kandi-browser-fixture-') as temp_dir:
        temp = pathlib.Path(temp_dir)
        (temp / 'index.html').write_text(local_html, encoding='utf-8')
        (temp / 'vendor').mkdir()
        (temp / 'vendor/three').symlink_to(three.resolve(), target_is_directory=True)
        shutil.copytree(ROOT / 'harness/kandi-boom/assets', temp / 'assets')
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(temp)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        results = {'schema': 'dancerudiments.kandi-boom.browser-qa/v1',
                   'source_demo': 'harness/kandi-boom/index.html',
                   'local_three_js': True, 'screenshots': []}
        try:
            with sync_playwright() as playwright:
                kwargs = {'headless': True,
                          'args': ['--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
                if browser_path:
                    kwargs['executable_path'] = str(browser_path)
                browser = playwright.chromium.launch(**kwargs)
                page = browser.new_page(viewport={'width': 1100, 'height': 850}, device_scale_factor=1)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('requestfailed', lambda request: errors.append(f'{request.url}: request failed'))
                page.goto(f'http://127.0.0.1:{server.server_port}/index.html', wait_until='domcontentloaded')
                page.wait_for_function('''() => {
                    const text = document.getElementById('status').textContent;
                    if (text.startsWith('Failed')) throw new Error(text);
                    return text.startsWith('Loaded');
                }''', timeout=45000)
                status = page.locator('#status').inner_text()
                if '24 bones' not in status:
                    raise RuntimeError(f'unexpected FBX loader result: {status}')
                page.wait_for_timeout(600)
                output_dir.mkdir(parents=True, exist_ok=True)
                for motion in ('idle', 'groove'):
                    page.locator('#motion').select_option(motion)
                    page.wait_for_timeout(350)
                    image = output_dir / f'kandi-browser-{motion}.png'
                    blob = page.locator('#stage canvas').screenshot(path=str(image))
                    if len(blob) < 25000:
                        raise RuntimeError(f'WebGL canvas appears blank or incorrectly framed ({motion})')
                    results['screenshots'].append({'motion': motion, 'file': image.name,
                                                   'bytes': len(blob)})
                phase_before = page.locator('#phase').inner_text()
                page.wait_for_timeout(440)
                phase_after = page.locator('#phase').inner_text()
                if phase_before == phase_after:
                    raise RuntimeError('beat indicator did not advance')
                page.locator('#play').click()
                if page.locator('#play').inner_text() != 'Play':
                    raise RuntimeError('Pause control did not respond')
                paused = page.locator('#phase').inner_text()
                page.wait_for_timeout(340)
                if page.locator('#phase').inner_text() != paused:
                    raise RuntimeError('paused beat phase advanced')
                if errors:
                    raise RuntimeError('browser errors: ' + '; '.join(errors))
                results.update({'fbx_status': status, 'transport_smoke_test_passed': True,
                                'page_errors': []})
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        (output_dir / 'report.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(results, indent=2))
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=pathlib.Path, default=pathlib.Path('generated/kandi-browser-qa'))
    parser.add_argument('--chromium', type=pathlib.Path)
    args = parser.parse_args()
    run(args.output_dir, args.chromium)


if __name__ == '__main__':
    main()
