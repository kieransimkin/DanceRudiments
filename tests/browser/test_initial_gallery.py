"""Real-browser audition smoke tests (requires playwright + Chromium).

The HTML is injected into an isolated document, requiring no network navigation.
This explicitly exercises the no-storage fallback; it does not claim to test
persistent file:// localStorage or a browser's local-file navigation policy.
"""
import argparse
import io
import json
from pathlib import Path
import shutil
import tempfile
import wave

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]


def run(chromium=None, screenshot_dir=None):
    checks=[]
    def check(condition,name):
        if not condition: raise AssertionError(name)
        checks.append(name)
    with sync_playwright() as pw:
        options=dict(headless=True,args=['--no-sandbox','--mute-audio'])
        if chromium: options['executable_path']=chromium
        browser=pw.chromium.launch(**options)
        page=browser.new_page(viewport=dict(width=1440,height=1100),device_scale_factor=1)
        errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda request:requests.append(request.url))
        page.set_content((ROOT/'harness/initial-collection.html').read_text(encoding='utf-8'))
        page.wait_for_function('window.audition && audition.ready')
        check(page.locator('#grid .card').count()==28,'28 real rendered candidates')
        check(not page.evaluate('audition.state().running'),'Starts paused')
        check(page.locator('#export-pack').is_disabled(),'Empty selection cannot export pack')
        page.locator('#play').click();page.wait_for_timeout(200)
        check(page.evaluate('audition.state().beat')>0,'Play advances the shared native clock')
        page.locator('#play').click();beat=page.evaluate('audition.state().beat');page.wait_for_timeout(100)
        check(page.evaluate('audition.state().beat')==beat,'Pause freezes phase')
        page.evaluate('audition.setBeat(0)');page.locator('#back').click()
        check(page.evaluate('audition.state().beat')==-1/64,'Negative pip stepping')
        page.locator('#forward').click()
        check(page.evaluate('audition.state().beat')==0,'Positive pip stepping')
        page.locator('#grid [data-name=lfo_breathe] .keep').click()
        page.locator('#grid [data-name=akwf_round_saw] .maybe').click()
        page.locator('#grid [data-name=lfo_surge] .skip').click()
        page.locator('#grid [data-name=lfo_breathe] .note').fill('Gentle baseline; keep for low-energy sections.')
        review=page.evaluate('audition.review()')
        check(sum(c['status']=='keep' for c in review['choices'])==1,'Keep / Maybe / Skip review updates')
        check(not page.locator('#export-pack').is_disabled(),'Kept selection enables export')
        with page.expect_download() as download:
            page.locator('#export-pack').click()
        saved=download.value.path();pack=json.loads(Path(saved).read_text())
        check([p['name'] for p in pack['patterns']]==['lfo_breathe'],'Actual compiled-pack download contains only kept patterns')
        check(pack['patterns'][0]['provenance']['license']=='MIT','Downloaded pack retains provenance')
        with page.expect_download() as download:
            page.locator('#export-score').click()
        scores=json.loads(Path(download.value.path()).read_text())
        check(scores['format']=='dancerudiments.score-pack' and len(scores['patterns'])==1,'Actual authoring-score download')
        with page.expect_download() as download:
            page.locator('#export-choices').click()
        exported=json.loads(Path(download.value.path()).read_text())
        check(exported==review,'Review download preserves notes and exact revision')
        bad=json.loads(json.dumps(review));bad['choices'][0]['source_sha256']='0'*64
        try:
            page.evaluate('(doc)=>audition.importReview(doc)',bad)
            raise AssertionError('Bad review accepted')
        except Exception as exc:
            if isinstance(exc,AssertionError): raise
        check(page.evaluate('audition.review()')==review,'Invalid import is rejected atomically')
        page.locator('#import-choices').set_input_files(dict(name='review.json',mimeType='application/json',buffer=json.dumps(review).encode()))
        page.wait_for_function("document.getElementById('status').textContent.includes('Review imported')")
        check(page.evaluate('audition.review()')==review,'Valid review import round trip')
        page.locator('#family').select_option('AKWF')
        check(page.locator('#grid .card').count()==4,'Family filter')
        page.locator('#family').select_option('')
        page.locator('#review').select_option('keep')
        check(page.locator('#grid .card').count()==1,'Review filter')
        page.locator('#review').select_option('')
        page.locator('#search').fill('multiple lobes')
        check(page.locator('#grid .card').count()==1,'Text search')
        page.locator('#search').fill('')
        page.evaluate("audition.compare(['groove_a_played','groove_a_grid','akwf_round_saw','lfo_flower'])")
        check(page.locator('#compare-grid .card').count()==4,'Four-way shared-clock comparison')
        page.locator('#grid [data-name=lfo_breathe] input[type=checkbox]').click()
        check(page.locator('#compare-grid .card').count()==4,'Fifth comparison is refused')
        page.locator('#clear-compare').click()
        page.locator('#grid [data-name=groove_a_played] .source-button').click()
        check('CC-BY-4.0' in page.locator('#detail-body').inner_text() and 'source_blob_sha1' in page.locator('#detail-body').inner_text(),'Source and licence inspector')
        page.locator('#close-details').click()
        # A real local WAV tests object-URL decoding and audio-clock seeking.
        page.locator('summary').click()
        payload=io.BytesIO()
        with wave.open(payload,'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000);wav.writeframes(b'\0\0'*8000*8)
        page.locator('#audio-file').set_input_files(dict(name='test.wav',mimeType='audio/wav',buffer=payload.getvalue()))
        page.wait_for_function('Number.isFinite(document.getElementById("audio").duration)')
        page.locator('#offset').fill('0.5');page.locator('#offset').dispatch_event('change')
        page.evaluate("document.getElementById('audio').currentTime=2.5")
        page.wait_for_function('Math.abs(audition.state().beat-4)<0.01')
        check(abs(page.evaluate('audition.state().beat')-4)<.01,'Local audio clock uses manual beat-zero offset')
        page.locator('#play').click();page.wait_for_timeout(150)
        check(page.evaluate('audition.state().running'),'Local audio Play uses the shared transport')
        page.locator('#play').click()
        page.locator('#clear-audio').click()
        check(page.evaluate("document.getElementById('audio').getAttribute('src')===null"),'Local audio can be removed')
        page.emulate_media(reduced_motion='reduce');page.wait_for_timeout(40)
        check(not page.evaluate('audition.state().running'),'Reduced-motion change pauses playback')
        page.evaluate('audition.setBeat(0.375)')
        page.evaluate('scrollTo(0,0)')
        if screenshot_dir:
            out=Path(screenshot_dir);out.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(out/'desktop.png'))
        page.set_viewport_size(dict(width=390,height=844));page.wait_for_timeout(40)
        check(not page.evaluate('document.documentElement.scrollWidth>innerWidth'),'390px mobile has no horizontal overflow')
        if screenshot_dir:page.screenshot(path=str(out/'mobile.png'))
        check(not errors,'No uncaught browser errors')
        check(not any(url.startswith(('https://','http://')) for url in requests),'No network requests')
        browser.close()
    print(json.dumps(dict(checks_passed=len(checks),checks=checks),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium',default=None)
    parser.add_argument('--screenshots')
    args=parser.parse_args();run(args.chromium,args.screenshots)
