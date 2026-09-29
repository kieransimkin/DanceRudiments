#include "dancerudiments/dance_rudiments.hpp"
#include <cmath>
#include <climits>
#include <iostream>
#include <stdexcept>
#include <string>
static void require(bool b) { if(!b) throw std::runtime_error("Dancefloor 06 regression"); }
int main() {
  using namespace dancerudiments;
  require(catalogue().size()==1731);
  std::size_t additions=0;
  for(std::size_t i=787;i<catalogue().size();++i) {
    const auto& p=catalogue()[i];++additions;
    for(int pip=0;pip<p.period_pips;++pip) {
      const auto a=sample(p.name,pip),b=sample(p.name,pip-1);
      require(std::isfinite(a.x)&&std::isfinite(a.y)&&std::isfinite(a.z));
      require(std::abs(a.x)<=1&&std::abs(a.y)<=1&&std::abs(a.z)<=1);
      require(std::hypot(std::hypot(a.x-b.x,a.y-b.y),a.z-b.z)<=.35);
    }
    for(int pip:{INT_MIN,INT_MAX,-1,0,1000000}) {
      const auto a=sample(p.name,pip),b=sample(p.name,wrap_pip(pip,p.period_pips));
      require(a.x==b.x&&a.y==b.y&&a.z==b.z);
    }
  }
  require(additions==944);
  std::cout<<"944 Dancefloor additions verified across full loops and extreme pips\n";
}
