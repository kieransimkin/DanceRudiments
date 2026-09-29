#include "dancerudiments/sampled_pattern.hpp"

#include <cmath>
#include <stdexcept>
#include <unordered_set>
#include <utility>

namespace dancerudiments {
namespace {
bool valid_name(std::string_view name) {
  if (name.empty() || name.size() > 128 || name[0] < 'a' || name[0] > 'z') return false;
  for (const char c : name) {
    if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_')) return false;
  }
  return true;
}
}

SampledPattern::SampledPattern(std::string name, std::string description,
                               std::vector<Offset3> samples)
    : name_(std::move(name)), description_(std::move(description)), samples_(std::move(samples)) {
  if (!valid_name(name_)) throw std::invalid_argument("Invalid pattern name");
  if (samples_.empty() || samples_.size() > max_pattern_samples)
    throw std::invalid_argument("A pattern requires 1..65535 samples (one per pip)");
  for (const auto& v : samples_) {
    for (const double component : {v.x, v.y, v.z}) {
      if (!std::isfinite(component) || component < -1.0 || component > 1.0)
        throw std::invalid_argument("Pattern samples must be finite and within [-1, 1]");
    }
    if (v.z != 0.0) dimensions_ = Dimension::three;
    else if (v.y != 0.0 && dimensions_ != Dimension::three) dimensions_ = Dimension::two;
  }
}

RudimentInfo SampledPattern::info() const noexcept {
  return {name_, description_, static_cast<std::uint16_t>(samples_.size()), dimensions_};
}

Offset3 SampledPattern::sample(int pip_count) const {
  if (samples_.empty()) throw std::logic_error("Cannot sample a moved-from pattern");
  return samples_[static_cast<std::size_t>(wrap_pip(pip_count, period_pips()))];
}

PatternLibrary::PatternLibrary(std::vector<SampledPattern> patterns)
    : patterns_(std::move(patterns)) {
  if (patterns_.size() > max_pack_patterns) throw std::invalid_argument("Too many patterns");
  std::unordered_set<std::string> names;
  for (const auto& item : dancerudiments::catalogue()) names.emplace(item.name);
  std::size_t total = 0;
  for (const auto& item : patterns_) {
    if (item.period_pips() == 0) throw std::invalid_argument("Empty/moved-from pattern");
    if (!names.insert(item.name()).second)
      throw std::invalid_argument("Duplicate or built-in pattern name: " + item.name());
    total += static_cast<std::size_t>(item.period_pips());
    if (total > max_pack_samples) throw std::invalid_argument("Pattern pack is too large");
  }
}

Offset3 PatternLibrary::sample(std::string_view name, int pip_count) const {
  for (const auto& item : patterns_) if (item.name() == name) return item.sample(pip_count);
  return dancerudiments::sample(name, pip_count);
}

std::vector<RudimentInfo> PatternLibrary::catalogue() const {
  auto result = dancerudiments::catalogue();
  result.reserve(result.size() + patterns_.size());
  for (const auto& item : patterns_) result.push_back(item.info());
  return result;
}
} // namespace dancerudiments
