#pragma once
#if defined(_MSC_VER)
#include <limits>
#endif
// Shared native/WASM table accessor. Non-looping; invalid positions return NaN.
// No standard-library or JavaScript movement implementation is required.
namespace dancerudiments {
inline double recording_component(const double* values, int count, int dimensions,
                                  int first_pip, int pip, int axis) noexcept {
  const long long row = static_cast<long long>(pip) - first_pip;
  if (!values || count < 1 || dimensions < 1 || axis < 0 || axis >= dimensions || row < 0 || row >= count)
#if defined(_MSC_VER)
    return std::numeric_limits<double>::quiet_NaN();
#else
    return __builtin_nan("");
#endif
  return values[row * dimensions + axis];
}
}
