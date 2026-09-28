#include "dancerudiments/dance_rudiments.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <initializer_list>

namespace dancerudiments {
namespace {
constexpr double pi = 3.14159265358979323846;

double phase(int pip, int period) noexcept {
  return static_cast<double>(wrap_pip(pip, period)) / static_cast<double>(period);
}

double smooth(double t) noexcept { return t * t * (3.0 - 2.0 * t); }

double lerp(double a, double b, double t) noexcept { return a + (b - a) * smooth(t); }

struct ClayKey { int pip; double x; double y; };

constexpr std::array<ClayKey, 14> clay_keys{{
  {0, 0.0, 0.0}, {23, 2.0 / 14.0, -1.0 / 10.0},
  {33, 13.0 / 14.0, -8.0 / 10.0}, {49, 5.0 / 14.0, -4.0 / 10.0},
  {87, -3.0 / 14.0, 2.0 / 10.0}, {100, -1.0, 9.0 / 10.0},
  {118, -5.0 / 14.0, 5.0 / 10.0}, {154, 1.0 / 14.0, 0.0},
  {169, 12.0 / 14.0, 1.0}, {187, 4.0 / 14.0, 5.0 / 10.0},
  {215, -2.0 / 14.0, -2.0 / 10.0}, {228, -10.0 / 14.0, -9.0 / 10.0},
  {243, -3.0 / 14.0, -3.0 / 10.0}, {256, 0.0, 0.0}
}};

std::array<Offset3, 256> make_clay_table() {
  std::array<Offset3, 256> table{};
  std::size_t segment = 0;
  for (int pip = 0; pip < 256; ++pip) {
    while (segment + 1 < clay_keys.size() && pip > clay_keys[segment + 1].pip) ++segment;
    const auto& a = clay_keys[segment];
    const auto& b = clay_keys[segment + 1];
    const double t = static_cast<double>(pip - a.pip) / static_cast<double>(b.pip - a.pip);
    table[static_cast<std::size_t>(pip)] = {lerp(a.x, b.x, t), lerp(a.y, b.y, t), 0.0};
  }
  return table;
}

const auto clay_table = make_clay_table();

struct Stroke { int pip; int hand; double strength; int width; };

double stroke_envelope(int pip, int period, const Stroke& stroke) noexcept {
  const int distance = wrap_pip(pip - stroke.pip, period);
  if (distance >= stroke.width) return 0.0;
  const double u = static_cast<double>(distance) / static_cast<double>(stroke.width);
  const double s = std::sin(pi * u);
  return stroke.strength * s * s;
}

Offset3 stroke_motion(int pip, int period, std::initializer_list<Stroke> strokes) noexcept {
  double x = 0.0;
  double y = 0.0;
  for (const auto& stroke : strokes) {
    const double amount = stroke_envelope(pip, period, stroke);
    x += static_cast<double>(stroke.hand) * amount;
    y -= amount * 0.72;
  }
  return {std::clamp(x, -1.0, 1.0), std::clamp(y, -1.0, 1.0), 0.0};
}
}

int wrap_pip(int pip_count, int period_pips) noexcept {
  if (period_pips <= 0) return 0;
  const int wrapped = pip_count % period_pips;
  return wrapped < 0 ? wrapped + period_pips : wrapped;
}

Offset3 bounce(int pip_count) noexcept {
  const double p = phase(pip_count, 64);
  const double triangle = 1.0 - 4.0 * std::abs(p - 0.5);
  return {triangle, 0.0, 0.0};
}

Offset3 sway(int pip_count) noexcept {
  return {std::sin(2.0 * pi * phase(pip_count, 128)), 0.0, 0.0};
}

Offset3 circle(int pip_count) noexcept {
  const double a = 2.0 * pi * phase(pip_count, 64) - pi / 2.0;
  return {std::cos(a), std::sin(a), 0.0};
}

Offset3 figure_eight(int pip_count) noexcept {
  const double a = 2.0 * pi * phase(pip_count, 128);
  return {std::sin(a), std::sin(2.0 * a), 0.0};
}

Offset3 step_touch(int pip_count) noexcept {
  const int pip = wrap_pip(pip_count, 128);
  const int quarter = pip / 32;
  const double t = (pip % 32) / 32.0;
  const double x0[] = {-1.0, 0.0, 1.0, 0.0};
  const double x1[] = {0.0, 1.0, 0.0, -1.0};
  const double lift = std::sin(pi * t) * 0.35;
  return {lerp(x0[quarter], x1[quarter], t), -lift, 0.0};
}

Offset3 box_step(int pip_count) noexcept {
  const int pip = wrap_pip(pip_count, 256);
  const int edge = pip / 64;
  const double t = (pip % 64) / 64.0;
  constexpr double x0[] = {-1.0, 1.0, 1.0, -1.0};
  constexpr double y0[] = {-1.0, -1.0, 1.0, 1.0};
  constexpr double x1[] = {1.0, 1.0, -1.0, -1.0};
  constexpr double y1[] = {-1.0, 1.0, 1.0, -1.0};
  return {lerp(x0[edge], x1[edge], t), lerp(y0[edge], y1[edge], t), 0.0};
}

Offset3 helix(int pip_count) noexcept {
  const double p = phase(pip_count, 256);
  const double a = 4.0 * pi * p;
  return {std::cos(a), std::sin(a), std::sin(2.0 * pi * p)};
}

Offset3 clay_background(int pip_count) noexcept {
  return clay_table[static_cast<std::size_t>(wrap_pip(pip_count, 256))];
}

Offset3 single_stroke_roll(int pip) noexcept {
  return stroke_motion(pip, 64, {{0,1,.92,8},{8,-1,.92,8},{16,1,.92,8},{24,-1,.92,8},
    {32,1,.92,8},{40,-1,.92,8},{48,1,.92,8},{56,-1,.92,8}});
}

Offset3 double_stroke_roll(int pip) noexcept {
  return stroke_motion(pip, 64, {{0,1,.88,8},{8,1,.72,8},{16,-1,.88,8},{24,-1,.72,8},
    {32,1,.88,8},{40,1,.72,8},{48,-1,.88,8},{56,-1,.72,8}});
}

Offset3 multiple_bounce_roll(int pip) noexcept {
  return stroke_motion(pip, 64, {{0,1,.92,6},{6,1,.68,6},{12,1,.48,6},{18,1,.32,6},
    {32,-1,.92,6},{38,-1,.68,6},{44,-1,.48,6},{50,-1,.32,6}});
}

Offset3 single_paradiddle(int pip) noexcept {
  return stroke_motion(pip, 128, {{0,1,1,8},{8,-1,.72,8},{16,1,.72,8},{24,1,.72,8},
    {32,-1,1,8},{40,1,.72,8},{48,-1,.72,8},{56,-1,.72,8},
    {64,1,1,8},{72,-1,.72,8},{80,1,.72,8},{88,1,.72,8},
    {96,-1,1,8},{104,1,.72,8},{112,-1,.72,8},{120,-1,.72,8}});
}

Offset3 flam(int pip) noexcept {
  return stroke_motion(pip, 64, {{0,-1,.34,10},{5,1,.9,14},{32,1,.34,10},{37,-1,.9,14}});
}

Offset3 drag(int pip) noexcept {
  return stroke_motion(pip, 64, {{0,-1,.28,8},{5,-1,.32,8},{10,1,.88,14},
    {32,1,.28,8},{37,1,.32,8},{42,-1,.88,14}});
}

Offset3 five_stroke_roll(int pip) noexcept {
  return stroke_motion(pip, 128, {{0,1,.72,9},{8,1,.62,9},{16,-1,.72,9},{24,-1,.62,9},{36,1,1,14},
    {64,-1,.72,9},{72,-1,.62,9},{80,1,.72,9},{88,1,.62,9},{100,-1,1,14}});
}

const std::vector<RudimentInfo>& catalogue() {
  static const std::vector<RudimentInfo> entries{
    {"bounce", "One-beat vertical bounce", 64, Dimension::one},
    {"sway", "Two-beat side-to-side sway", 128, Dimension::one},
    {"circle", "One-beat circular orbit", 64, Dimension::two},
    {"figure_eight", "Two-beat figure eight", 128, Dimension::two},
    {"step_touch", "Two-beat side step with a small lift", 128, Dimension::two},
    {"box_step", "Four-beat softened square path", 256, Dimension::two},
    {"helix", "Four-beat double-turn helix", 256, Dimension::three},
    {"clay_background", "Clay/Stars four-beat accented background drift", 256, Dimension::two},
    {"single_stroke_roll", "Alternating R/L strokes with smooth attack and decay", 64, Dimension::two},
    {"double_stroke_roll", "RRLL strokes with a softer second motion", 64, Dimension::two},
    {"multiple_bounce_roll", "Decaying same-hand bounce clusters", 64, Dimension::two},
    {"single_paradiddle", "RLRR LRLL with accented lead strokes", 128, Dimension::two},
    {"flam", "Grace motion flowing into an opposite-hand primary motion", 64, Dimension::two},
    {"drag", "Two grace motions flowing into an opposite-hand primary motion", 64, Dimension::two},
    {"five_stroke_roll", "Two diddles resolving to an accented fifth motion", 128, Dimension::two}
  };
  return entries;
}

Offset3 sample(std::string_view name, int pip_count) {
  if (name == "bounce") return bounce(pip_count);
  if (name == "sway") return sway(pip_count);
  if (name == "circle") return circle(pip_count);
  if (name == "figure_eight") return figure_eight(pip_count);
  if (name == "step_touch") return step_touch(pip_count);
  if (name == "box_step") return box_step(pip_count);
  if (name == "helix") return helix(pip_count);
  if (name == "clay_background") return clay_background(pip_count);
  if (name == "single_stroke_roll") return single_stroke_roll(pip_count);
  if (name == "double_stroke_roll") return double_stroke_roll(pip_count);
  if (name == "multiple_bounce_roll") return multiple_bounce_roll(pip_count);
  if (name == "single_paradiddle") return single_paradiddle(pip_count);
  if (name == "flam") return flam(pip_count);
  if (name == "drag") return drag(pip_count);
  if (name == "five_stroke_roll") return five_stroke_roll(pip_count);
  throw std::invalid_argument("Unknown dance rudiment: " + std::string(name));
}
} // namespace dancerudiments
