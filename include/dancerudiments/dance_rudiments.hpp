#pragma once

#include <array>
#include <cstdint>
#include <string_view>
#include <vector>

namespace dancerudiments {

struct Offset3 {
  double x{0.0};
  double y{0.0};
  double z{0.0};
};

enum class Dimension : std::uint8_t { one = 1, two = 2, three = 3 };

struct RudimentInfo {
  std::string_view name;
  std::string_view description;
  std::uint16_t period_pips;
  Dimension dimensions;
};

// Every public sampler wraps pip_count into [0, period_pips), including negatives.
// Offsets are dimensionless and normally bounded to [-1, 1]. Scale them at the call site.
int wrap_pip(int pip_count, int period_pips) noexcept;
const std::vector<RudimentInfo>& catalogue();
Offset3 sample(std::string_view name, int pip_count);

Offset3 bounce(int pip_count) noexcept;       // 1D, 64 pips
Offset3 sway(int pip_count) noexcept;         // 1D, 128 pips
Offset3 circle(int pip_count) noexcept;       // 2D, 64 pips
Offset3 figure_eight(int pip_count) noexcept; // 2D, 128 pips
Offset3 step_touch(int pip_count) noexcept;   // 2D, 128 pips
Offset3 box_step(int pip_count) noexcept;     // 2D, 256 pips
Offset3 helix(int pip_count) noexcept;        // 3D, 256 pips
Offset3 clay_background(int pip_count) noexcept; // 2D LUT, 256 pips
Offset3 single_stroke_roll(int pip_count) noexcept; // 2D, 64 pips
Offset3 double_stroke_roll(int pip_count) noexcept; // 2D, 64 pips
Offset3 multiple_bounce_roll(int pip_count) noexcept; // 2D, 64 pips
Offset3 single_paradiddle(int pip_count) noexcept;  // 2D, 128 pips
Offset3 flam(int pip_count) noexcept;               // 2D, 64 pips
Offset3 drag(int pip_count) noexcept;               // 2D, 64 pips
Offset3 five_stroke_roll(int pip_count) noexcept;   // 2D, 128 pips

} // namespace dancerudiments
