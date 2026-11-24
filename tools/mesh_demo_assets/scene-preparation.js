/* Share one in-flight scene load; the existing owner still cancels and disposes. */
export function createScenePreparation(prepare) {
  if (typeof prepare !== 'function') throw new TypeError('Scene preparation needs a function');
  let inFlight = null;
  return Object.freeze({
    prepare(key) {
      if (inFlight?.key === key) return inFlight.promise;
      const job = {key, promise: null};
      inFlight = job;
      job.promise = (async () => {
        try { return await prepare(key); }
        finally { if (inFlight === job) inFlight = null; }
      })();
      return job.promise;
    },
    clear() { inFlight = null; },
  });
}
