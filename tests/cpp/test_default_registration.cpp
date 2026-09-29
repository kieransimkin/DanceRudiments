#include "dancerudiments/dance_rudiments.hpp"
#include "dancerudiments/sampled_pattern.hpp"
#include <climits>
#include <cmath>
#include <set>
#include <stdexcept>
#include <string>
using namespace dancerudiments;
static void require(bool value) { if (!value) throw std::runtime_error("Default regression failed"); }
int main() {
  require(catalogue().size()==643);
  std::set<std::string> names;
  for (const auto& p: catalogue()) {
    require(names.insert(std::string(p.name)).second);
    for (int pip: {INT_MIN, INT_MAX, -1, 0, 512, 1000000}) {
      auto a=sample(p.name,pip),b=sample(p.name,wrap_pip(pip,p.period_pips));
      require(a.x==b.x && a.y==b.y && a.z==b.z);
      require(std::isfinite(a.x) && std::isfinite(a.y) && std::isfinite(a.z));
    }
  }
  std::vector<Offset3> values;
  auto p=catalogue()[15];
  for (int pip=0;pip<p.period_pips;++pip) values.push_back(sample(p.name,pip));
  SampledPattern copy(std::string(p.name),std::string(p.description),values);
  require(PatternLibrary({copy}).catalogue().size()==643);
  values[10].x=.123;
  bool rejected=false;
  try { PatternLibrary changed({SampledPattern(std::string(p.name),std::string(p.description),values)}); }
  catch (const std::invalid_argument&) { rejected=true; }
  require(rejected);
}
