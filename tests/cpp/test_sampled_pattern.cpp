#include "dancerudiments/sampled_pattern.hpp"
#include <climits>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace dancerudiments;
void check(bool condition) { if (!condition) throw std::runtime_error("Pattern test failed"); }
template <typename F> void rejects(F f) {
  bool rejected = false;
  try { f(); } catch (const std::invalid_argument&) { rejected = true; }
  check(rejected);
}
bool same(Offset3 a, Offset3 b) { return a.x == b.x && a.y == b.y && a.z == b.z; }

int main() {
  const std::vector<Offset3> values{{0,0,0}, {1,-.5,0}, {-1,.5,.25}};
  SampledPattern p("custom_step", "Three-pip test", values);
  check(p.period_pips() == 3 && p.info().dimensions == Dimension::three);
  for (int pip : {INT_MIN, -200, -3, -1, 0, 1, 2, 3, 200, INT_MAX})
    check(same(p.sample(pip), values[wrap_pip(pip, 3)]));
  constexpr std::array<Offset3, 3> table{{{0,0,0},{1,-.5,0},{-1,.5,.25}}};
  check(same(sample_table(table, -1), p.sample(-1)));
  auto input = values;
  SampledPattern owned("owned", "", input);
  input[0].x = .9;
  check(owned.sample(0).x == 0);
  SampledPattern one("one", "", {{0, 0, 0}});
  check(one.info().dimensions == Dimension::one && one.sample(INT_MIN).x == 0);
  SampledPattern two("two", "", {{0, .2, 0}});
  check(two.info().dimensions == Dimension::two);
  SampledPattern longest("longest", "", std::vector<Offset3>(max_pattern_samples));
  check(longest.period_pips() == 65535);
  rejects([] { SampledPattern("empty", "", {}); });
  rejects([] { SampledPattern("bad-name", "", {{0,0,0}}); });
  rejects([] { SampledPattern("", "", {{0,0,0}}); });
  rejects([] { SampledPattern("bad", "", {{1.01,0,0}}); });
  rejects([] { SampledPattern("bad", "", {{0,0,std::numeric_limits<double>::infinity()}}); });
  rejects([] { SampledPattern("bad", "", {{0,std::numeric_limits<double>::quiet_NaN(),0}}); });
  rejects([] { SampledPattern("long", "", std::vector<Offset3>(max_pattern_samples + 1)); });
  PatternLibrary library({p, owned, one, two});
  check(library.catalogue().size() == 19 && catalogue().size() == 15);
  check(same(library.sample("custom_step", -1), p.sample(-1)));
  for (const auto& builtin : catalogue()) {
    for (int pip = -2 * builtin.period_pips; pip <= 2 * builtin.period_pips; ++pip) {
      check(same(library.sample(builtin.name, pip), sample(builtin.name, pip)));
      const auto v = sample(builtin.name, pip);
      check(std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z));
      check(std::abs(v.x) <= 1 && std::abs(v.y) <= 1 && std::abs(v.z) <= 1);
    }
  }
  rejects([&] { PatternLibrary duplicate({p, p}); });
  rejects([] { PatternLibrary collision({SampledPattern("circle", "", {{0,0,0}})}); });
  rejects([&] { library.sample("not_present", 0); });
  rejects([&] { PatternLibrary many(std::vector<SampledPattern>(max_pack_patterns + 1, p)); });
  // Catalogue views are constructed on demand; copying a bank cannot retain
  // string_views into a destroyed original bank.
  PatternLibrary copy;
  { PatternLibrary temporary({p}); copy = temporary; }
  check(copy.catalogue().back().name == "custom_step");
  check(same(copy.sample("custom_step", 1), p.sample(1)));
  std::cout << "Sampled patterns and built-in regression checks passed\n";
}
