#include "dancerudiments/dance_rudiments.hpp"
#include <cmath>
#include <climits>
#include <iostream>
#include <stdexcept>

static void require(bool condition) { if (!condition) throw std::runtime_error("Club rhythm test failed"); }
int main() {
  using namespace dancerudiments;
  require(catalogue().size() == 1731);
  int count = 0;
  for (const auto& info : catalogue()) {
    if (info.name.substr(0, 5) != "beat_") continue;
    ++count;
    require(info.period_pips == 256 || info.period_pips == 512 || info.period_pips == 768 || info.period_pips == 1024);
    for (int pip=0; pip<info.period_pips; ++pip) {
      const auto v=sample(info.name,pip);
      require(std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z));
      require(std::abs(v.x)<=1 && std::abs(v.y)<=1 && std::abs(v.z)<=1);
    }
    for (int pip : {INT_MIN, -1, 0, INT_MAX}) {
      const auto a=sample(info.name,pip), b=sample(info.name,wrap_pip(pip,info.period_pips));
      require(a.x==b.x && a.y==b.y && a.z==b.z);
    }
  }
  require(count == 1088);
  // Bare quarter-note kick maximum aligns with every numbered beat.
  for (int beat=0; beat<4; ++beat) require(sample("beat_four_floor_bounce",beat*64).y == .55);
  std::cout << "1088 beat movements registered, bounded and safe at extreme pips\n";
}
