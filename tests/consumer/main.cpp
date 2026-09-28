#include <dancerudiments/dance_rudiments.hpp>
#include <cmath>

int main() {
  const auto start = dancerudiments::sample("circle", 0);
  const auto wrapped = dancerudiments::sample("circle", 64);
  constexpr double tolerance = 1e-12;
  return (std::abs(start.x - wrapped.x) < tolerance &&
          std::abs(start.y - wrapped.y) < tolerance &&
          std::abs(start.z - wrapped.z) < tolerance)
             ? 0
             : 1;
}
