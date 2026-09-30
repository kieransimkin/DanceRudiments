// MIT. Kieran Simkin — https://kieransimkin.co.uk/my-songs/
#include "dancerudiments/c_api.h"
#include "dancerudiments/sampled_pattern.hpp"
#include <algorithm>
#include <cstring>
#include <limits>
#include <memory>
#include <new>
#include <stdexcept>
#include <string>
#include <utility>

#ifndef DANCERUDIMENTS_C_VERSION
# error The C ABI must be built with a project version
#endif
namespace d = dancerudiments;
struct dr_library {
  d::PatternLibrary bank;
  std::vector<d::RudimentInfo> info;
  explicit dr_library(std::vector<d::SampledPattern> patterns)
    : bank(std::move(patterns)), info(bank.catalogue()) {}
};
namespace {
thread_local char error_text[1024] = {};
void set_error(const char* message) noexcept {
  std::size_t i = 0;
  if (message) for (; i + 1 < sizeof(error_text) && message[i]; ++i) error_text[i] = message[i];
  error_text[i] = '\0';
}
template<class F> dr_status protect(F&& action) noexcept {
  error_text[0] = '\0';
  try { action(); return DR_OK; }
  catch (const std::invalid_argument& e) { set_error(e.what()); return DR_INVALID_ARGUMENT; }
  catch (const std::out_of_range& e) { set_error(e.what()); return DR_OUT_OF_RANGE; }
  catch (const std::bad_alloc&) { set_error("Native allocation failed"); return DR_OUT_OF_MEMORY; }
  catch (const std::exception& e) { set_error(e.what()); return DR_INTERNAL_ERROR; }
  catch (...) { set_error("Unknown native error"); return DR_INTERNAL_ERROR; }
}
void require(bool ok, const char* message) {
  if (!ok) throw std::invalid_argument(message);
}
void name_ok(const char* name) {
  require(name && *name, "A pattern name is required");
}
void copy_info(const std::vector<d::RudimentInfo>& info, uint32_t index, dr_info* out) {
  require(out, "A metadata output pointer is required");
  if (index >= info.size()) throw std::out_of_range("Catalogue index is out of range");
  const auto& v = info[index];
  // The underlying catalogue owns strings (custom) or uses string literals (defaults).
  *out = {v.name.data(), v.description.data(), v.period_pips, static_cast<uint32_t>(v.dimensions)};
}
int period(const std::vector<d::RudimentInfo>& info, const char* name) {
  name_ok(name);
  const auto found = std::find_if(info.begin(), info.end(),
    [name](const d::RudimentInfo& v) { return v.name == name; });
  if (found == info.end()) throw std::invalid_argument("Unknown dance rudiment: " + std::string(name));
  return found->period_pips;
}
dr_offset3 offset(d::Offset3 v) noexcept { return {v.x, v.y, v.z}; }
template<class Sampler>
void batch(const std::vector<d::RudimentInfo>& info, const char* name, int32_t start,
           int32_t step, uint32_t count, dr_offset3* out, Sampler&& sampler) {
  require(count <= d::max_pack_samples, "Batch exceeds the sample limit");
  require(count == 0 || out, "A batch output buffer is required");
  const int n = period(info, name); // Validate everything BEFORE writing any output.
  for (uint32_t i = 0; i < count; ++i) {
    int64_t p = (static_cast<int64_t>(start) + static_cast<int64_t>(step) * i) % n;
    if (p < 0) p += n;
    out[i] = offset(sampler(static_cast<int>(p)));
  }
}
}
extern "C" {
uint32_t DR_CALL dr_abi_version() noexcept { return 1; }
uint32_t DR_CALL dr_pips_per_beat() noexcept { return d::pips_per_beat; }
const char* DR_CALL dr_version() noexcept { return DANCERUDIMENTS_C_VERSION; }
const char* DR_CALL dr_last_error() noexcept { return error_text; }
dr_status DR_CALL dr_catalogue_count(uint32_t* count) noexcept {
  return protect([&] { require(count, "A count output pointer is required");
    *count = static_cast<uint32_t>(d::catalogue().size()); });
}
dr_status DR_CALL dr_catalogue_get(uint32_t index, dr_info* info) noexcept {
  return protect([&] { copy_info(d::catalogue(), index, info); });
}
dr_status DR_CALL dr_sample(const char* name, int32_t pip, dr_offset3* value) noexcept {
  return protect([&] { name_ok(name); require(value, "An output pointer is required");
    *value = offset(d::sample(name, pip)); });
}
dr_status DR_CALL dr_sample_many(const char* name, int32_t start, int32_t step,
                                uint32_t count, dr_offset3* values) noexcept {
  return protect([&] { batch(d::catalogue(), name, start, step, count, values,
    [&](int pip) { return d::sample(name, pip); }); });
}
dr_status DR_CALL dr_library_create(const dr_pattern_definition* definitions,
                                   uint32_t count, dr_library** result) noexcept {
  if (result) *result = nullptr;
  return protect([&] {
    require(result, "A library output pointer is required");
    require(count <= d::max_pack_patterns, "Too many patterns");
    require(count == 0 || definitions, "Pattern definitions are required");
    std::size_t total = 0;
    // Validate sizes before allocating or reading the sample buffers.
    for (uint32_t i = 0; i < count; ++i) {
      const auto& p = definitions[i];
      require(p.name && p.description && p.samples, "A definition contains a NULL pointer");
      require(p.count > 0 && p.count <= d::max_pattern_samples, "Invalid pattern sample count");
      total += p.count;
      require(total <= d::max_pack_samples, "Pattern pack is too large");
    }
    std::vector<d::SampledPattern> patterns;
    patterns.reserve(count);
    for (uint32_t i = 0; i < count; ++i) {
      const auto& p = definitions[i];
      std::vector<d::Offset3> values;
      values.reserve(p.count);
      for (uint32_t j = 0; j < p.count; ++j) values.push_back({p.samples[j].x,p.samples[j].y,p.samples[j].z});
      patterns.emplace_back(p.name, p.description, std::move(values));
    }
    *result = new dr_library(std::move(patterns));
  });
}
void DR_CALL dr_library_destroy(dr_library* library) noexcept { delete library; }
dr_status DR_CALL dr_library_count(const dr_library* library, uint32_t* count) noexcept {
  return protect([&] { require(library && count, "Library and count pointer are required");
    *count = static_cast<uint32_t>(library->info.size()); });
}
dr_status DR_CALL dr_library_get(const dr_library* library, uint32_t index, dr_info* info) noexcept {
  return protect([&] { require(library, "A library handle is required"); copy_info(library->info,index,info); });
}
dr_status DR_CALL dr_library_sample(const dr_library* library, const char* name,
                                   int32_t pip, dr_offset3* value) noexcept {
  return protect([&] { require(library && value, "Library and output pointer are required");
    name_ok(name); *value = offset(library->bank.sample(name, pip)); });
}
dr_status DR_CALL dr_library_sample_many(const dr_library* library, const char* name,
                                        int32_t start, int32_t step, uint32_t count,
                                        dr_offset3* values) noexcept {
  return protect([&] { require(library, "A library handle is required");
    batch(library->info, name, start, step, count, values,
      [&](int pip) { return library->bank.sample(name, pip); }); });
}
}
