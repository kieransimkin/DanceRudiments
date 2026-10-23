import test from 'node:test';
import assert from 'node:assert/strict';
import {PipTransport, MOTION_TIME_RATES} from '../../tools/mesh_demo_assets/transport.js';

test('half, normal and double time preserve pips across live rate changes', () => {
  let now = 0;
  const transport = new PipTransport(0, 1280, () => now);
  assert.deepEqual(MOTION_TIME_RATES, {half: .5, normal: 1, double: 2});
  transport.setTimeMode('half');
  transport.play(); now = 1000;
  assert.equal(transport.pip(), 32);
  transport.setTimeMode('double');
  assert.equal(transport.pip(), 32);
  now += 1000;
  assert.equal(transport.pip(), 160);
  transport.setTimeMode('normal');
  now += 1000;
  assert.equal(transport.pip(), 224);
  transport.pause(); now += 9999;
  assert.equal(transport.pip(), 224);
  assert.equal(transport.timeMode, 'normal');
  assert.throws(() => transport.setTimeMode('three_quarters'), /mode/);
});
test('pickups, pauses, seeks and inclusive endpoints survive playback rates', () => {
  let now = 0;
  const transport = new PipTransport(-64, 64, () => now);
  transport.setTimeMode('double'); transport.play(); now = 500;
  assert.equal(transport.pip(), 0);
  transport.seek(-32);
  transport.setTimeMode('half'); now += 500;
  assert.equal(transport.pip(), -16);
  now += 10000;
  assert.equal(transport.pip(), 64);
  assert.equal(transport.playing, false);
  assert.throws(() => transport.seek(65), /outside/);
});
test('existing fractional preview rates remain supported and labelled', () => {
  const transport = new PipTransport(0, 128);
  transport.setTimeMode('half'); assert.equal(transport.timeMode, 'half');
  transport.setSpeed(.75); assert.equal(transport.timeMode, null);
  transport.setSpeed(2); assert.equal(transport.timeMode, 'double');
});
