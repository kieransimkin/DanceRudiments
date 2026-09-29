#include <emscripten/bind.h>
#include <string>
#include <stdexcept>
#include <utility>
#include "dancerudiments/dance_rudiments.hpp"
#include "dancerudiments/sampled_pattern.hpp"

using namespace emscripten;
using namespace dancerudiments;

namespace {
PatternLibrary* make_pattern_library(const val& values) {
  const auto count = values["length"].as<unsigned>();
  if (count > max_pack_patterns) throw std::invalid_argument("Too many patterns");
  std::vector<SampledPattern> patterns;
  patterns.reserve(count);
  for (unsigned i = 0; i < count; ++i) patterns.push_back(values[i].as<SampledPattern>());
  return new PatternLibrary(std::move(patterns));
}
}

EMSCRIPTEN_BINDINGS(dancerudiments) {
  value_object<Offset3>("Offset3").field("x", &Offset3::x).field("y", &Offset3::y).field("z", &Offset3::z);
  register_vector<Offset3>("OffsetVector");
  class_<SampledPattern>("SampledPattern")
    .constructor<std::string, std::string, std::vector<Offset3>>()
    .function("sample", &SampledPattern::sample)
    .function("periodPips", &SampledPattern::period_pips);
  class_<PatternLibrary>("PatternLibrary")
    .constructor(&make_pattern_library, allow_raw_pointers())
    .function("sample", optional_override([](const PatternLibrary& library,
                                            const std::string& name, int pip) {
      return library.sample(name, pip);
    }));
  function("sample", optional_override([](const std::string& name, int pip) { return sample(name, pip); }));
  function("bounce", &bounce); function("sway", &sway); function("circle", &circle);
  function("figureEight", &figure_eight); function("stepTouch", &step_touch);
  function("boxStep", &box_step); function("helix", &helix); function("clayBackground", &clay_background);
  function("singleStrokeRoll", &single_stroke_roll); function("doubleStrokeRoll", &double_stroke_roll);
  function("multipleBounceRoll", &multiple_bounce_roll);
  function("singleParadiddle", &single_paradiddle); function("flam", &flam); function("drag", &drag);
  function("fiveStrokeRoll", &five_stroke_roll);
}
