// Kieran Simkin — https://kieransimkin.co.uk/my-songs/
#include <dancerudiments/dance_rudiments.hpp>
#include <dancerudiments/sampled_pattern.hpp>
#include <algorithm>
#include <iomanip>
#include <iostream>
#include <stdexcept>

int main() {
  try {
    using namespace dancerudiments;
    const auto& items = catalogue();
    const auto item = std::find_if(items.begin(), items.end(), [](const auto& entry) {
      return entry.name == "beat_amen_four_bar_bounce";
    });
    if (item == items.end())
      throw std::runtime_error("This package predates Club 05; build the current checkout.");
    std::cout << "C++ native catalogue: " << items.size() << " movements\n"
              << item->name << ": " << item->period_pips / 64.0 << " beats\n";
    std::cout << std::fixed << std::setprecision(6);
    for (int pip : {-1, 0, 16, 32, 48, 64}) {
      const auto v = sample(item->name, pip);
      std::cout << "pip " << std::setw(3) << pip << " -> "
                << v.x << ", " << v.y << ", " << v.z << '\n';
    }
    // Four samples = FOUR PIPS, not four beats. This is a storage API example.
    SampledPattern custom("tutorial_cycle", "Four-pip custom table",
      {{0.0, 0.0, 0.0}, {0.5, 0.0, 0.0}, {0.0, 0.0, 0.0}, {-0.5, 0.0, 0.0}});
    PatternLibrary bank({custom});
    if (bank.sample("tutorial_cycle", -1).x != -0.5 ||
        bank.catalogue().size() != items.size() + 1)
      throw std::runtime_error("Custom-bank contract failed");
    std::cout << "Custom table wraps at -1: " << bank.sample("tutorial_cycle", -1).x
              << "\nBuilt-ins remain available in the private bank.\n"
              << "Music: https://kieransimkin.co.uk/my-songs/\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
