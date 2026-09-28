#include <emscripten/bind.h>
#include "dancerudiments/dance_rudiments.hpp"

using namespace emscripten;
using namespace dancerudiments;

EMSCRIPTEN_BINDINGS(dancerudiments) {
  value_object<Offset3>("Offset3").field("x", &Offset3::x).field("y", &Offset3::y).field("z", &Offset3::z);
  function("sample", optional_override([](const std::string& name, int pip) { return sample(name, pip); }));
  function("bounce", &bounce); function("sway", &sway); function("circle", &circle);
  function("figureEight", &figure_eight); function("stepTouch", &step_touch);
  function("boxStep", &box_step); function("helix", &helix); function("clayBackground", &clay_background);
  function("singleStrokeRoll", &single_stroke_roll); function("doubleStrokeRoll", &double_stroke_roll);
  function("multipleBounceRoll", &multiple_bounce_roll);
  function("singleParadiddle", &single_paradiddle); function("flam", &flam); function("drag", &drag);
  function("fiveStrokeRoll", &five_stroke_roll);
}
