/** Explicit source-motion playback rates; never a claim about music BPM. */
export type MotionTimeMode = 'half' | 'normal' | 'double';
export const MOTION_TIME_RATES: Readonly<Record<MotionTimeMode, number>> =
  Object.freeze({half: 0.5, normal: 1, double: 2});

export function motionTimeRate(mode: MotionTimeMode): number {
  if (!Object.prototype.hasOwnProperty.call(MOTION_TIME_RATES, mode))
    throw new RangeError('Motion time mode must be half, normal or double');
  return MOTION_TIME_RATES[mode];
}

/** Get the absolute integer source pip without resampling or implicit wrapping. */
export function motionSourcePipAtTime(
  sourceStartPip: number, elapsedOutputSeconds: number,
  mode: MotionTimeMode, pipsPerSourceSecond = 64,
): number {
  if (!Number.isSafeInteger(sourceStartPip) ||
      !Number.isFinite(elapsedOutputSeconds) || elapsedOutputSeconds < 0 ||
      !Number.isFinite(pipsPerSourceSecond) || pipsPerSourceSecond <= 0)
    throw new RangeError('Invalid source pip, elapsed time or clock');
  const pip = Math.floor(sourceStartPip + elapsedOutputSeconds *
    pipsPerSourceSecond * motionTimeRate(mode));
  if (!Number.isSafeInteger(pip) || pip < -2147483648 || pip > 2147483647)
    throw new RangeError('Motion source pip exceeds signed int32 bounds');
  return pip;
}
