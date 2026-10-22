/** A UI clock only. Poses are always read by the existing native sampler. */
export class PipTransport {
  constructor(first, last, now = () => performance.now()) {
    if (!Number.isSafeInteger(first) || !Number.isSafeInteger(last) || last < first)
      throw Error('Invalid inclusive motion bounds');
    this.first = first; this.last = last; this.now = now;
    this.anchorPip = first; this.anchorTime = now(); this.speed = 1; this.playing = false;
  }
  position(time = this.now()) {
    const value = this.anchorPip + (this.playing ? Math.max(0, time - this.anchorTime) * .064 * this.speed : 0);
    if (value >= this.last) {
      this.anchorPip = this.last; this.anchorTime = time; this.playing = false;
      return this.last;
    }
    return Math.max(this.first, value);
  }
  pip(time = this.now()) { return Math.floor(this.position(time)); }
  pause() { this.anchorPip = this.position(); this.anchorTime = this.now(); this.playing = false; }
  play() { if (!this.playing) { this.anchorTime = this.now(); this.playing = true; } }
  seek(pip) {
    if (!Number.isSafeInteger(pip) || pip < this.first || pip > this.last) throw Error('Seek is outside this non-looping performance');
    this.anchorPip = pip; this.anchorTime = this.now();
  }
  setSpeed(speed) {
    if (!Number.isFinite(speed) || speed <= 0 || speed > 4) throw Error('Invalid preview speed');
    this.anchorPip = this.position(); this.anchorTime = this.now(); this.speed = speed;
  }
}
