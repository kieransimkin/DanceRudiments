#!/usr/bin/env python3
"""Exercise the offline audio/motion demo, render desktop/mobile, package checked assets."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import zipfile
from playwright.sync_api import sync_playwright

def render(path,in_memory=False,browser_executable=None):
    path=Path(path).resolve();checks=[];errors=[];network=[]
    def check(condition,message):
        if not condition:raise AssertionError(message)
        checks.append(message)
    with sync_playwright() as p:
        args=dict(headless=True,args=['--no-sandbox'])
        if browser_executable:args['executable_path']=browser_executable
        browser=p.chromium.launch(**args)
        page=browser.new_page(viewport={'width':1480,'height':1400},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:network.append(r.url) if r.url.startswith(('http:','https:')) else None)
        if in_memory:page.set_content(path.read_text(encoding='utf-8'),wait_until='load')
        else:page.goto(path.as_uri(),wait_until='load')
        page.wait_for_function('window.clubDemo?.stats.ready',timeout=30000)
        check(page.evaluate('!clubDemo.playing'),'starts paused')
        check(page.evaluate('clubDemo.audioState==="not-created"'),'does not create audio until user action')
        check(page.locator('.motion').count()==4,'four simultaneous motion cards')
        check(page.locator('#rhythm option').count()==36,'36 selectable rhythm studies')
        result=page.evaluate('''() => {let count=0;for(let i=0;i<clubDemo.patterns.length;i++){
          const p=clubDemo.patterns[i];for(let n=0;n<p.period_pips;n++){
           const got=clubDemo.sample(i,n);for(let a=0;a<3;a++){if(got[a]!==p.samples[n][a])throw new Error('Sample mismatch');count++;}}
          for(const n of [-2147483648,-1,p.period_pips,2147483647]){const j=((n%p.period_pips)+p.period_pips)%p.period_pips;
           const got=clubDemo.sample(i,n);for(let a=0;a<3;a++){if(got[a]!==p.samples[j][a])throw new Error('Wrap mismatch');count++;}}}
          return count;}''')
        check(result>200000,'all C++ snapshot samples and extreme-pip samples match native export')
        for rid in page.evaluate('clubDemo.rhythms.map(r=>r.id)'):
            page.evaluate('(id)=>clubDemo.select(id)',rid)
            check(page.evaluate('clubDemo.stats.errors.length===0') and page.locator('.name').first.inner_text().startswith('beat_'+rid+'_'),'render '+rid)
        page.evaluate('clubDemo.select("amen_four_bar")');page.click('#amen')
        check(page.evaluate('clubDemo.current==="amen_no_ghosts"'),'Amen A/B selects stripped comparison')
        page.click('#amen');check(page.evaluate('clubDemo.current==="amen_four_bar"'),'Amen A/B returns to full four-bar study')
        page.select_option('#genre','UK garage');check(page.locator('#rhythm option').count()==4,'UK garage family filtering')
        page.select_option('#rhythm','ukg_two_step');page.click('#next');check(page.locator('#seek').input_value()=='1','exact pip stepping')
        page.click('#previous');check(page.locator('#seek').input_value()=='0','reverse pip stepping')
        page.evaluate('clubDemo.seek(3.75)');check(page.locator('#seek').input_value()=='240','seek to exact subdivision')
        page.fill('#bpm','150');page.locator('#bpm').dispatch_event('change');check(page.evaluate('clubDemo.bpm===150'),'tempo control updates musical clock')
        page.click('#native-tempo');check(page.evaluate('clubDemo.bpm===132'),'study tempo reset')
        page.click('#reset');page.click('#play');page.wait_for_timeout(950)
        check(page.evaluate('clubDemo.playing&&clubDemo.beat>1'),'transport advances')
        check(page.evaluate('clubDemo.stats.audioUnlocked&&clubDemo.stats.scheduledEvents>4&&clubDemo.stats.voices>4'),'user-activated Web Audio schedules real oscillator/noise voices')
        page.click('#play');b=page.evaluate('clubDemo.beat');page.wait_for_timeout(100);check(page.evaluate('clubDemo.beat')==b,'pause freezes the musical position')
        page.uncheck('#sound');events=page.evaluate('clubDemo.stats.scheduledEvents');page.click('#play');page.wait_for_timeout(400)
        check(page.evaluate('clubDemo.stats.scheduledEvents')==events,'mute preserves movement without scheduling sound')
        page.click('#play');page.fill('#bpm','999');page.locator('#bpm').dispatch_event('change');check(page.evaluate('clubDemo.bpm===132'),'invalid tempo rejected')
        page.emulate_media(reduced_motion='reduce');check(page.evaluate('!clubDemo.playing'),'reduced-motion change pauses transport')
        page.evaluate('clubDemo.select("amen_four_bar");clubDemo.seek(11.5)')
        desktop=path.with_suffix('.png');page.screenshot(path=str(desktop),full_page=True)
        page.set_viewport_size({'width':430,'height':932});page.evaluate('clubDemo.select("drill_displaced");clubDemo.seek(7)');page.wait_for_timeout(80)
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'mobile has no page-wide horizontal overflow')
        mobile=path.with_name(path.stem+'-mobile.png');page.screenshot(path=str(mobile),full_page=True)
        check(not network,'no external network requests')
        check(not errors and page.evaluate('clubDemo.stats.errors.length===0'),'no browser or application exceptions')
        browser.close()
    report=dict(check_count=len(checks),checks=checks,scalar_matches=result,browser_errors=errors,external_requests=network,
                load_mode='set_content' if in_memory else 'file_navigation',scope='Chromium, native C++ snapshot WASM and Web Audio scheduling; not production Embind or subjective listening')
    report_path=path.with_suffix('.validation.json');report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    files=[path,path.with_suffix('.manifest.json'),desktop,mobile,report_path]
    archive=path.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(f,f.name)
    files.append(archive)
    path.with_suffix('.sha256').write_text(''.join(sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in files),encoding='ascii')
    print(f'{len(checks)} browser checks and {result} exact scalar comparisons passed ({report["load_mode"]})')
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('html',type=Path);ap.add_argument('--in-memory',action='store_true');ap.add_argument('--browser-executable')
    a=ap.parse_args();render(a.html,a.in_memory,a.browser_executable)
