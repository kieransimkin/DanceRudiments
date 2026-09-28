#include <dancerudiments/dance_rudiments.hpp>

int main() {
  const auto sample = dancerudiments::sample("circle", 64);
  return (sample.x == 1.0 && sample.y == 0.0) ? 0 : 1;
}
