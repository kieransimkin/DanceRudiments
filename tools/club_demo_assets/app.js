(async function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const data = JSON.parse($('payload').textContent);
  const rational = value => { const q=String(value).split('/').map(Number); return q.length===2?q[0]/q[1]:q[0]; };
  const wrap = (x,n) => ((x%n)+n)%n;
  const colours = ['#79e5c7','#ffb780','#beafff'];
  const laneOrder=['kick','snare','clap','hat','open_hat','ride','pedal_hat','rim','tom','shaker','bass','crash'];
  const laneColour = lane => ['kick','bass'].includes(lane)?colours[lane==='kick'?0:2]:['snare','clap','rim'].includes(lane)?colours[1]:'#e8d28a';
  const patterns = data.patterns;
  const indices = new Map(patterns.map((p,i)=>[p.name,i]));
  const byRhythm = new Map(data.rhythms.map(r=>[r.id,r]));
  const cards = [...document.querySelectorAll('[data-map]')];
  let wasm, rhythm, currentPatterns=[], period=16, bpm=136, position=0, playing=false, epoch=0;
  let audio=null, master=null, noise=null, scheduledUntil=0, busy=false;
  const active=new Set();
  const stats={drawFrames:0,scheduledEvents:0,voices:0,ready:false,errors:[],audioUnlocked:false};
  const clock=()=>audio?audio.currentTime:performance.now()/1000;
  const beat=()=>playing?position+Math.max(0,clock()-epoch)*bpm/60:position;
  function report(error){stats.errors.push(String(error));$('error').textContent=String(error);$('error').hidden=false;}
  function sample(index,pip){
    if(!Number.isInteger(index)||index<0||index>=patterns.length||!Number.isInteger(pip)||pip< -2147483648||pip>2147483647)throw new RangeError('Invalid sample request');
    return [0,1,2].map(axis=>wasm.sample_component(index,pip,axis));
  }
  function fit(canvas,height){
    const width=Math.max(10,canvas.getBoundingClientRect().width), dpr=Math.min(devicePixelRatio||1,2);
    if(canvas.width!==Math.round(width*dpr)||canvas.height!==Math.round(height*dpr)){
      canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);
    }
    const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);
    return [ctx,width,height];
  }
  function strokePath(ctx,points,colour,width=1){
    ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.strokeStyle=colour;ctx.lineWidth=width;ctx.stroke();
  }
  function drawCards(pip){
    const amplitude=Number($('amplitude').value);
    cards.forEach((card,j)=>{
      const p=currentPatterns[j], index=indices.get(p.name), xyz=sample(index,pip);
      const canvas=card.querySelector('.motion');const height=canvas.getBoundingClientRect().height;
      const [ctx,w,h]=fit(canvas,height), scale=Math.min(w,h)*.50*amplitude;
      const project=([x,y,z])=>[w/2+(x+.38*z)*scale,h/2+(y-.30*z)*scale];
      ctx.strokeStyle='#243344';ctx.lineWidth=1;
      for(let t=-1;t<=1;t+=.5){const xx=w/2+t*scale,yy=h/2+t*scale;strokePath(ctx,[[xx,14],[xx,h-14]],'#243344');strokePath(ctx,[[12,yy],[w-12,yy]],'#243344');}
      const all=p.samples.map(project);strokePath(ctx,[...all,all[0]],'#3c5366',1.1);
      const tail=[];for(let k=24;k>=0;k--)tail.push(project(sample(index,wrap(pip-k,p.period_pips))));
      strokePath(ctx,tail,colours[j%3],2);
      const [x,y]=project(xyz);ctx.beginPath();ctx.arc(x,y,7.5,0,2*Math.PI);ctx.fillStyle=colours[j%3];ctx.fill();
      ctx.beginPath();ctx.arc(x,y,12,0,2*Math.PI);ctx.strokeStyle=colours[j%3]+'66';ctx.stroke();
      const scope=card.querySelector('.scope');const [sc,sw,sh]=fit(scope,scope.getBoundingClientRect().height);
      for(let axis=0;axis<3;axis++){
        const points=p.samples.map((v,i)=>[i/p.period_pips*sw,sh/2-v[axis]*(sh*.41)]);
        strokePath(sc,points,colours[axis],axis===2?.9:1.2);
      }
      strokePath(sc,[[pip/p.period_pips*sw,3],[pip/p.period_pips*sw,sh-3]],'#eef4f7',1);
      sc.font='9px system-ui';['X','Y','Z'].forEach((v,i)=>{sc.fillStyle=colours[i];sc.fillText(v,7+i*16,12);});
      card.querySelector('.values').textContent=xyz.map((v,i)=>'XYZ'[i]+' '+v.toFixed(3)).join('  ');
    });
  }
  function drawScore(pip){
    const lanes=laneOrder.filter(l=>rhythm.events.some(e=>e.lane===l));
    const height=35+lanes.length*24;const canvas=$('score');canvas.style.height=height+'px';
    const [ctx,w,h]=fit(canvas,height), left=77,right=w-10, width=right-left;
    ctx.font='10px ui-monospace, monospace';
    for(let t=0;t<=period*4;t++){
      const x=left+t/(period*4)*width;strokePath(ctx,[[x,22],[x,h-1]],t%16===0?'#5a6b7d':t%4===0?'#3b4b5e':'#233242',t%16===0?1.4:1);
      if(t%4===0&&t<period*4){ctx.fillStyle=t%16===0?'#79e5c7':'#9aacbd';ctx.fillText(`${Math.floor(t/16)+1}.${(t/4)%4+1}`,x+2,13);}
    }
    lanes.forEach((lane,i)=>{
      const y=37+i*24;ctx.fillStyle='#bac7d4';ctx.fillText(lane.replace('_',' '),1,y+3);
      strokePath(ctx,[[left,y+10],[right,y+10]],'#233242');
      for(const e of rhythm.events.filter(e=>e.lane===lane)){
        const x=left+rational(e.beat)/period*width;
        ctx.globalAlpha=.3+.7*e.velocity;ctx.fillStyle=laneColour(lane);
        ctx.beginPath();ctx.arc(x,y,2+3*e.velocity,0,2*Math.PI);ctx.fill();ctx.globalAlpha=1;
      }
    });
    const x=left+pip/(period*64)*width;strokePath(ctx,[[x,20],[x,h]],'#eef4f7',1.5);
    const viewport=canvas.parentElement;
    if(playing && w>viewport.clientWidth && (x<viewport.scrollLeft+left || x>viewport.scrollLeft+viewport.clientWidth-20))
      viewport.scrollLeft=Math.max(0,x-viewport.clientWidth*.65);
  }
  function redraw(){
    if(!stats.ready||!rhythm)return;
    const pip=Math.floor(wrap(beat(),period)*64)%Math.round(period*64);
    $('seek').value=String(pip);$('pip').textContent=`${pip} / ${period*64}`;
    $('counter').textContent=`${Math.floor(pip/256)+1} · ${Math.floor(pip/64)%4+1} · ${String(pip%64).padStart(2,'0')}`;
    drawCards(pip);drawScore(pip);stats.drawFrames++;
  }
  function frame(){if(playing)redraw();requestAnimationFrame(frame);}
  function makeNoise(){
    noise=audio.createBuffer(1,audio.sampleRate*.6,audio.sampleRate);const out=noise.getChannelData(0);let seed=51673;
    for(let i=0;i<out.length;i++){seed=(1664525*seed+1013904223)>>>0;out[i]=(seed/4294967296)*2-1;}
  }
  async function unlockAudio(){
    if(!audio){
      const Constructor=window.AudioContext||window.webkitAudioContext;
      if(!Constructor)throw new Error('Web Audio is unavailable; disable Drums on for silent playback.');
      audio=new Constructor();master=audio.createGain();master.gain.value=0;
      const limiter=audio.createDynamicsCompressor();limiter.threshold.value=-12;limiter.knee.value=12;limiter.ratio.value=6;
      master.connect(limiter);limiter.connect(audio.destination);makeNoise();
      audio.addEventListener('statechange',()=>{if(playing&&audio.state!=='running')pause();});
    }
    await audio.resume();stats.audioUnlocked=audio.state==='running';
    master.gain.setValueAtTime($('sound').checked?Number($('volume').value):0,audio.currentTime);
  }
  function voice(e,time){
    const lane=e.lane,v=e.velocity;
    function tracked(source,gain,nodes,end){
      active.add(source);stats.voices++;
      source.onended=()=>{active.delete(source);source.disconnect();gain.disconnect();nodes.forEach(n=>n.disconnect());};
      source.start(time);source.stop(end);
    }
    function tone(frequency,duration,level,to=frequency,type='sine'){
      const osc=audio.createOscillator(), g=audio.createGain();osc.type=type;
      osc.frequency.setValueAtTime(frequency,time);osc.frequency.exponentialRampToValueAtTime(Math.max(1,to),time+duration*.8);
      g.gain.setValueAtTime(0,time);g.gain.linearRampToValueAtTime(level*v,time+.002);g.gain.exponentialRampToValueAtTime(.0001,time+duration);
      osc.connect(g);g.connect(master);tracked(osc,g,[],time+duration+.008);
    }
    function hiss(duration,level,frequency,type='highpass'){
      const src=audio.createBufferSource(),filter=audio.createBiquadFilter(),g=audio.createGain();src.buffer=noise;filter.type=type;filter.frequency.value=frequency;filter.Q.value=.7;
      g.gain.setValueAtTime(0,time);g.gain.linearRampToValueAtTime(level*v,time+.001);g.gain.exponentialRampToValueAtTime(.0001,time+duration);
      src.connect(filter);filter.connect(g);g.connect(master);tracked(src,g,[filter],time+duration+.008);
    }
    if(lane==='kick')tone(145,.24,.85,45);
    else if(lane==='snare'){tone(180,.105,.18,120,'triangle');hiss(.14,.55,1600,'highpass');}
    else if(lane==='clap'){hiss(.12,.5,1250,'bandpass');}
    else if(lane==='hat'||lane==='shaker'||lane==='pedal_hat')hiss(lane==='shaker'?.075:.042,lane==='hat'?.24:.15,6500);
    else if(lane==='open_hat')hiss(.19,.26,5700);
    else if(lane==='ride'||lane==='crash'){hiss(lane==='ride'?.15:.4,.19,5000);tone(2900,.12,.04,2650,'triangle');}
    else if(lane==='rim')tone(980,.045,.25,650,'triangle');
    else if(lane==='tom')tone(190,.18,.43,83);
    else if(lane==='bass'){const hz=440*Math.pow(2,((e.note||36)-69)/12);tone(hz*1.18,.28,.47,hz,'triangle');}
  }
  function stopVoices(){for(const src of [...active]){try{src.stop();}catch(_){} }active.clear();}
  function schedule(){
    if(!playing||!audio||audio.state!=='running')return;
    const now=beat(), horizon=now+.12*bpm/60;
    const from=Math.max(scheduledUntil,now-.012*bpm/60);
    if($('sound').checked){
      for(let cycle=Math.floor(from/period);cycle<=Math.floor(horizon/period);cycle++){
        for(const e of rhythm.events){
          const at=cycle*period+rational(e.beat);
          if(at>=from-1e-9&&at<horizon-1e-9){
            const t=epoch+(at-position)*60/bpm;
            if(t>=audio.currentTime-.012){voice(e,Math.max(t,audio.currentTime));stats.scheduledEvents++;}
          }
        }
      }
    }
    scheduledUntil=horizon;
  }
  async function play(){
    if(playing||busy)return;busy=true;
    try{
      if(audio||$('sound').checked)await unlockAudio();
      position=wrap(position,period);epoch=clock()+.045;scheduledUntil=position;playing=true;
      $('play').textContent='Pause';$('play').setAttribute('aria-pressed','true');
      $('status').textContent=$('sound').checked?'Synthesised drum study • adjust volume gently • visual motion is sampled at integer pips.':'Silent audition • the beat clock and all four C++ animations stay synchronised.';
      schedule();
    }catch(e){report(e);}finally{busy=false;}
  }
  function pause(){
    if(playing)position=wrap(beat(),period);playing=false;stopVoices();
    $('play').textContent='Play';$('play').setAttribute('aria-pressed','false');redraw();
  }
  function seek(value){const resume=playing;pause();position=wrap(value,period);redraw();if(resume)play();}
  function selectRhythm(id){
    pause();rhythm=byRhythm.get(id);if(!rhythm)throw new Error('Unknown rhythm');
    period=rational(rhythm.period_beats);position=0;bpm=rhythm.bpm;$('bpm').value=String(bpm);
    $('rhythm').value=id;currentPatterns=data.mappings.map(m=>patterns[indices.get('beat_'+id+'_'+m)]);
    cards.forEach((card,j)=>{card.querySelector('.name').textContent=currentPatterns[j].name;});
    $('rhythm-title').textContent=rhythm.title;
    $('rhythm-meta').textContent=`${rhythm.bars} bar${rhythm.bars===1?'':'s'} · ${period} quarter-note beats · ${rhythm.bpm} BPM suggestion · ${rhythm.swing_ratio==='1/2'?'straight grid':'swung '+rhythm.swing_ratio+' of each eighth-note pair'}`;
    $('rhythm-note').textContent=rhythm.notes||'An original genre study. The same event score drives all four movement interpretations.';
    $('seek').max=String(period*64-1);
    $('references').replaceChildren();
    for(const id of rhythm.reference_ids){
      const source=data.sources[id],li=document.createElement('li'),a=document.createElement('a');
      a.textContent=source.publisher+' — '+source.title;a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';li.append(a);
      li.append(document.createTextNode(' · '+source.supports));$('references').append(li);
    }
    redraw();
  }
  function populate(genre='all', preferred){
    const options=data.rhythms.filter(r=>genre==='all'||r.genre===genre);$('rhythm').replaceChildren();
    for(const r of options){const o=document.createElement('option');o.value=r.id;o.textContent=r.title;$('rhythm').append(o);}
    selectRhythm(options.some(r=>r.id===preferred)?preferred:options[0].id);
  }
  try{
    const binary=Uint8Array.from(atob(data.wasm),c=>c.charCodeAt(0));
    wasm=(await WebAssembly.instantiate(binary,{})).instance.exports;
    if(wasm.pattern_count()!==patterns.length)throw new Error('Native sampler/catalogue mismatch');
    for(const genre of [...new Set(data.rhythms.map(r=>r.genre))]){const o=document.createElement('option');o.value=genre;o.textContent=genre;$('genre').append(o);}
    stats.ready=true;$('engine').textContent='C++ / WASM ready • '+patterns.length+' movements';$('play').disabled=false;
    $('build-info').textContent=`Club Rhythms 05 · v${data.version} · source ${data.source_commit.slice(0,12)} · MIT mappings`;
    populate('all','amen_four_bar');
    $('play').onclick=()=>playing?pause():play();$('reset').onclick=()=>seek(0);
    $('rhythm').onchange=()=>selectRhythm($('rhythm').value);
    $('genre').onchange=()=>populate($('genre').value,rhythm.id);
    $('amen').onclick=()=>{const id=rhythm.id==='amen_four_bar'?'amen_no_ghosts':'amen_four_bar';$('genre').value='all';populate('all',id);};
    $('bpm').onchange=()=>{const next=Number($('bpm').value);if(!Number.isFinite(next)||next<40||next>220){$('bpm').value=String(bpm);return;}const resume=playing;pause();bpm=next;redraw();if(resume)play();};
    $('native-tempo').onclick=()=>{$('bpm').value=String(rhythm.bpm);$('bpm').onchange();};
    $('sound').onchange=async()=>{const resume=playing;pause();if(master)master.gain.setValueAtTime(0,audio.currentTime);if(resume)await play();};
    $('volume').oninput=()=>{if(master)master.gain.setTargetAtTime($('sound').checked?Number($('volume').value):0,audio.currentTime,.02);};
    $('amplitude').oninput=redraw;$('seek').oninput=()=>seek(Number($('seek').value)/64);
    $('previous').onclick=()=>{pause();position=wrap((Math.round(position*64)-1)/64,period);redraw();};
    $('next').onclick=()=>{pause();position=wrap((Math.round(position*64)+1)/64,period);redraw();};
    window.addEventListener('resize',redraw);
    document.addEventListener('visibilitychange',()=>{if(document.hidden&&playing){pause();$('status').textContent='Paused while this tab is hidden.';}});
    const reduced=matchMedia('(prefers-reduced-motion: reduce)');reduced.addEventListener('change',e=>{if(e.matches)pause();});
    setInterval(schedule,25);requestAnimationFrame(frame);
    window.clubDemo={stats,sample,select:id=>{$('genre').value='all';populate('all',id);},seek,play,pause,
      get current(){return rhythm.id;},get playing(){return playing;},get beat(){return beat();},get bpm(){return bpm;},
      get audioState(){return audio?audio.state:'not-created';},patterns:data.patterns,rhythms:data.rhythms};
  }catch(e){report(e);}
})();
