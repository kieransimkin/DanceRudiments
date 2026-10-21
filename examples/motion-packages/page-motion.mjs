/**
 * Call mountCharacterMotion only when entering the character's page/scene.
 * There is no module-level native initialization, fetch, or motion registration.
 *
 * The host supplies:
 * - rig.target: {typeUri, sha256, dimensions}, from the actual saved scene rig;
 *   do not manufacture this compatibility target from the package manifest.
 * - rig.applyChannels(profile, physicalValues): the scene's rig evaluator.
 *   Rigify IK/constraints need a capable evaluator; bone-name copying is not one.
 * - clock.currentPip()/subscribe(callback): absolute integer positions at 64
 *   pips per quarter note, derived from the host transport's absolute clock.
 *   For a time-only preview, this instead means floor(elapsedSeconds * 64).
 * - wasmUrl: the trusted, separately hosted package `./recording-wasm` asset.
 *   Configure its public URL in the app's build; no motion assets are bundled.
 *
 * Example route lifecycle:
 *   const route = new AbortController();
 *   const playback = mountCharacterMotion({
 *     manifestUrl, packageId, wasmUrl, rig, clock, signal: route.signal,
 *     selection: {sourceClipId: selectedSourceHash}, timing: 'seconds-preview',
 *     onError: error => showError(error.message),
 *   });
 *   await playback.ready;
 *   // On route exit: route.abort(); playback.dispose();
 *
 * `timing: 'music'` requires an explicitly beat/phase-annotated motion. A
 * time-only 60 BPM coordinate does not establish musical tempo or alignment;
 * compile source beat annotations first. No clock or interpolation runs here.
 */
export function mountCharacterMotion({
  manifestUrl, packageId, wasmUrl, rig, clock, selection, timing,
  signal, pipOffset = 0, manifestSha256, fetchAsset = globalThis.fetch,
  onError = error => console.error(error),
}) {
  if (!Number.isSafeInteger(pipOffset)) throw Error('pipOffset must be an integer');
  if (!['music','seconds-preview'].includes(timing)) throw Error('Choose music or seconds-preview timing');
  if (!selection || Boolean(selection.clipId) === Boolean(selection.sourceClipId))
    throw Error('Select either one clipId or one complete sourceClipId');
  const lifetime = new AbortController();
  let loader, unsubscribe, chunks = [], closed = false, generation = 0;
  let active, pending, desiredPip, failedId;
  const aborted = () => { throw new DOMException('Character page was closed','AbortError'); };
  const checkOpen = () => { if (closed || lifetime.signal.aborted) aborted(); };
  const report = error => { if (!closed && error?.name !== 'AbortError') onError(error); };

  function releaseCurrent() {
    generation++;
    if (pending) {
      const old = pending; pending = undefined;
      old.controller.abort(); loader?.unload(old.id);
    }
    if (active) { const old = active; active = undefined; loader?.unload(old.id); }
  }
  function dispose() {
    if (closed) return;
    closed = true;
    lifetime.abort();
    signal?.removeEventListener('abort',dispose);
    unsubscribe?.(); unsubscribe = undefined;
    releaseCurrent(); loader?.dispose(); loader = undefined;
  }
  signal?.addEventListener('abort',dispose,{once:true});
  if (signal?.aborted) dispose();

  function descriptorAt(pip) {
    // Metadata search only; this does not read any other chunk's samples.
    let low=0, high=chunks.length;
    while(low<high) {
      const middle=Math.floor((low+high)/2), item=chunks[middle];
      if(pip<item.start_pip) high=middle;
      else if(pip>=item.start_pip+item.sample_count) low=middle+1;
      else return item;
    }
  }
  function applyLatest(motion, token) {
    if (closed || token !== generation) return;
    const pip=desiredPip;
    if(pip<motion.startPip || pip>=motion.startPip+motion.sampleCount) return;
    // Native sampler reads the absolute pip. Only channel-unit decoding is JS.
    rig.applyChannels(motion.profile,motion.sample(pip));
  }
  function update(hostPip) {
    if (closed) return Promise.resolve();
    if (!Number.isSafeInteger(hostPip)) {
      releaseCurrent(); report(Error('Host clock must supply an integer pip'));return Promise.resolve();
    }
    desiredPip=hostPip-pipOffset;
    const descriptor=descriptorAt(desiredPip);
    if (!descriptor) {
      // Recordings do not loop or hold an invented endpoint outside their range.
      if(active || pending) releaseCurrent();
      return Promise.resolve();
    }
    if(active?.id===descriptor.id) {
      try {applyLatest(active.motion,generation);} catch(error) {releaseCurrent();failedId=descriptor.id;report(error);}
      return Promise.resolve();
    }
    // Frame ticks within one pending chunk update desiredPip without restarting
    // its request. Its completion will sample the latest host position.
    if(pending?.id===descriptor.id) return pending.promise;
    if(failedId===descriptor.id) return Promise.resolve(); // explicit retry below
    releaseCurrent();
    const token=generation, controller=new AbortController();
    const request={id:descriptor.id,controller,promise:undefined};
    pending=request;
    request.promise=loader.load(descriptor.id,{signal:controller.signal}).then(motion=>{
      // Seeking/unmounting invalidates this generation before releasing its
      // handle, so a late network/native completion cannot apply a stale pose.
      if(closed || token!==generation) return;
      pending=undefined;
      if(timing==='music' && motion.clock.phase_status==='unverified') {
        loader.unload(descriptor.id);
        throw Error('Musical playback requires an explicitly annotated source beat phase');
      }
      active={id:descriptor.id,motion};failedId=undefined;
      applyLatest(motion,token);
    }).catch(error=>{
      if(closed || token!==generation) return;
      pending=undefined;failedId=descriptor.id;
      loader.unload(descriptor.id);active=undefined;report(error);
    });
    return request.promise;
  }

  const ready=(async()=>{
    checkOpen();
    // Dynamic import is deliberately inside this route-level operation.
    const {createMotionPackageLoader,createRecordingWasmAdapter} =
      await import('@kieransimkin/dance-rudiments/motion-packages');
    checkOpen();
    const response=await fetchAsset(wasmUrl,{signal:lifetime.signal,credentials:'omit'});
    if(!response.ok) throw Error(`Recording WASM HTTP ${response.status}`);
    const module=await WebAssembly.compile(await response.arrayBuffer());
    checkOpen();
    loader=createMotionPackageLoader({manifestUrl,packageId,expectedProfile:rig.target,
      nativeFactory:createRecordingWasmAdapter(module),fetch:fetchAsset,manifestSha256});
    const manifest=await loader.catalogue({signal:lifetime.signal});
    checkOpen();
    chunks=selection.clipId
      ? manifest.clips.filter(item=>item.id===selection.clipId)
      : manifest.clips.filter(item=>(item.metadata?.original_clip_id ?? item.metadata?.clip_id)===selection.sourceClipId);
    chunks.sort((a,b)=>a.start_pip-b.start_pip);
    if(!chunks.length) throw Error('Selected motion is not in this compatible package');
    if(selection.sourceClipId) {
      const total=chunks.reduce((sum,item)=>sum+item.sample_count,0);
      chunks.forEach((item,index)=>{
        if(item.metadata?.chunk_index!==index || item.metadata?.chunk_count!==chunks.length ||
           item.metadata?.total_sample_count!==total ||
           (index && item.start_pip!==chunks[index-1].start_pip+chunks[index-1].sample_count))
          throw Error('Selected source motion must have its complete contiguous chunk manifest');
      });
    }
    for(const item of chunks) {
      const kind=item.metadata?.timing_kind, mode=item.metadata?.timing_mode;
      if(timing==='music' && (kind==='time-only' || mode==='time-only' || mode==='tempo-only'))
        throw Error('Time-only/tempo-only motion needs explicit source tempo and beat phase before musical playback');
      if(timing==='seconds-preview' && kind!=='time-only' && mode!=='time-only')
        throw Error('Seconds-preview is reserved for explicitly labelled time-only motion');
    }
    unsubscribe=clock.subscribe(pip=>{void update(pip);});
    await update(clock.currentPip());
  })().catch(error=>{report(error);dispose();throw error;});

  return Object.freeze({
    ready, dispose,
    retry() {if(!closed && loader) {failedId=undefined;return update(clock.currentPip());}return Promise.resolve();},
  });
}
