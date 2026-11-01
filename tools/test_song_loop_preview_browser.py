#!/usr/bin/env python3
"""Headless UI smoke for generated, audio-free song/rig loop viewer.

Serves only the generated artifact over localhost. Uploads an exact bundled
master through a browser file picker to test hash verification in memory; the
song is never copied into the review artifact or screenshot directory.
"""
from __future__ import annotations
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading


def inspect(page_path: Path, audio_path: Path, output_dir: Path, *, require_timing_review=False):
    from playwright.sync_api import sync_playwright
    page_path=page_path.resolve();site=page_path.parent
    report=json.loads((site/'report.json').read_text())
    timing_result=None
    output_dir.mkdir(parents=True,exist_ok=True)
    if len(report['songs'])!=3:
        raise AssertionError('Expected all three distinct StemLab song masters')
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(site)))
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        with sync_playwright() as driver:
            browser=driver.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1280,'height':880},device_scale_factor=1)
            errors=[]
            page.on('pageerror',lambda exc:errors.append(str(exc)))
            page.goto(f'http://127.0.0.1:{server.server_port}/{page_path.name}')
            assert page.locator('#song option').count()==3
            assert page.locator('#timeline').is_visible()
            assert page.locator('#skeleton').is_visible()
            assert page.locator('#tempo-detail').is_visible()
            assert page.get_by_text('Motion + music: complete dances and loops').count()==1
            assert page.locator('#motion option').count()==len(report['motions'])
            for index,song in enumerate(report['songs']):
                page.select_option('#song',str(index))
                assert page.locator('#metrics').inner_text().strip()
                assert page.locator('#provenance').inner_text().strip()
                count=page.locator('#candidate option').count()
                assert count==len(song.get('pairs',[])),(song['id'],count)
            # Real CI source evidence includes a weaker explicit 120 BPM
            # double-time interpretation for the 60 BPM synthetic action.
            arc=next(i for i,s in enumerate(report['songs']) if s['id']=='arcadians')
            assert any(p.get('metrical_factor')==2 for p in report['songs'][arc]['pairs']), (
                'Arcadians double-time candidate missing from review gallery')
            page.select_option('#song',str(arc))
            assert page.locator('#candidate option').count()>0
            page.select_option('#candidate','0')
            assert 'interpret' in page.locator('#tempo-detail').inner_text().lower()
            truth=next(i for i,s in enumerate(report['songs']) if s['id']=='the-truth-is-a-virus')
            page.select_option('#song',str(truth))
            # The source is loaded via the protected local picker, never a remote
            # request nor a separate copy in CI upload artifacts.
            page.locator('#audiofile').set_input_files(str(audio_path.resolve()))
            page.get_by_text('Exact master verified locally.',exact=False).wait_for(timeout=30000)
            assert page.locator('#audio').get_attribute('src').startswith('blob:')
            if require_timing_review:
                from stemlab.analysis.motion_alignment import validate_alignment_revision
                entry=next(e for e in report['alignment_reviews']
                           if e['report']['audio_source']['sha256']==report['songs'][truth]['source_sha256'])
                motion=next(m for m in report['motions']
                            if m.get('source_capture_sha256')==entry['report']['motion_source']['sha256'])
                page.select_option('#motion',motion['id'])
                assert page.locator('#timing-candidate option').count()==len(entry['report']['candidates'])
                assert not page.locator('#timing-enable').is_checked()
                assert page.locator('#timing-save').is_enabled()
                page.locator('#timing-enable').check()
                page.locator('#timing-reviewer').fill('Automated UI test — not a musical approval')
                # A small explicit phase edit, constrained to actual source coverage.
                phase=page.evaluate('''entry => {
                  for(const delta of [.01,-.01,0])try{
                    DanceRudimentsTimingReview.shiftedSegments(entry,0,delta);return delta;
                  }catch{}
                  throw Error('No valid phase correction');
                }''',entry)
                page.locator('#timing-offset').fill(str(phase))
                first_audio=entry['report']['candidates'][0]['mapping_segments'][0]['anchors'][0]['audio_seconds']+phase
                page.locator('#timing-beat-one').fill(str(first_audio))
                page.select_option('#timing-meter','4/4')
                with page.expect_download() as saved:
                    page.locator('#timing-save').click()
                revision_path=output_dir/'automated-test-timing-revision.json'
                saved.value.save_as(revision_path)
                revision=json.loads(revision_path.read_text())
                validate_alignment_revision(entry['report'],revision,report_sha256=entry['report_sha256'])
                assert revision['beat_one_audio_seconds']==first_audio
                assert revision['meter']==[4,4]
                assert not revision['loop_seams_verified'] and not revision['retargeting_verified']
                assert page.evaluate('motionPhase(-1)') is None
                timing_result=dict(status='passed',candidate_count=len(entry['report']['candidates']),
                    phase_correction_seconds=phase,source_identity_checked=True,
                    coverage_gap_no_extrapolation=True,revision_validated_by_stemlab=True,
                    review_is_automated_test_only=True)
            page.locator('#silent').click()
            page.wait_for_timeout(550)
            assert page.locator('#silent').inner_text().startswith('■')
            assert not errors,errors
            page.screenshot(path=str(output_dir/'song-loop-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            page.wait_for_timeout(150)
            assert page.locator('#skeleton').is_visible()
            page.screenshot(path=str(output_dir/'song-loop-mobile.png'),full_page=True)
            # The full-length catalogue must remain independently auditionable
            # even when no audio cut passes the candidate pairing gates.
            full=next((x['id'] for x in report['motions']
                       if x.get('motion_kind')=='full_length'),None)
            assert full, 'CI should shortlist one rhythmic complete source Action'
            page.evaluate('DATA.songs.forEach(s=>{s.pairs=[]}); updateSong()')
            assert page.locator('#candidate').is_disabled()
            page.select_option('#motion',full)
            page.locator('#silent').click()
            page.wait_for_timeout(300)
            assert page.locator('#skeleton').is_visible()
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close()
    return dict(status='passed',songs=[s['id'] for s in report['songs']],errors=[],
                timing_review=timing_result,
                screenshots=['song-loop-desktop.png','song-loop-mobile.png'])


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--site',type=Path,required=True)
    ap.add_argument('--truth-audio',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--require-timing-review',action='store_true',
                    help='Exercise supplied exact-source timing evidence and validate the saved test revision')
    a=ap.parse_args(argv)
    status=inspect(a.site/'index.html',a.truth_audio,a.output_dir,
                   require_timing_review=a.require_timing_review)
    (a.output_dir/'browser-report.json').write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps(status,indent=2))

if __name__=='__main__': main()
