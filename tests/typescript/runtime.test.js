import test from "node:test";
import assert from "node:assert/strict";
import { catalogue, sample, wrapPip } from "../../harness/dancerudiments.js";

test("catalogue samples are finite, bounded, and modulo-safe", () => {
  assert.equal(catalogue.length, 15);
  assert.equal(wrapPip(-1,64),63);
  for (const item of catalogue) {
    assert.deepEqual(sample(item.name,0), sample(item.name,item.periodPips));
    for (let pip=0; pip<item.periodPips; pip++) {
      for (const value of Object.values(sample(item.name,pip))) {
        assert.ok(Number.isFinite(value)); assert.ok(Math.abs(value)<=1.0000001);
      }
    }
  }
});

test("drum strokes use smooth zero-boundary envelopes", () => {
  assert.equal(sample("single_stroke_roll",0).x,0);
  assert.ok(sample("single_stroke_roll",4).x>.8);
  assert.ok(Math.abs(sample("single_stroke_roll",8).x)<1e-12);
});
