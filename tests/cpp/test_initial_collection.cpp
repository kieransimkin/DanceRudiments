// MIT. Full native library and allocation-free functions versus the audition C++ binding.
#include "dancerudiments/collections/initial.hpp"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

extern "C" int pattern_count();
extern "C" int pattern_period(int);
extern "C" double sample_component(int, int, int);

using Sampler = dancerudiments::Offset3 (*)(int);
const char* names[] = {"lfo_breathe", "lfo_surge", "lfo_soft_gate", "lfo_double_pump", "lfo_ratchet", "lfo_glide_stair", "lfo_morph", "lfo_flower", "rhythm_euclid_3_8", "rhythm_euclid_5_12", "rhythm_three_two", "rhythm_half_time", "rudiment_double_paradiddle", "rudiment_paradiddle_diddle", "rudiment_six_stroke", "rudiment_flam_accent", "ease_rebound", "ease_anticipate", "ease_overshoot", "ease_elastic", "akwf_round_saw", "akwf_quick_return", "akwf_multi_lobe", "akwf_plateau", "groove_a_played", "groove_a_grid", "groove_b_played", "groove_b_grid"};
Sampler samplers[] = {dancerudiments_initial::sample_lfo_breathe, dancerudiments_initial::sample_lfo_surge, dancerudiments_initial::sample_lfo_soft_gate, dancerudiments_initial::sample_lfo_double_pump, dancerudiments_initial::sample_lfo_ratchet, dancerudiments_initial::sample_lfo_glide_stair, dancerudiments_initial::sample_lfo_morph, dancerudiments_initial::sample_lfo_flower, dancerudiments_initial::sample_rhythm_euclid_3_8, dancerudiments_initial::sample_rhythm_euclid_5_12, dancerudiments_initial::sample_rhythm_three_two, dancerudiments_initial::sample_rhythm_half_time, dancerudiments_initial::sample_rudiment_double_paradiddle, dancerudiments_initial::sample_rudiment_paradiddle_diddle, dancerudiments_initial::sample_rudiment_six_stroke, dancerudiments_initial::sample_rudiment_flam_accent, dancerudiments_initial::sample_ease_rebound, dancerudiments_initial::sample_ease_anticipate, dancerudiments_initial::sample_ease_overshoot, dancerudiments_initial::sample_ease_elastic, dancerudiments_initial::sample_akwf_round_saw, dancerudiments_initial::sample_akwf_quick_return, dancerudiments_initial::sample_akwf_multi_lobe, dancerudiments_initial::sample_akwf_plateau, dancerudiments_initial::sample_groove_a_played, dancerudiments_initial::sample_groove_a_grid, dancerudiments_initial::sample_groove_b_played, dancerudiments_initial::sample_groove_b_grid};
void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
int main() {
  auto bank=dancerudiments_initial::make_library();
  require(dancerudiments::catalogue().size()==323, "Approved defaults missing");
  require(bank.catalogue().size()==323, "Legacy loader duplicated defaults");
  require(pattern_count()==28, "Wrong preview count");
  long checked=0;
  for (int i=0; i<pattern_count(); ++i) {
    const int n=pattern_period(i);
    auto check=[&](int pip) {
      auto a=dancerudiments::sample(names[i],pip), b=samplers[i](pip);
      const auto legacy=bank.sample(names[i],pip);
      require(a.x==legacy.x && a.y==legacy.y && a.z==legacy.z, "Legacy load drift");
      double expected[3]={a.x,a.y,a.z}, direct[3]={b.x,b.y,b.z};
      for (int axis=0;axis<3;++axis) {
        double value=sample_component(i,pip,axis);
        require(value==expected[axis] && value==direct[axis], "Native sample disagreement");
        require(std::isfinite(value) && std::abs(value)<=1, "Invalid component");
        ++checked;
      }
    };
    for(int pip=-n;pip<n;++pip) check(pip);
    check(std::numeric_limits<int>::min()); check(std::numeric_limits<int>::max());
    check(n);check(-2*n);
  }
  require(std::isnan(sample_component(-1,0,0)), "Invalid pattern must return NaN");
  require(std::isnan(sample_component(0,0,3)), "Invalid axis must return NaN");
  require(pattern_period(-1)==0, "Invalid period");
  std::cout << "Native initial collection parity: " << checked << " component comparisons passed\n";
}
