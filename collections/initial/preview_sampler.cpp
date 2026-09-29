// Minimal C++17 audition binding. Generated data are identical to initial.hpp.
// This freestanding binding avoids an Emscripten install for an offline preview;
// production consumers keep using DanceRudiments' SampledPattern/PatternLibrary.
// MIT; Kieran Simkin / DanceRudiments. See per-pattern data source notices.
#include "preview_data.inc"

extern "C" {
int pattern_count() { return kPatternCount; }
int pattern_period(int index) {
  return index >= 0 && index < kPatternCount ? kPatterns[index].count : 0;
}
double sample_component(int index, int pip, int axis) {
  if (index < 0 || index >= kPatternCount || axis < 0 || axis > 2)
    return __builtin_nan("");
  const auto& pattern = kPatterns[index];
  int wrapped = pip % pattern.count;
  if (wrapped < 0) wrapped += pattern.count;
  return pattern.samples[wrapped][axis];
}
}
