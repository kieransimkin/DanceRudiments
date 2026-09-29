#!/usr/bin/env python3
"""Render actual release HTML; verify every WASM sample and seal versioned assets."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile
from playwright.sync_api import sync_playwright

def render(path,chromium=None,in_memory=False):
    path=Path(path).resolve();manifest=json.loads(path.with_suffix('.json').read_text());checks=[]
    def check(value,label):
        if not value:raise AssertionError(label)
        checks.append(label)
    check(sha256(path.read_bytes()).hexdigest()==manifest['html_sha256'],'HTML integrity')
    with sync_playwright() as p:
        opts=dict(headless=True,args=['--no-sandbox','--mute-audio'])
        if chromium:opts['executable_path']=chromium
        browser=p.chromium.launch(**opts);page=browser.new_page(viewport=dict(width=1440,height=1050),reduced_motion='reduce')
        errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def deny(route):requests.append(route.request.url);route.abort()
        page.route(re.compile('^https?://'),deny)
        if in_memory:page.set_content(path.read_text(encoding='utf-8'))
        else:page.goto(path.as_uri())
        page.wait_for_function('window.audition && audition.ready',timeout=30000)
        check(page.locator('#grid .card').count()==manifest['pattern_count'],'All catalogue entries render')
        check(not page.evaluate('audition.state().running'),'Starts paused')
        check(page.locator('#export-pack').is_hidden(),'Snapshot export is not misrepresented as an editable pack')
        comparisons=page.evaluate('''() => {
          const data=JSON.parse(document.getElementById('data').textContent);let count=0;
          data.pack.patterns.forEach((p,i)=>{
            for(let pip=-p.period_pips;pip<p.period_pips;pip++) {
              const a=audition.sample(i,pip),b=p.samples[((pip%p.period_pips)+p.period_pips)%p.period_pips];
              if(a.some((v,j)=>v!==b[j]))throw Error('Sample mismatch '+p.name+' '+pip);count+=3;
            }
            for(const pip of [-2147483648,2147483647]) {
              const a=audition.sample(i,pip),b=p.samples[((pip%p.period_pips)+p.period_pips)%p.period_pips];
              if(a.some((v,j)=>v!==b[j]))throw Error('Extreme pip mismatch '+p.name);count+=3;
            }
          });return count;
        }''')
        check(comparisons>0,'Exact native-snapshot/WASM sample equality')
        page.evaluate('audition.setBeat(11.25)');check(page.evaluate('audition.state().beat')==11.25,'Seeking beyond eight beats')
        page.locator('#play').click();page.wait_for_timeout(150);check(page.evaluate('audition.state().beat')>11.25,'Playback advances')
        page.locator('#play').click();frozen=page.evaluate('audition.state().beat');page.wait_for_timeout(80)
        check(page.evaluate('audition.state().beat')==frozen,'Pause freezes')
        collection_values=page.locator('#collection option').evaluate_all('(options)=>options.slice(1).map(o=>o.value)')
        for collection in collection_values:
            page.locator('#collection').select_option(collection)
            expected=page.evaluate('(id)=>JSON.parse(document.getElementById("data").textContent).pack.patterns.filter(p=>(p.provenance.collection_id||"core")===id).length',collection)
            check(page.locator('#grid .card').count()==expected,'Collection filter '+collection)
        page.locator('#collection').select_option('')
        page.wait_for_timeout(100)
        counts=page.evaluate('audition.state()')
        if manifest['pattern_count']>32:
            check(0<counts['renderedLastFrame']<counts['plotCount'],'Only near-viewport canvases are animated')
            page.locator('#grid .card').last.scroll_into_view_if_needed()
            page.wait_for_timeout(150)
            check(page.locator('#grid .card').first.locator('canvas').first.evaluate('(c)=>c.width')==1,'Offscreen canvas backing store is released')
            check(page.locator('#grid .card').last.locator('canvas').first.evaluate('(c)=>c.width')>1,'Scrolled-to card draws from current native phase')
            page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(100)
        families=page.locator('#family option').all_text_contents()[1:]
        for family in families:
            page.locator('#family').select_option(family);check(page.locator('#grid .card').count()>0,'Filter '+family)
        page.locator('#family').select_option('')
        page.evaluate('(ids)=>audition.compare(ids)',manifest['names'][:4]);check(page.locator('#compare-grid .card').count()==min(4,manifest['pattern_count']),'Comparison')
        page.evaluate('audition.setBeat(1.5)');page.wait_for_timeout(60)
        check(not requests,'No external asset requests');check(not errors,'No browser exceptions')
        desktop=path.with_suffix('.png');page.screenshot(path=str(desktop))
        page.set_viewport_size(dict(width=390,height=844));page.wait_for_timeout(80)
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'Mobile fits viewport')
        mobile=path.with_name(path.stem+'-mobile.png');page.screenshot(path=str(mobile));browser.close()
    manifest.update(browser_checks=checks,component_comparisons=comparisons,load_mode='in-memory' if in_memory else 'file')
    meta=path.with_suffix('.json');meta.write_text(json.dumps(manifest,indent=2)+'\n')
    files=[path,desktop,mobile,meta];archive=path.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.name)
    files.append(archive)
    path.with_suffix('.sha256').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
    print(f'{len(checks)} browser checks; {comparisons} exact component comparisons');return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('html',type=Path);p.add_argument('--chromium');p.add_argument('--in-memory',action='store_true')
    a=p.parse_args();render(a.html,a.chromium,a.in_memory)
