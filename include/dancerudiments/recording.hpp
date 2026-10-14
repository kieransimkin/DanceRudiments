#pragma once
#include "dancerudiments/recording_view.hpp"
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>
namespace dancerudiments {
static_assert(sizeof(double)==8 && std::numeric_limits<double>::is_iec559, "Recordings require IEEE-754 binary64");
class SampledRecording {
 public:
  SampledRecording(std::string name, std::vector<std::string> dimensions,
                   const std::vector<std::vector<double>>& samples, double bpm,
                   double beat_zero_seconds=0., int start_pip=0)
      : name_(std::move(name)), dimensions_(std::move(dimensions)), bpm_(bpm), origin_(beat_zero_seconds), first_(start_pip) {
    validate_name(name_);
    if (!std::isfinite(bpm) || bpm<=0 || !std::isfinite(60./bpm) || 60./bpm/64<=0 || !std::isfinite(origin_))
      throw std::invalid_argument("A finite positive BPM and beat origin are required");
    if (dimensions_.empty() || dimensions_.size()>8388608 || samples.empty() || samples.size()>8388608/dimensions_.size() ||
        static_cast<long long>(first_)+static_cast<long long>(samples.size())>2147483647)
      throw std::invalid_argument("Empty recording or recording resource limit exceeded");
    std::unordered_set<std::string> seen;
    for (const auto& d : dimensions_) { validate_name(d); if (!seen.insert(d).second) throw std::invalid_argument("Duplicate axis"); }
    values_.reserve(samples.size()*dimensions_.size());
    for (const auto& row : samples) {
      if (row.size()!=dimensions_.size()) throw std::invalid_argument("Ragged recording");
      for (double v : row) { if (!std::isfinite(v) || std::abs(v)>1) throw std::invalid_argument("Invalid sample"); values_.push_back(v); }
    }
  }
  const std::string& name() const noexcept { return name_; }
  const std::vector<std::string>& dimensions() const noexcept { return dimensions_; }
  int sample_count() const noexcept { return dimensions_.empty()?0:static_cast<int>(values_.size()/dimensions_.size()); }
  double bpm() const noexcept { return bpm_; }
  double beat_zero_seconds() const noexcept { return origin_; }
  int start_pip() const noexcept { return first_; }
  std::vector<double> sample(int pip) const {
    if (pip<first_ || static_cast<long long>(pip)-first_>=sample_count()) throw std::out_of_range("Pip outside non-looping recording");
    std::vector<double> result; result.reserve(dimensions_.size());
    for (int axis=0;axis<static_cast<int>(dimensions_.size());++axis)
      result.push_back(recording_component(values_.data(),sample_count(),static_cast<int>(dimensions_.size()),first_,pip,axis));
    return result;
  }
 private:
  static void validate_name(const std::string& s) {
    if (s.empty() || s.size()>128 || s[0]<'a' || s[0]>'z') throw std::invalid_argument("Invalid identifier");
    for (char c:s) if (!(c>='a'&&c<='z') && !(c>='0'&&c<='9') && c!='_') throw std::invalid_argument("Invalid identifier");
  }
  std::string name_; std::vector<std::string> dimensions_; std::vector<double> values_;
  double bpm_,origin_; int first_;
};
}
