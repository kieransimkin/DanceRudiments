"""Exercise the actual shared visualizer and native WASM in Chromium.

Normal mode opens file://. Restricted environments may explicitly use --in-memory;
in that mode copied audio is attached as a Blob containing the exact same bytes.
This is resource hydration, not a replacement renderer, clock or movement engine.
"""
from __future__ import annotations
import argparse
import base64
import json
import math
from pathlib import Path
import re
import sys


def fixture(path):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
    from dancerudiments_authoring.recording import Recording, RecordingClock, write_recording
    from dancerudiments_authoring.harness import build_recording_harness
    (path.parent/'recordings').mkdir(parents=True,exist_ok=True)
    values=[]
    for k,dims in enumerate([2,3,6,8]):
        r=Recording('fixture_'+str(k),tuple('axis_'+str(j) for j in range(dims)),
                    tuple(tuple(.6*math.sin((i+j*7+k)*.1) for j in range(dims)) for i in range(256)),
                    RecordingClock(120,'synthetic renderer fixture',beat_zero_seconds=.25,start_pip=-32),
                    json.dumps({'title':'Synthetic renderer fixture '+str(k),'family':'Test fixture'}))
        write_recording(path.parent/'recordings'/(r.name+'.json'),r)
        values.append(r)
    # A synthetic stereo tone exercises the same HTMLAudioElement clock in CI.
    import struct
    import wave
    audio = path.parent / 'fixture-audio.wav'
    with wave.open(str(audio), 'wb') as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b''.join(struct.pack('<hh', v, v) for v in
                           (int(4000 * math.sin(i * 2 * math.pi * 220 / 16000)) for i in range(32000))))
    build_recording_harness(values,path,audio={'relative_path':audio.name},
                            notices='Synthetic 2-second stereo tone and synthetic movement test fixture.')


def test(path, *, in_memory=False, chromium=None, screenshot=None):
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
    from dancerudiments_authoring.harness_checks import check_display_modes, check_running_view_switch
    text=path.read_text(encoding='utf-8')
    payload=json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>',text,re.S).group(1))
    patterns=payload['pack']['patterns']
    first=payload['clock']['start_pip']
    n=patterns[0]['period_pips']
    last=first+n-1
    expected=[]
    for item in patterns:
        r=json.loads((path.parent/item['recording_path']).read_text())
        expected.append([r['samples'][i] for i in (0,n//2,n-1)])
    errors=[]
    external=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=chromium,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1600,'height':1080},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http://','https://')) else None)
        if in_memory:
            page.set_content(text)
        else:
            page.goto(path.resolve().as_uri())
        page.wait_for_function('window.audition?.ready===true',timeout=30000)
        state=page.evaluate('window.audition.state()')
        assert not state['running'] and state['midi']['bpm']==payload['clock']['bpm']
        assert page.locator('#bpm').is_disabled() and page.locator('#offset').is_disabled()
        actual=page.evaluate('([first,n])=>window.audition.metadata().map((_,i)=>[0,Math.floor(n/2),n-1].map(k=>window.audition.sample(i,first+k)))',[first,n])
        assert actual==expected,'WASM sample differs from authoritative recording JSON'
        assert page.evaluate('(p)=>{try{window.audition.sample(0,p);return false}catch(e){return true}}',first-1)
        names=[x['name'] for x in patterns[:4]]
        page.evaluate('(names)=>window.audition.compare(names)',names)
        chosen=next((i for i,p in enumerate(patterns) if len(p['dimensions'])>3),None)
        if chosen is not None:
            count=len(patterns[chosen]['dimensions'])
            page.evaluate('([i,n])=>window.audition.setProjection(i,[n-1,n-2,-1])',[chosen,count])
            assert page.evaluate('(i)=>window.audition.projection(i)',chosen)==[count-1,count-2,-1]
        midpoint=(first+n//2)/64
        page.evaluate('(b)=>window.audition.setBeat(b)',midpoint)
        page.wait_for_timeout(80)
        audio=payload.get('audio',{})
        audio_checked=False
        if audio.get('relative_path'):
            if in_memory:
                raw=(path.parent/audio['relative_path']).read_bytes()
                page.evaluate('''(text)=>{const raw=atob(text),bytes=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
                    document.getElementById('audio').src=URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));}''',base64.b64encode(raw).decode())
            page.wait_for_function("document.getElementById('audio').readyState>=2",timeout=10000)
            page.evaluate('(b)=>window.audition.setBeat(b)',midpoint)
            expected_time=payload['clock']['beat_zero_seconds']+midpoint*60/payload['clock']['bpm']
            assert abs(page.locator('#audio').evaluate('(a)=>a.currentTime')-expected_time)<.01
            audio_checked=True
        display_report = check_display_modes(page)
        before=page.evaluate('window.audition.state().beat')
        page.locator('#play').click()
        page.wait_for_timeout(200)
        assert page.evaluate('window.audition.state().running')
        assert page.evaluate('window.audition.state().beat')>before
        check_running_view_switch(page)
        page.locator('#play').click()
        page.wait_for_timeout(60)
        assert not page.evaluate('window.audition.state().running')
        name=patterns[0]['name']
        page.evaluate('(name)=>window.audition.setStatus(name,"keep")',name)
        doc=page.evaluate('window.audition.review()')
        assert doc['choices'][0]['status']=='keep'
        with page.expect_download() as downloaded:
            page.locator('#export-choices').click()
        review_file=path.parent/'browser-test-review.json'
        downloaded.value.save_as(review_file)
        assert json.loads(review_file.read_text())==doc
        page.evaluate('(doc)=>window.audition.importReview(doc)',doc)
        page.locator('#search').fill(name)
        assert page.locator('#grid .card').count()==1
        page.locator('#search').fill('')
        page.evaluate('(b)=>window.audition.setBeat(b)',last/64)
        page.locator('#play').click()
        page.wait_for_timeout(180)
        assert not page.evaluate('window.audition.state().running'),'Recording unexpectedly loops'
        assert not errors,errors
        assert not external,external
        page.evaluate('(b)=>window.audition.setBeat(b)',midpoint)
        page.locator('#comparison').scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        if screenshot:
            page.locator('#comparison').screenshot(path=str(screenshot))
            page.select_option('#view-mode', 'bars')
            page.wait_for_timeout(100)
            page.locator('#comparison').screenshot(path=str(Path(screenshot).with_name(Path(screenshot).stem + '-bars.png')))
        browser.close()
    report=dict(candidates=len(patterns),sample_vectors_checked=len(patterns)*3,engine='actual C++/WebAssembly',
                mode='in-memory with exact copied-audio Blob hydration' if in_memory else 'local-file',
                audio_decode_and_clock_verified=audio_checked,auto_play=False,non_looping=True,
                projection=True,review_download=True,external_requests=external,page_errors=errors,
                listening_qa=False,file_loading_verified=not in_memory)
    report.update(display_report)
    path.with_name('browser-test.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html',type=Path)
    parser.add_argument('--make-fixture',action='store_true')
    parser.add_argument('--in-memory',action='store_true')
    parser.add_argument('--chromium')
    parser.add_argument('--screenshot',type=Path)
    args=parser.parse_args()
    if args.make_fixture:
        fixture(args.html)
    test(args.html,in_memory=args.in_memory,chromium=args.chromium,screenshot=args.screenshot)
