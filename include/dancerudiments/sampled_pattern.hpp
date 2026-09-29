#pragma once

#include "dancerudiments/dance_rudiments.hpp"
#include <cstddef>
#include <string>

namespace dancerudiments {

inline constexpr int pips_per_beat = 64;
inline constexpr std::size_t max_pattern_samples = 65535;
inline constexpr std::size_t max_pack_patterns = 1024;
inline constexpr std::size_t max_pack_samples = 1048576;

// Generated C++ functions use this allocation-free sampler. No interpolation,
// clock, random state or Python is involved in playback.
template <std::size_t N>
Offset3 sample_table(const std::array<Offset3, N>& table, int pip_count) noexcept {
  static_assert(N > 0 && N <= max_pattern_samples, "Invalid pattern period");
  return table[static_cast<std::size_t>(wrap_pip(pip_count, static_cast<int>(N)))];
}

// Owns a validated table, copied at construction. The public API is read-only.
// Reading a moved-from object throws rather than indexing an empty vector.
class SampledPattern {
 public:
  SampledPattern(std::string name, std::string description, std::vector<Offset3> samples);
  const std::string& name() const noexcept { return name_; }
  const std::string& description() const noexcept { return description_; }
  int period_pips() const noexcept { return static_cast<int>(samples_.size()); }
  RudimentInfo info() const noexcept;
  Offset3 sample(int pip_count) const;

 private:
  std::string name_;
  std::string description_;
  std::vector<Offset3> samples_;
  Dimension dimensions_{Dimension::one};
};

// Explicit, independent banks: never modifies the global built-in catalogue.
// Custom names must be unique and must not shadow built-ins. Exact copies of
// defaults are accepted idempotently for legacy pack loaders. All construction
// is complete before publication, so concurrent read-only sampling is safe.
class PatternLibrary {
 public:
  explicit PatternLibrary(std::vector<SampledPattern> patterns = {});
  Offset3 sample(std::string_view name, int pip_count) const;
  // Returned string_views remain valid while this library remains alive and
  // is not moved from or assigned to. Bindings copy the strings before return.
  std::vector<RudimentInfo> catalogue() const;

 private:
  std::vector<SampledPattern> patterns_;
};

} // namespace dancerudiments
