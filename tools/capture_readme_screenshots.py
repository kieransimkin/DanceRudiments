#!/usr/bin/env python3
"""Capture the real self-contained visualizer. Music: https://kieransimkin.co.uk/my-songs/"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--output', type=Path, default=Path('docs/images'))
    parser.add_argument('--browser', help='Optional installed Chromium executable')
    parser.add_argument('--in-memory', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as pw:
        options = {'headless': True}
        if args.browser:
            options['executable_path'] = args.browser
        browser = pw.chromium.launch(**options)
        page = browser.new_page(viewport={'width': 1440, 'height': 1400}, device_scale_factor=1)
        page.on('pageerror', lambda e: errors.append(str(e)))
        if args.in_memory:
            page.set_content(args.html.read_text(encoding='utf-8'), wait_until='load', timeout=90000)
        else:
            page.goto(args.html.resolve().as_uri(), wait_until='load', timeout=90000)
        page.wait_for_function('window.audition?.ready', timeout=90000)
        page.locator('#related-only').check()
        page.locator('#compare-beat').click()
        page.evaluate('window.audition.setBeat(2.75)')
        page.wait_for_function('window.audition.state().renderedLastFrame > 0')
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(args.output/'visualizer-amen-desktop.png'))
        page.locator('#beat-score-details').evaluate('(el) => el.open = true')
        page.locator('#beat-score-details').scroll_into_view_if_needed()
        page.locator('.midi-panel').screenshot(path=str(args.output/'visualizer-midi-score.png'))
        page.locator('#beat-score-details').evaluate('(el) => el.open = false')
        page.set_viewport_size({'width': 420, 'height': 1100})
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(args.output/'visualizer-mobile.png'))
        state = page.evaluate('window.audition.state()')
        browser.close()
    if errors:
        raise RuntimeError('\n'.join(errors))
    (args.output/'capture.json').write_text(json.dumps({
        'source_sha256': sha256(args.html.read_bytes()).hexdigest(),
        'loading': 'in-memory' if args.in_memory else 'file-navigation',
        'desktop_viewport': [1440, 1400], 'mobile_viewport': [420, 1100],
        'state': state, 'page_errors': errors,
        'author_url': 'https://kieransimkin.co.uk/my-songs/'}, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
