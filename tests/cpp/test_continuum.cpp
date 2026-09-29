// MIT. Real native lookup and direct generated functions; checks stay active in Release.
#include "dancerudiments/dance_rudiments.hpp"
#include "dancerudiments/collections/continuum.hpp"
#include <climits>
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace dancerudiments;
static void require(bool ok) { if (!ok) throw std::runtime_error("Continuum check failed"); }
static bool same(Offset3 a, Offset3 b) { return a.x==b.x && a.y==b.y && a.z==b.z; }
int main() {
  require(catalogue().size()==787);
  std::size_t count=0;
  for (const auto& item: catalogue()) {
    for (int pip=0; pip<item.period_pips; ++pip) {
      const auto a=sample(item.name,pip);
      require(std::isfinite(a.x) && std::isfinite(a.y) && std::isfinite(a.z));
      require(std::abs(a.x)<=1 && std::abs(a.y)<=1 && std::abs(a.z)<=1);
      require(same(a,sample(item.name,pip-item.period_pips))); ++count;
    }
    for (int pip : {INT_MIN, INT_MAX, -100003, 100003})
      require(same(sample(item.name,pip),sample(item.name,wrap_pip(pip,item.period_pips))));
  }
  for (int pip : {INT_MIN, -1025, -1, 0, 63, 1024, INT_MAX}) {
    require(same(sample("ribbon_2_5_deep",pip),dancerudiments_continuum::sample_ribbon_2_5_deep(pip)));
    require(same(sample("surface_3_5_wide",pip),dancerudiments_continuum::sample_surface_3_5_wide(pip)));
  }
  for (const char* bad: {"", "a", "zzzzzz", "ribbon_1_2", "ribbon_1_2_slim_"}) {
    bool threw=false; try { (void)sample(bad,0); } catch (const std::invalid_argument&) { threw=true; }
    require(threw);
  }
  std::cout << "Validated " << count << " native XYZ samples and wrapped positions\n";
}
