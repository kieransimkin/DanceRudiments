#include "dancerudiments/dance_rudiments.hpp"
#include <cassert>
#include <cmath>
#include <iostream>

using namespace dancerudiments;
bool near(double a, double b) { return std::abs(a - b) < 1e-9; }

int main() {
  assert(catalogue().size() == 67);
  assert(wrap_pip(-1, 64) == 63);
  for (const auto& item : catalogue()) {
    const auto a = sample(item.name, 0);
    const auto b = sample(item.name, item.period_pips);
    const auto c = sample(item.name, -item.period_pips);
    assert(near(a.x, b.x) && near(a.y, b.y) && near(a.z, b.z));
    assert(near(a.x, c.x) && near(a.y, c.y) && near(a.z, c.z));
    for (int pip = 0; pip < item.period_pips; ++pip) {
      const auto v = sample(item.name, pip);
      assert(std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z));
      assert(std::abs(v.x) <= 1.0000001 && std::abs(v.y) <= 1.0000001 && std::abs(v.z) <= 1.0000001);
    }
  }
  const auto clayAccent = clay_background(100);
  assert(near(clayAccent.x, -1.0) && near(clayAccent.y, 0.9));
  // Stroke envelopes start and finish at rest rather than jumping between beats.
  assert(near(single_stroke_roll(0).x, 0.0));
  assert(single_stroke_roll(4).x > 0.8);
  assert(near(single_stroke_roll(8).x, 0.0));
  std::cout << "DanceRudiments C++ tests passed\n";
}
