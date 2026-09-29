// MIT. Export exact samples from the linked native catalogue for release demos.
#include "dancerudiments/dance_rudiments.hpp"
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <stdexcept>
#include <string_view>

static void quoted(std::string_view s) {
  std::cout << '"';
  for (const unsigned char c : s) {
    if (c == '"' || c == '\\') std::cout << '\\' << c;
    else if (c < 32) {
      const char* hex = "0123456789abcdef";
      std::cout << "\\u00" << hex[c >> 4] << hex[c & 15];
    } else std::cout << c;
  }
  std::cout << '"';
}
int main() {
  try {
    std::cout.imbue(std::locale::classic());
    std::cout << std::setprecision(std::numeric_limits<double>::max_digits10);
    std::cout << "{\"pips_per_beat\":64,\"patterns\":[";
    bool first = true;
    for (const auto& p : dancerudiments::catalogue()) {
      if (!first) std::cout << ',';
      first = false;
      std::cout << "{\"name\":"; quoted(p.name);
      std::cout << ",\"description\":"; quoted(p.description);
      std::cout << ",\"period_pips\":" << p.period_pips
                << ",\"dimensions\":" << static_cast<int>(p.dimensions) << ",\"samples\":[";
      if (p.period_pips == 0) throw std::runtime_error("Zero period in native catalogue");
      for (int pip = 0; pip < p.period_pips; ++pip) {
        const auto v = dancerudiments::sample(p.name, pip);
        if (!std::isfinite(v.x) || !std::isfinite(v.y) || !std::isfinite(v.z) ||
            std::abs(v.x)>1 || std::abs(v.y)>1 || std::abs(v.z)>1)
          throw std::runtime_error("Invalid native sample");
        if (pip) std::cout << ',';
        std::cout << '[' << v.x << ',' << v.y << ',' << v.z << ']';
      }
      std::cout << "]}";
    }
    std::cout << "]}\n";
    return std::cout ? 0 : 1;
  } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
