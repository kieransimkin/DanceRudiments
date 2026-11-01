#!/usr/bin/env python3
"""Exercise the local loop authoring UI on the actual Kandi skin and native WASM.

This gate copies an explicitly labelled automated-test workspace. Its saved
decisions are test fixtures, never human musical or visual approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from dancerudiments_authoring.loop_review import audio_seconds_to_pip, read_review
from review_motion_loop import ReviewWorkspace, create_server, preflight


def test(workspace, output_dir, *, chromium=None):
    from playwright.sync_api import sync_playwright

    source, output = Path(workspace).resolve(), Path(output_dir).resolve()
    original = ReviewWorkspace(source)
    if original.config['review_kind'] != 'automated_test':
        raise ValueError('Browser validation requires an explicitly automated-test workspace')
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError('Browser output must be a new directory outside the source workspace')
    preflight(output.parent)
    output.mkdir()
    copied = output/'workspace'
    shutil.copytree(source, copied)
    server = create_server(copied)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks, errors, blocked, failed_requests = [], [], [], []
    report = {'format': 'dancerudiments.loop-review-browser.v1', 'schema_version': 1,
                  'scope': 'local-authoring-automated-test', 'human_approved': False,
                  'source_build': read_review(copied/'site'/'build.json'), 'checks': checks,
                  'browser_errors': errors, 'unexpected_network_requests': blocked,
                  'failed_http_requests': failed_requests, 'operation_seconds': {}, 'http_operations': []}

    def check(ok, message):
        if not ok:
            raise AssertionError(message)
        checks.append(message)
        print(message, flush=True)

    def public_session():
        return server.workspace.session()

    try:
        with sync_playwright() as pw:
            options = {'headless': True, 'args': ['--no-sandbox', '--mute-audio', '--disable-dev-shm-usage',
                '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
            if chromium:
                options['executable_path'] = str(Path(chromium).resolve())
            browser = pw.chromium.launch(**options)
            report['browser_version'] = browser.version
            context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce',
                                          service_workers='block', accept_downloads=True)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            request_starts = {}
            page.on('request', lambda request: request_starts.__setitem__(request,time.monotonic())
                    if urlsplit(request.url).path.startswith('/api/') else None)
            def capture_failure(response):
                path=urlsplit(response.url).path
                if response.request in request_starts:
                    elapsed=time.monotonic()-request_starts.pop(response.request)
                    report['http_operations'].append({'method': response.request.method,'path': path,
                        'status': response.status,'seconds': elapsed})
                    if not path.startswith('/api/files/'):
                        print(f'{response.request.method} {path}: HTTP {response.status}, {elapsed:.2f} s',flush=True)
                if response.status >= 400:
                    message=response.text()[:1000]
                    failed_requests.append({'path': path,'status': response.status,'message': message})
                    print(f'{path}: {message}',flush=True)
            page.on('response', capture_failure)
            origin = urlsplit(server.review_url)

            def restrict(route):
                target = urlsplit(route.request.url)
                if target.scheme in ('http', 'https') and target.netloc != origin.netloc:
                    blocked.append(target.scheme+'://'+target.netloc+target.path)
                    route.abort()
                else:
                    route.continue_()
            page.route('**/*', restrict)
            page.goto(server.review_url, wait_until='networkidle', timeout=180000)
            page.wait_for_function('()=>meshDemo.debugSnapshot().loopWorkspace?.revision===1', timeout=30000)
            snapshot = lambda: page.evaluate('()=>meshDemo.debugSnapshot()')
            def wait_revision(expected, *, timeout=180000):
                page.wait_for_function('(revision)=>{const state=meshDemo.debugSnapshot().loopWorkspace;'
                    'return state?.error||(state?.revision===revision&&!state.busy);}', arg=expected, timeout=timeout)
                if snapshot()['loopWorkspace']['error']:
                    raise AssertionError(snapshot()['loopWorkspace']['error'])
            def wait_loaded():
                page.wait_for_function('()=>{const state=meshDemo.debugSnapshot().loopWorkspace;'
                    'return state?.error||(state?.loaded&&!state.busy);}', timeout=180000)
                if snapshot()['loopWorkspace']['error']:
                    raise AssertionError(snapshot()['loopWorkspace']['error'])
            check(snapshot()['activeNativeHandles'] == 0, 'Opening a review session does not allocate a native motion or Kandi skin')
            check(page.locator('#scene-cards').is_hidden(), 'An imported Action workspace has no unrelated performance navigation')
            check('Review one Action.' in page.locator('#page-title').inner_text()
                  and 'two real motion-capture' not in page.locator('.intro-copy').inner_text(),
                  'The local workspace identifies a single imported Action')
            check(page.locator('.loop-scope').is_visible()
                  and 'no human approval' in page.locator('.loop-scope').inner_text(),
                  'The browser visibly labels automated review evidence')
            mismatch = context.new_page()
            mismatch.on('pageerror', lambda error: errors.append(str(error)))
            mismatch.route('**/*',restrict)
            def change_source_identity(route):
                response=route.fetch()
                document=response.json()
                document['selection']['source']['original_source_sha256']='f'*64
                route.fulfill(response=response,json=document)
            mismatch.route('**/api/session',change_source_identity)
            mismatch.goto(server.review_url,wait_until='networkidle',timeout=180000)
            mismatch.wait_for_function('()=>Boolean(meshDemo.debugSnapshot().loopWorkspace?.error)',timeout=30000)
            mismatched=mismatch.evaluate('()=>meshDemo.debugSnapshot()')
            check('different source Action or rig' in mismatched['loopWorkspace']['error']
                  and mismatched['activeNativeHandles']==0,
                  'The actual review UI rejects mismatched source identity before loading native motion')
            mismatch.close()
            page.bring_to_front()
            started = time.monotonic()
            page.locator('#loop-load').click()
            wait_loaded()
            report['operation_seconds']['initial_load'] = time.monotonic()-started
            state = snapshot()
            check(state['error'] is None and state['loopWorkspace']['error'] is None, 'Exact local motion and audio load without errors')
            check(state['vertexCount'] > 1000 and state['skinnedMeshCount'] > 0, 'The actual Kandi skinned character is present')
            check(state['loopWorkspace']['audioBytesVerified'] and state['loopWorkspace']['motionBytesVerified'], 'Audio master and derivative bytes match their saved SHA-256 identities')
            check(state['activeNativeHandles'] == 2, 'Original and corrected motion use two owned handles of the existing native sampler')

            # Establish controlled source-clock correspondences for the gate.
            # These are explicitly test annotations rather than detector truth.
            session = public_session()
            bounds = session['selection']['bounds']
            start, end = bounds['start_seconds'], bounds['end_seconds']
            audio_start = max(1.0, session['alignment']['report']['audio_source']['valid_segments_seconds'][0][0]+.1)
            audio_end = audio_start + (end-start)*1.1
            page.locator('details').filter(has=page.locator('#loop-anchors')).locator('summary').click()
            page.locator('#loop-anchors').fill(f'{start}, {audio_start}\n{end}, {audio_end}')
            page.locator('#loop-offset').fill('0.01')
            page.locator('#loop-reviewer').fill('Automated browser test')
            page.locator('#loop-notes').fill('Controlled playback and persistence fixture; no human listening or visual acceptance.')
            page.locator('#loop-draft').click()
            wait_revision(2)
            check(not public_session()['export_ready'], 'Saving a draft cannot promote a loop for export')
            page.reload(wait_until='networkidle', timeout=180000)
            page.wait_for_function('()=>meshDemo.debugSnapshot().loopWorkspace?.revision===2', timeout=30000)
            check(page.locator('#loop-reviewer').input_value() == 'Automated browser test'
                  and page.locator('#loop-offset').input_value() == '0.01', 'Reviewer and phase draft survive closing and reopening the page')
            restored_anchors = [[float(value.strip()) for value in line.split(',')]
                                for line in page.locator('#loop-anchors').input_value().splitlines()]
            check(restored_anchors == [[start, audio_start], [end, audio_end]],
                  'Manual source-clock anchors reopen without changing their values')
            page.locator('#loop-load').click()
            wait_loaded()

            # A different beat interpretation creates a new native selection,
            # and the browser must discard approval of the previous selection.
            old_beats = session['selection']['beat_count']
            new_beats = old_beats//2 if old_beats % 2 == 0 and old_beats >= 2 else old_beats
            new_start, new_end = start+(end-start)*.001, end-(end-start)*.001
            page.locator('#loop-start').fill(str(new_start))
            page.locator('#loop-end').fill(str(new_end))
            page.locator('#loop-beats').fill(str(new_beats))
            started = time.monotonic()
            page.locator('#loop-finish').click()
            wait_revision(3)
            report['operation_seconds']['finish'] = time.monotonic()-started
            session = public_session()
            check(session['selection']['sample_count'] == new_beats*64 and not session['review']
                  and session['selection']['bounds'] == {'start_seconds': new_start,'end_seconds': new_end},
                  'Finishing the edited boundaries and beat count recompiles the selected phrase and invalidates prior review')
            check(snapshot()['finishedMotion']['sampleCount'] == new_beats*64, 'The browser replaces the native derivative with the newly compiled sample count')

            for name in ('seam', 'feet', 'skin'):
                page.locator('#loop-'+name).select_option('accept')
            started = time.monotonic()
            page.locator('#loop-save').click()
            wait_revision(4)
            report['operation_seconds']['save_review'] = time.monotonic()-started
            session = public_session()
            review = session['review']
            check(review['status'] == 'automated_test_fixture' and review['human_approved'] is False,
                  'Saved automated timing and visual verdicts remain explicitly unapproved test evidence')
            check(page.locator('.loop-scope').is_visible()
                  and 'no human approval' in page.locator('.loop-scope').inner_text(),
                  'The automated-test notice remains visible after saving decisions')
            check(session['export_ready'], 'A complete test-only review can exercise the isolated package export gate')
            playback = review['playback']
            sample_time = playback['audio_seconds_range'][0] + .37*(playback['audio_seconds_range'][1]-playback['audio_seconds_range'][0])
            page.locator('#loop-audio').evaluate('(audio,t)=>{audio.pause();audio.currentTime=t;}', sample_time)
            expected_pip = audio_seconds_to_pip(playback, sample_time)
            page.wait_for_function('(pip)=>meshDemo.debugSnapshot().currentPip===pip', arg=expected_pip, timeout=10000)
            state_file = read_review(copied/'state.json')
            motion = read_review(copied/state_file['selection_dir']/'finished.motion.json')
            actual = snapshot()['nativeNormalizedSample']
            expected = motion['recording']['samples'][expected_pip]
            native_error = max(abs(a-b) for a,b in zip(actual,expected))
            check(len(actual)==len(expected) and native_error < 1e-10,
                  'Auditioning maps the exact audio clock to the expected native normalized sample')
            report['maximum_native_sample_error'] = native_error
            page.locator('#loop-original').click()
            check(snapshot()['loopWorkspace']['loaded'], 'Original comparison retains the same saved audio-clock review')
            page.locator('#loop-finished').click()
            page.locator('#loop-repeat').check()
            page.locator('#loop-audition').click()
            page.wait_for_function('()=>meshDemo.debugSnapshot().loopWorkspace.repeatCount>0', timeout=15000)
            check(snapshot()['loopWorkspace']['audioPlaying'], 'Explicit repeat loops the master interval and native motion together')
            page.locator('#loop-audio').evaluate('(audio)=>audio.pause()')

            # Optimistic writes must fail when another tab has advanced state.
            request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/draft',
                data=json.dumps({'expected_revision': 1,'draft': {}}).encode(),method='POST',
                headers={'Content-Type':'application/json','X-Loop-Review-Token':server.review_token,
                         'Origin':f'http://127.0.0.1:{server.server_port}'})
            try:
                urllib.request.urlopen(request)
                raise AssertionError('Stale review write unexpectedly succeeded')
            except urllib.error.HTTPError as error:
                check(error.code==409, 'Stale revision writes are rejected by the local authoring server')

            page.locator('details').filter(has=page.locator('#loop-export')).locator('summary').click()
            started = time.monotonic()
            with page.expect_download(timeout=180000) as download:
                page.locator('#loop-export').click()
            archive=output/'reviewed-loop-test-fixture.zip'
            download.value.save_as(archive)
            wait_revision(5)
            report['operation_seconds']['export'] = time.monotonic()-started
            with zipfile.ZipFile(archive) as package:
                names=package.namelist()
                check(not any(name.lower().endswith(('.mp3','.wav','.fbx','.blend','.glb')) for name in names),
                      'The optional package contains no audio master or target model assets')
                manifest=json.loads(package.read('manifest.json'))
                check(len(manifest['clips'])==1 and manifest['clips'][0]['sample_count']==new_beats*64,
                      'The downloaded package contains the exact reviewed native loop extent')
            report['export_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
            page.reload(wait_until='networkidle', timeout=180000)
            page.wait_for_function('()=>meshDemo.debugSnapshot().loopWorkspace?.savedReview', timeout=30000)
            check(page.locator('#loop-seam').input_value()=='accept' and page.locator('#loop-reviewer').input_value()=='Automated browser test',
                  'Saved timing and independent visual decisions survive reopening after export')
            page.locator('#loop-load').click()
            wait_loaded()
            page.locator('#loop-audio').evaluate('(audio,t)=>{audio.pause();audio.currentTime=t;}',sample_time)
            page.wait_for_function('(pip)=>{const state=meshDemo.debugSnapshot();'
                'return state.characterVisible&&state.currentPip===pip;}',arg=expected_pip,timeout=10000)
            check(snapshot()['characterVisible'], 'Saved review reopening renders Kandi at an interior mapped audio time')
            page.evaluate('()=>scrollTo(0,0)')
            page.screenshot(path=str(output/'desktop.png'),full_page=False)
            page.set_viewport_size({'width': 390,'height': 844})
            page.locator('.workspace').evaluate('(element)=>window.scrollTo(0,element.offsetTop)')
            check(page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth'), 'The local review controls fit a mobile-width viewport')
            page.screenshot(path=str(output/'mobile.png'),full_page=False)
            page.locator('#loop-offset').fill('0.02')
            check(page.locator('#loop-export').is_disabled() and page.locator('#loop-seam').input_value()=='unreviewed',
                  'Editing timing invalidates prior visual acceptance and disables export in the active review')
            page.locator('#unload-scene').click()
            page.wait_for_function('()=>meshDemo.debugSnapshot().activeNativeHandles===0&&!meshDemo.debugSnapshot().loopWorkspace.loaded', timeout=10000)
            check(not snapshot()['loopWorkspace']['audioPlaying'], 'Unload releases native handles and pauses the audio master')
            check(not errors and not blocked and not failed_requests,
                  'The complete review flow has no browser errors, failed HTTP requests or external network requests')
            context.close()
            browser.close()
        report['status']='PASS'
    except BaseException:
        report['status']='FAIL'
        raise
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        (output/'browser-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--chromium')
    args=parser.parse_args(argv)
    report=test(args.workspace,args.output_dir,chromium=args.chromium)
    print(json.dumps({'status': report['status'],'checks': len(report['checks']),'human_approved': False},indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
