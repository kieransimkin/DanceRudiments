/* DanceRudiments beat transport + Standard MIDI File codec. MIT.
 * JavaScript handles audio/UI only. Movement samples still come from C++/WASM.
 * No soundfonts, network requests, MIDI-device permissions or audio recordings.
 */
'use strict';
(() => {
  const MAX_EVENTS=65536, MAX_BYTES=2097152, MAX_BEATS=4096;
  const positiveModulo=(x,n)=>((x%n)+n)%n;
  function rational(value){
    if(typeof value==='number' && Number.isFinite(value)) return value;
    if(typeof value!=='string'||!/^[-+]?\d+(?:\/\d+)?$/.test(value))throw Error('Invalid rational beat');
    const [n,d='1']=value.split('/').map(Number), result=n/d;
    if(!Number.isSafeInteger(n)||!Number.isSafeInteger(Number(d))||!d||!Number.isFinite(result))throw Error('Invalid rational beat');
    return result;
  }
  function normalizeBeat(b){
    if(!b||typeof b.id!=='string'||!Array.isArray(b.events)||b.events.length>MAX_EVENTS)throw Error('Invalid beat score');
    const period=rational(b.period_beats);
    if(period<=0||period>MAX_BEATS)throw Error('Beat loop is out of range');
    const events=b.events.map((e,i)=>{
      const time=rational(e.beat), duration=rational(e.duration===undefined?'1/16':e.duration);
      if(time<0||time>=period||duration<=0||duration>MAX_BEATS||!Number.isFinite(e.velocity)||e.velocity<=0||e.velocity>1||
         !Number.isInteger(e.note)||e.note<0||e.note>127||!Number.isInteger(e.channel)||e.channel<0||e.channel>15)
        throw Error('Invalid MIDI note in '+b.id+' at index '+i);
      return Object.freeze({...e,time,durationBeats:duration,index:i});
    }).sort((a,b)=>a.time-b.time||a.index-b.index);
    return Object.freeze({...b,period,events:Object.freeze(events)});
  }
  /** Half-open musical interval, valid across loop boundaries and negative seeks. */
  function eventsBetween(b,from,to){
    if(!Number.isFinite(from)||!Number.isFinite(to)||to<from||to-from>MAX_BEATS)throw Error('Invalid scheduling window');
    const out=[];
    for(let cycle=Math.floor(from/b.period);cycle<=Math.floor(to/b.period);cycle++){
      for(const event of b.events){const at=cycle*b.period+event.time;
        if(at>=from&&at<to)out.push({event,beat:at});
      }
    }
    return out;
  }

  class BeatTransport {
    constructor({bpm=120,onChange=()=>{},contextFactory=null,autoTick=true}={}){
      this.bpm=bpm;this.onChange=onChange;this.contextFactory=contextFactory;this.autoTick=autoTick;
      this.context=null;this.master=null;this.score=null;this.running=false;this.sound=true;
      this.volume=.28;this.baseBeat=0;this.epoch=0;this.cursor=0;this.generation=0;
      this.timer=null;this.active=new Set();this.buffers=new Map();this.muted=new Set();
      this.stats={scheduled:0,voices:0,late:0,peakVoices:0};
    }
    rawTime(){return this.context?this.context.currentTime:performance.now()/1000;}
    visualTime(){
      const c=this.context;if(!c)return this.rawTime();
      if(c.getOutputTimestamp){const s=c.getOutputTimestamp();
        if(s&&s.contextTime>0&&Number.isFinite(s.performanceTime))
          return Math.min(c.currentTime,Math.max(0,s.contextTime+(performance.now()-s.performanceTime)/1000));
      }
      return Math.max(0,c.currentTime-(c.outputLatency||c.baseLatency||0));
    }
    beatAt(time){return this.baseBeat+(this.running?Math.max(0,time-this.epoch)*this.bpm/60:0);}
    beat(){return this.beatAt(this.visualTime());}
    async unlock(){
      const beat=this.beat();
      if(!this.context){
        const C=globalThis.AudioContext||globalThis.webkitAudioContext;
        if(!C&&!this.contextFactory)throw Error('Web Audio is unavailable. Untick MIDI sound for silent animation.');
        this.context=this.contextFactory?this.contextFactory():new C({latencyHint:'interactive'});
        this.master=this.context.createGain();this.master.gain.value=this.volume;
        const limiter=this.context.createDynamicsCompressor();limiter.threshold.value=-10;limiter.knee.value=12;limiter.ratio.value=8;
        this.master.connect(limiter);limiter.connect(this.context.destination);
        this.baseBeat=beat;this.epoch=this.context.currentTime;this.cursor=beat;
        this.context.addEventListener('statechange',()=>{if(this.running&&this.context.state!=='running')this.pause();});
      }
      await this.context.resume();
      if(this.context.state!=='running')throw Error('Audio is suspended. Press Play to enable it.');
    }
    async play(){
      if(this.running)return;
      const generation=++this.generation;
      if(this.sound||this.context)await this.unlock();
      if(generation!==this.generation)return;
      this.epoch=this.rawTime()+.035;this.cursor=this.baseBeat;this.running=true;
      this.tick();if(this.autoTick)this.timer=setInterval(()=>this.tick(),25);this.onChange();
    }
    cancelVoices(){for(const src of this.active){try{src.stop();}catch(_){}}this.active.clear();}
    pause(){
      const beat=this.beat();++this.generation;this.running=false;this.baseBeat=beat;
      if(this.timer!==null)clearInterval(this.timer);this.timer=null;this.cancelVoices();this.onChange();
    }
    rebase(beat){
      if(!Number.isFinite(beat)||Math.abs(beat)>33554400)throw Error('Seek exceeds the signed 32-bit pip range');
      this.cancelVoices();this.baseBeat=beat;this.cursor=beat;this.epoch=this.rawTime()+.025;
      if(this.running)this.tick();this.onChange();
    }
    seek(beat){this.rebase(beat);}
    setBpm(bpm){
      if(!Number.isFinite(bpm)||bpm<20||bpm>300)throw Error('Tempo must be 20–300 BPM');
      const beat=this.beat();this.bpm=bpm;this.rebase(beat);
    }
    setScore(score){const checked=normalizeBeat(score);const beat=this.beat();this.score=checked;this.muted.clear();this.rebase(beat);}
    setVolume(value){
      if(!Number.isFinite(value)||value<0||value>1)throw Error('Volume must be 0–1');
      this.volume=value;if(this.master)this.master.gain.setTargetAtTime(value,this.context.currentTime,.01);
    }
    async setSound(enabled){
      const generation=++this.generation, beat=this.beat();this.sound=!!enabled;
      this.cancelVoices();
      if(enabled&&this.running)await this.unlock();
      if(generation!==this.generation)return;
      this.rebase(beat);
    }
    mute(lane,value){value?this.muted.add(lane):this.muted.delete(lane);this.rebase(this.beat());}
    tick(){
      if(!this.running||!this.score)return;
      const now=this.rawTime(), start=this.beatAt(now), end=this.beatAt(now+.10);
      const from=Math.max(this.cursor,start);
      if(this.sound&&this.context&&this.context.state==='running'){
        for(const {event,beat} of eventsBetween(this.score,from,end)){
          if(this.muted.has(event.lane))continue;
          const when=this.epoch+(beat-this.baseBeat)*60/this.bpm;
          if(when+1e-6<now){this.stats.late++;continue;}
          this.voice(event,Math.max(when,now));this.stats.scheduled++;
        }
      }
      this.cursor=end;
    }
    drumBuffer(note){
      if(this.buffers.has(note))return this.buffers.get(note);
      const c=this.context, kick=note===35||note===36, snare=[38,40].includes(note), clap=note===39;
      const hat=[42,44,46,69,70,82].includes(note), metal=[49,51,52,53,55,57,59].includes(note);
      const tom=[41,43,45,47,48,50].includes(note), rim=note===37;
      const duration=kick?.38:snare?.22:clap?.19:hat?(note===46?.30:.075):metal?.65:tom?.32:.16;
      const out=c.createBuffer(1,Math.ceil(c.sampleRate*duration),c.sampleRate), v=out.getChannelData(0);
      let seed=0x5eeda1+note,phase=0,previous=0;
      for(let i=0;i<v.length;i++){
        const t=i/c.sampleRate;seed=(Math.imul(seed,1664525)+1013904223)>>>0;
        const noise=seed/2147483648-1, high=noise-previous*.8;previous=noise;
        phase+=2*Math.PI*((kick?42+115*Math.exp(-t*38):tom?80+(note-41)*12+100*Math.exp(-t*35):180))/c.sampleRate;
        const attack=Math.min(1,t/.0015), env=Math.exp(-t/(kick?.082:tom?.07:metal?.17:hat?(note===46?.075:.016):.045));
        let value=kick?Math.sin(phase)*.85:snare?(.48*high+.2*Math.sin(phase)):clap?high*.5*(.45+.55*Math.abs(Math.sin(t*950))):
          hat?high*.22:metal?(high*.15+.06*Math.sin(t*19000)):tom?Math.sin(phase)*.55:
          rim?.28*(Math.sin(t*6200)+.35*Math.sin(t*9500)):.26*(Math.sin(t*(2000+note*20))+.4*high);
        v[i]=value*attack*env;
      }
      this.buffers.set(note,out);return out;
    }
    voice(e,when){
      if(this.active.size>=256)return; // defensive bound for user-imported files
      const c=this.context,gain=c.createGain();gain.connect(this.master);let src,end;
      if(e.channel===9){src=c.createBufferSource();src.buffer=this.drumBuffer(e.note);end=when+src.buffer.duration;gain.gain.setValueAtTime(e.velocity,when);}
      else{src=c.createOscillator();src.type='triangle';src.frequency.value=440*Math.pow(2,(e.note-69)/12);
        const duration=Math.min(8,e.durationBeats*60/this.bpm);end=when+duration+.045;
        gain.gain.setValueAtTime(0,when);gain.gain.linearRampToValueAtTime(.38*e.velocity,when+.005);
        gain.gain.setValueAtTime(.28*e.velocity,when+Math.max(.006,duration));gain.gain.linearRampToValueAtTime(0,end);
      }
      src.connect(gain);this.active.add(src);this.stats.voices++;this.stats.peakVoices=Math.max(this.stats.peakVoices,this.active.size);
      src.onended=()=>{this.active.delete(src);src.disconnect();gain.disconnect();};src.start(when);src.stop(end+.005);
    }
    dispose(){this.pause();if(this.context)this.context.close();this.buffers.clear();}
    state(){return {beat:this.beat(),bpm:this.bpm,running:this.running,sound:this.sound,score:this.score?.id,
      audioState:this.context?.state||'not-created',activeVoices:this.active.size,...this.stats};}
  }

  function midiRead(input,title='Imported MIDI'){
    const a=input instanceof Uint8Array?input:new Uint8Array(input);
    if(a.length<14||a.length>MAX_BYTES)throw Error('MIDI must be a valid SMF of at most 2 MiB');
    const d=new DataView(a.buffer,a.byteOffset,a.byteLength);let p=0;
    const need=n=>{if(p+n>a.length)throw Error('Truncated MIDI file');};
    const u16=()=>{need(2);const v=d.getUint16(p);p+=2;return v;};
    const u32=()=>{need(4);const v=d.getUint32(p);p+=4;return v;};
    const text=n=>{need(n);const s=String.fromCharCode(...a.subarray(p,p+n));p+=n;return s;};
    if(text(4)!=='MThd')throw Error('Missing MIDI header');const header=u32();
    if(header<6||header>a.length-8)throw Error('Invalid MIDI header');
    const format=u16(),tracks=u16(),ppq=u16();p=8+header;
    if(format>1||tracks<1||tracks>128||(format===0&&tracks!==1))throw Error('Only MIDI type 0 and 1 files are supported');
    if(ppq===0||ppq&0x8000)throw Error('SMPTE timing is not supported; use a PPQ MIDI file');
    const notes=[],tempos=[],meters=[],credits=[];let endTick=0,messages=0;
    for(let track=0;track<tracks;track++){
      if(text(4)!=='MTrk')throw Error('Missing MIDI track');const size=u32(),end=p+size;need(size);
      let tick=0,running=0,ended=false;const active=new Map();
      const byte=()=>{if(p>=end)throw Error('Truncated MIDI event');return a[p++];};
      const dataByte=()=>{const n=byte();if(n>127)throw Error('Invalid MIDI data byte');return n;};
      const vlq=()=>{let v=0;for(let i=0;i<4;i++){const b=byte();v=v*128+(b&127);if(!(b&128))return v;}throw Error('MIDI VLQ exceeds four bytes');};
      while(p<end){
        if(++messages>MAX_EVENTS*16)throw Error('Too many MIDI events');tick+=vlq();
        if(tick/ppq>MAX_BEATS)throw Error('MIDI exceeds 4096 quarter-note beats');
        let status=byte();if(status<128){if(!running)throw Error('Invalid MIDI running status');p--;status=running;}
        if(status===255){running=0;const type=byte(),length=vlq();if(p+length>end)throw Error('Truncated MIDI metadata');
          if(type===81){if(length!==3)throw Error('Invalid tempo event');const us=a[p]*65536+a[p+1]*256+a[p+2];if(!us)throw Error('Zero MIDI tempo');tempos.push({tick,bpm:60000000/us});}
          if(type===88){if(length!==4||a[p]===0||a[p+1]>6)throw Error('Invalid MIDI meter');meters.push({tick,meter:[a[p],2**a[p+1]]});}
          if([1,2].includes(type)&&length<=8192&&credits.length<32)credits.push(new TextDecoder().decode(a.subarray(p,p+length)));
          p+=length;if(type===47){if(length!==0||p!==end)throw Error('Invalid end-of-track');ended=true;break;}continue;
        }
        if(status===240||status===247){running=0;const length=vlq();if(p+length>end)throw Error('Truncated MIDI sysex');p+=length;continue;}
        if(status<128||status>=240)throw Error('Unsupported MIDI system status');running=status;
        const hi=status>>4,channel=status&15,n=dataByte(),v=[12,13].includes(hi)?0:dataByte();
        const key=channel+':'+n;
        if(hi===9&&v>0){
          if(notes.length>=MAX_EVENTS)throw Error('Too many MIDI notes');
          const item={tick,channel,note:n,velocity:v/127,end:null};notes.push(item);
          if(!active.has(key))active.set(key,[]);active.get(key).push(item);
        }else if(hi===8||(hi===9&&v===0)){const queue=active.get(key);if(queue?.length)queue.shift().end=tick;}
      }
      if(!ended)throw Error('MIDI track has no end-of-track');endTick=Math.max(endTick,tick);
    }
    if(p!==a.length)throw Error('Unexpected bytes after MIDI tracks');
    if(!notes.length||!endTick)throw Error('MIDI contains no playable notes');
    tempos.sort((a,b)=>a.tick-b.tick);meters.sort((a,b)=>a.tick-b.tick);
    const events=notes.filter(n=>n.tick<endTick).map(n=>({beat:`${n.tick}/${ppq}`,note:n.note,channel:n.channel,
      lane:n.channel===9?'GM '+n.note:'Channel '+(n.channel+1),velocity:n.velocity,
      duration:`${Math.max(1,n.end===null?Math.min(Math.max(1,Math.round(ppq/4)),endTick-n.tick):n.end-n.tick)}/${ppq}`}));
    return normalizeBeat({id:'imported_midi',title,family:'Your MIDI',kind:'imported',period_beats:`${endTick}/${ppq}`,
      bpm:tempos[0]?.bpm||120,meter:meters[0]?.meter||null,events,pattern_names:[],license:'User-provided file',
      notes:'PPQ note timing and end-of-track loop length retained. All tempo changes are replaced by the harness BPM. '+
        'Channel 10 uses a synthesised percussion kit; other channels use simple pitched cues. '+
        'Programs, controllers, pitch bends and pedals are not emulated. '+(tempos.length>1?'This file contains a tempo map.':''),
      midi:{format,ppq,tempo_events:tempos.length,meter_events:meters.length,credits}});
  }
  function midiWrite(score,bpm=120){
    const b=normalizeBeat(score);
    if(!Number.isFinite(bpm)||bpm<20||bpm>300)throw Error('Invalid MIDI tempo');
    const gcd=(a,b)=>b?gcd(b,a%b):a;
    let ppq=960;
    for(const value of [b.period_beats,...b.events.flatMap(e=>[e.beat,e.duration])]){
      const denominator=typeof value==='string'&&value.includes('/')?Number(value.split('/')[1]):1;
      const next=ppq/gcd(ppq,denominator)*denominator;
      if(next>32767){ppq=30720;break;}ppq=next;
    }
    const encode=new TextEncoder(), out=[];
    const vlq=n=>{if(!Number.isInteger(n)||n<0||n>0x0fffffff)throw Error('MIDI delta out of range');const a=[n&127];while(n>>>=7)a.unshift((n&127)|128);return a;};
    const be=(n,bytes)=>Array.from({length:bytes},(_,i)=>(n/2**((bytes-i-1)*8))&255);
    const str=s=>[...encode.encode(s)];
    const chunk=(name,data)=>[...str(name),...be(data.length,4),...data];
    const end=Math.round(b.period*ppq), tempo=Math.round(60000000/bpm);
    const meta=(type,s)=>{const text=str(s);return [255,type,...vlq(text.length),...text];};
    const header=[...be(1,2),...be(2,2),...be(ppq,2)];
    out.push(...chunk('MThd',header));
    let conductor=[0,...meta(3,b.title),0,255,81,3,...be(tempo,3)];
    if(b.meter&&b.meter[0]<=255&&Number.isInteger(Math.log2(b.meter[1])))conductor.push(0,255,88,4,b.meter[0],Math.log2(b.meter[1]),24,8);
    const provenance=b.provenance||{};
    const credit=[provenance.attribution||provenance.author||'Kieran Simkin / DanceRudiments',b.license,
      provenance.license_url,provenance.source_url,provenance.transformation,
      'Adapted to General MIDI audition notes. Original event timing retained subject to the reported PPQ quantisation.',
      ...(b.midi?.credits||[])].filter(Boolean).join(' | ');
    conductor.push(0,...meta(2,credit.slice(0,24000)));
    conductor.push(0,...meta(1,'DanceRudiments; '+(b.license||'source terms apply')+'; '+(b.notes||'')));
    conductor.push(...vlq(end),255,47,0);out.push(...chunk('MTrk',conductor));
    const messages=[];let maxError=Math.abs(end/ppq-b.period);
    b.events.forEach((e,i)=>{
      const tick=Math.min(end-1,Math.round(e.time*ppq)),off=Math.min(end,Math.max(tick+1,Math.round((e.time+e.durationBeats)*ppq)));
      maxError=Math.max(maxError,Math.abs(tick/ppq-e.time));
      messages.push({tick,order:1,index:i,bytes:[144|e.channel,e.note,Math.max(1,Math.min(127,Math.round(e.velocity*127)))]},
                    {tick:off,order:0,index:i,bytes:[128|e.channel,e.note,0]});
    });
    messages.sort((a,b)=>a.tick-b.tick||a.order-b.order||a.index-b.index);
    const track=[0,...meta(3,'Beat notes')];let tick=0;
    for(const m of messages){track.push(...vlq(m.tick-tick),...m.bytes);tick=m.tick;}
    track.push(...vlq(end-tick),255,47,0);
    // Avoid argument-count overflow for large imported files.
    const finalChunk=chunk('MTrk',track), bytes=new Uint8Array(out.length+finalChunk.length);
    bytes.set(out);bytes.set(finalChunk,out.length);
    return {bytes,ppq,maxTimingErrorBeats:maxError};
  }
  globalThis.DanceBeat=Object.freeze({BeatTransport,normalizeBeat,eventsBetween,rational,midiRead,midiWrite,positiveModulo});
})();
