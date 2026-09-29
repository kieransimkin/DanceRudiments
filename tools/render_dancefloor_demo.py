#!/usr/bin/env python3
"""Render and exercise all 68×16 combinations and the four-slot audio comparison UI."""
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
        page=browser.new_page(viewport={'width':1480,'height':1300},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:network.append(r.url) if r.url.startswith(('http:','https:')) else None)
        if in_memory:page.set_content(path.read_text(encoding='utf-8'),wait_until='load',timeout=60000)
        else:page.goto(path.as_uri(),wait_until='load',timeout=60000)
        page.wait_for_function('window.clubDemo?.stats.ready',timeout=60000)
        check(page.evaluate('!clubDemo.playing'),'starts paused')
        check(page.evaluate('clubDemo.audioState==="not-created"'),'no automatic audio context')
        check(page.locator('.motion').count()==4,'four simultaneous motion cards')
        check(page.locator('#rhythm option').count()==68,'68 selectable rhythms')
        check(page.locator('.mapping-select').count()==4,'four independent mapping selectors')
        check(page.locator('.mapping-select').first.locator('option').count()==16,'sixteen mappings per selector')
        result=page.evaluate('''() => {let count=0;for(let i=0;i<clubDemo.patterns.length;i++){
          const p=clubDemo.patterns[i];for(let n=0;n<p.period_pips;n++){
           const got=clubDemo.sample(i,n);for(let a=0;a<3;a++){if(got[a]!==p.samples[n][a])throw new Error('Sample mismatch');count++;}}
          for(const n of [-2147483648,-1,p.period_pips,2147483647]){const j=((n%p.period_pips)+p.period_pips)%p.period_pips;
           const got=clubDemo.sample(i,n);for(let a=0;a<3;a++){if(got[a]!==p.samples[j][a])throw new Error('Wrap mismatch');count++;}}}
          return count;}''')
        check(result>1700000,'every snapshot scalar and extreme-pip sample equals native export')
        coverage=page.evaluate('''() => {let n=0;for(const r of clubDemo.rhythms){clubDemo.select(r.id);
          for(let bank=0;bank<4;bank++){clubDemo.setBank(bank);clubDemo.seek(1.25);
            const names=[...document.querySelectorAll('.name')].map(x=>x.textContent);
            if(!names.every((name,i)=>name==='beat_'+r.id+'_'+clubDemo.mappings[i]))throw new Error('Bad mapping card');
            n+=4;}}return n;}''')
        check(coverage==1088,'all 1088 rhythm/mapping combinations draw in a card')
        for bank in range(4):
            page.click(f'[data-bank="{bank}"]')
            check(page.locator(f'[data-bank="{bank}"]').get_attribute('aria-pressed')=='true',f'mapping bank {bank+1} selects and announces its state')
        page.evaluate('clubDemo.select("jersey_five");clubDemo.setBank(1)')
        page.select_option('.mapping-select[data-slot="0"]','recoil')
        check(page.evaluate('clubDemo.mappings[0]==="recoil"&&clubDemo.mappings[1]==="surge"'),'duplicate selection swaps slots without losing a mapping')
        page.select_option('.mapping-select[data-slot="0"]','spring')
        check(page.evaluate('clubDemo.mappings[0]==="spring"'),'select arbitrary mapping outside current bank')
        invalid=page.evaluate('''() => {let n=0;for(const m of [[],['spring'],['spring','spring','dive','box'],['missing','dive','box','surge']]){
          try{clubDemo.setMappings(m);}catch(e){n++;}}return n;}''')
        check(invalid==4,'invalid mapping selections rejected')
        for projection in ('xy','xz','yz','oblique'):
            page.select_option('#projection',projection)
            check(page.evaluate('clubDemo.stats.errors.length===0'),'renders '+projection+' projection')
        page.evaluate('clubDemo.select("amen_four_bar")');page.click('#amen')
        check(page.evaluate('clubDemo.current==="amen_no_ghosts"'),'Amen A/B retains simplified comparison')
        page.click('#amen');check(page.evaluate('clubDemo.current==="amen_four_bar"'),'Amen A/B returns to full phrase')
        page.select_option('#genre','Jersey club');check(page.locator('#rhythm option').count()==2,'new family filtering')
        page.select_option('#rhythm','jersey_five');page.click('#next');check(page.locator('#seek').input_value()=='1','exact forward pip')
        page.click('#previous');check(page.locator('#seek').input_value()=='0','exact reverse pip')
        page.evaluate('clubDemo.seek(3.75)');check(page.locator('#seek').input_value()=='240','exact fractional-beat seek')
        page.fill('#bpm','150');page.locator('#bpm').dispatch_event('change');check(page.evaluate('clubDemo.bpm===150'),'tempo change')
        page.click('#native-tempo');check(page.evaluate('clubDemo.bpm===142'),'suggested tempo reset')
        page.click('#reset');page.click('#play');page.wait_for_timeout(950)
        check(page.evaluate('clubDemo.playing&&clubDemo.beat>1'),'play advances musical clock')
        check(page.evaluate('clubDemo.stats.audioUnlocked&&clubDemo.stats.scheduledEvents>4&&clubDemo.stats.voices>4'),'actual Web Audio oscillator/noise scheduling')
        before=page.evaluate('clubDemo.beat');page.click('[data-bank="2"]')
        check(page.evaluate('clubDemo.playing&&clubDemo.beat')>=before,'mapping bank change keeps clock running')
        page.click('#play');b=page.evaluate('clubDemo.beat');page.wait_for_timeout(150)
        check(page.evaluate('clubDemo.beat')==b,'pause freezes transport')
        check(page.evaluate('clubDemo.activeVoices===0'),'pause disposes active voices')
        page.uncheck('#sound');events=page.evaluate('clubDemo.stats.scheduledEvents');page.click('#play');page.wait_for_timeout(350)
        check(page.evaluate('clubDemo.stats.scheduledEvents')==events,'mute stops sound scheduling but keeps motion')
        page.click('#play');page.fill('#bpm','999');page.locator('#bpm').dispatch_event('change')
        check(page.evaluate('clubDemo.bpm===142'),'invalid tempo rejected')
        page.click('#play');page.emulate_media(reduced_motion='reduce');page.wait_for_timeout(80)
        check(page.evaluate('!clubDemo.playing'),'reduced-motion change pauses active transport')
        page.emulate_media(reduced_motion='no-preference')
        page.evaluate('clubDemo.select("jersey_five");clubDemo.setBank(2);clubDemo.seek(2.75)')
        desktop=path.with_suffix('.png');page.screenshot(path=str(desktop),full_page=True)
        page.set_viewport_size({'width':430,'height':932});page.evaluate('clubDemo.select("amen_four_bar");clubDemo.setBank(3);clubDemo.seek(11.5)');page.wait_for_timeout(100)
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'mobile has no page-wide horizontal overflow')
        mobile=path.with_name(path.stem+'-mobile.png');page.screenshot(path=str(mobile),full_page=True)
        check(not network,'no external network requests')
        check(not errors and page.evaluate('clubDemo.stats.errors.length===0'),'no browser/application exceptions')
        browser.close()
    report=dict(check_count=len(checks),checks=checks,scalar_matches=result,combination_draws=coverage,
        browser_errors=errors,external_requests=network,load_mode='set_content' if in_memory else 'file_navigation',
        scope='Chromium, actual C++ snapshot WASM, Web Audio scheduling and DOM/canvas interaction; not production Embind or subjective listening')
    report_path=path.with_suffix('.validation.json');report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    files=[path,path.with_suffix('.manifest.json'),desktop,mobile,report_path];archive=path.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(f,f.name)
    files.append(archive)
    path.with_suffix('.sha256').write_text(''.join(sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in files),encoding='ascii')
    print(f'{len(checks)} browser checks; {coverage} combinations; {result} exact scalar comparisons ({report["load_mode"]})')
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('html',type=Path);ap.add_argument('--in-memory',action='store_true');ap.add_argument('--browser-executable')
    a=ap.parse_args();render(a.html,a.in_memory,a.browser_executable)
