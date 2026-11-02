#!/usr/bin/env python3
"""Exercise a generated private collection audition in an isolated browser.

Source evidence, test playback and screenshots do not record human approval.
Only this script's context/browser/server are closed on completion.
"""
import argparse
import json
from pathlib import Path
import threading
from serve_song_loop_preview import create_server


def inspect(directory,output):
    from playwright.sync_api import sync_playwright
    directory,output=Path(directory).resolve(),Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    data=json.loads((directory/'report.json').read_text(encoding='utf-8'))
    server,url=create_server(directory)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    errors=[];checks=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--mute-audio',
                '--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            context=browser.new_context(viewport={'width':1440,'height':1000},
                service_workers='block',record_video_dir=str(output/'video'),record_video_size={'width':1440,'height':1000})
            try:
                page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(url)
                assert page.locator('#source option').count()==len(data['collection_coverage']['actions'])+1
                for i,song in enumerate(data['songs']):
                    page.select_option('#source','');page.select_option('#song',str(i))
                    page.click('#audition')
                    page.wait_for_function("()=>document.querySelector('#mesh-status').textContent.startsWith('Song clock drives')",timeout=60000)
                    frame=page.frame_locator('#mesh-frame')
                    frame.locator('#stage').scroll_into_view_if_needed()
                    child=page.frames[1]
                    sample=lambda:child.evaluate('()=>meshDemo.debugSnapshot()')
                    before=sample()
                    assert before['auditionMotion'] and before['skinnedMeshCount']>0
                    page.wait_for_function('()=>document.querySelector("audio").currentTime > 0 && !document.querySelector("audio").paused')
                    child.wait_for_function('(pip)=>meshDemo.debugSnapshot().currentPip!==pip',arg=before['currentPip'],timeout=15000)
                    after=sample()
                    assert before['physicalSample']!=after['physicalSample']
                    assert before['representativeDeformedVertices']!=after['representativeDeformedVertices']
                    page.screenshot(path=str(output/(song['id']+'.png')))
                    checks.append(dict(song=song['id'],native_pose_changed=True,skin_changed=True,
                        profile=after['auditionMotion']['profileSha256'],sample_count=after['auditionMotion']['sampleCount']))
                # A recording without ranked loops must still offer its source-time motion.
                paired={m['original_source_sha256'] for m in data['motions'] if m.get('loopable')}
                original=next(m for m in data['motions'] if m['motion_kind']=='source_time' and m['original_source_sha256'] not in paired)
                page.select_option('#source',original['original_source_sha256'])
                assert page.locator('#candidate option').count()==0
                page.click('#original-source')
                page.wait_for_function('()=>document.querySelector("#motion").selectedOptions[0].textContent.includes("ORIGINAL SOURCE SPEED")')
                checks.append(dict(original_without_loop=True,source=original['original_source_sha256']))
                unsupported=data.get('mesh_audition',{}).get('unavailable',[])
                if unsupported:
                    page.select_option('#source',unsupported[0]['source_sha256']);page.click('#original-source')
                    page.wait_for_function('()=>document.querySelector("#mesh-frame").hidden')
                    assert 'no declared Kandi calibration' in page.locator('#mesh-status').inner_text()
                    checks.append(dict(unsupported_calibration_stays_unloaded=True))
                page.click('#unload-mesh')
                assert page.locator('#mesh-frame').get_attribute('src') is None
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(output/'mobile.png'))
                assert page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth')
                assert not errors,errors
            finally:
                context.close();browser.close()
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
    receipt=dict(format='dancerudiments.collection-audition-browser.v1',passed=True,
        source_report_sha256=__import__('hashlib').sha256((directory/'report.json').read_bytes()).hexdigest(),
        checks=checks,errors=errors,human_approved=False,browser_closed=True,server_closed=not worker.is_alive())
    (output/'browser-report.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(inspect(args.directory,args.output_dir),indent=2))
