import test from 'node:test';
import assert from 'node:assert/strict';
import {createScenePreparation} from '../../tools/mesh_demo_assets/scene-preparation.js';

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}

test('selection and immediate audition share one source load', async () => {
  const load = deferred();
  const calls = [];
  const preparation = createScenePreparation(key => { calls.push(key); return load.promise; });
  const selected = preparation.prepare('source-a');
  const audition = preparation.prepare('source-a');
  assert.equal(selected, audition);
  assert.deepEqual(calls, ['source-a']);
  load.resolve('ready');
  assert.deepEqual(await Promise.all([selected, audition]), ['ready', 'ready']);
  await preparation.prepare('source-a');
  assert.deepEqual(calls, ['source-a', 'source-a']);
});

test('a superseded load cannot clear the newer source preparation', async () => {
  const first = deferred(), second = deferred();
  const preparation = createScenePreparation(key => key === 'a' ? first.promise : second.promise);
  const a = preparation.prepare('a'), b = preparation.prepare('b');
  first.resolve();
  await a;
  assert.equal(preparation.prepare('b'), b);
  second.resolve();
  await b;
});

test('unload clears sharing without allowing an old completion to clear a new load', async () => {
  const first = deferred(), second = deferred();
  let calls = 0;
  const preparation = createScenePreparation(() => (++calls === 1 ? first : second).promise);
  const a = preparation.prepare('a');
  preparation.clear();
  const b = preparation.prepare('a');
  assert.notEqual(a, b);
  first.resolve();
  await a;
  assert.equal(preparation.prepare('a'), b);
  second.resolve();
  await b;
  assert.equal(calls, 2);
});

test('failed and synchronous preparations release their slot for a retry', async () => {
  let calls = 0;
  const preparation = createScenePreparation(() => {
    if (++calls === 1) throw Error('source unavailable');
    return 'ready';
  });
  await assert.rejects(preparation.prepare('a'), /source unavailable/);
  assert.equal(await preparation.prepare('a'), 'ready');
  assert.equal(calls, 2);
  assert.throws(() => createScenePreparation(null), TypeError);
});
