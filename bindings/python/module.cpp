#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <utility>
#include "dancerudiments/dance_rudiments.hpp"
#include "dancerudiments/sampled_pattern.hpp"

namespace py = pybind11;
using namespace dancerudiments;
using namespace pybind11::literals;

PYBIND11_MODULE(dancerudiments, m) {
  m.doc() = "Integer-pip rhythmic position functions";
  m.attr("PIPS_PER_BEAT") = pips_per_beat;
  py::class_<Offset3>(m, "Offset3")
    .def_readonly("x", &Offset3::x).def_readonly("y", &Offset3::y).def_readonly("z", &Offset3::z)
    .def("as_tuple", [](const Offset3& v) { return py::make_tuple(v.x, v.y, v.z); });
  py::class_<SampledPattern>(m, "SampledPattern")
    .def(py::init([](std::string name, std::string description,
                    const std::vector<std::array<double, 3>>& values) {
      std::vector<Offset3> samples;
      samples.reserve(values.size());
      for (const auto& v : values) samples.push_back({v[0], v[1], v[2]});
      return SampledPattern(std::move(name), std::move(description), std::move(samples));
    }), py::arg("name"), py::arg("description"), py::arg("samples"))
    .def_property_readonly("name", &SampledPattern::name)
    .def_property_readonly("description", &SampledPattern::description)
    .def_property_readonly("period_pips", &SampledPattern::period_pips)
    .def("sample", &SampledPattern::sample, py::arg("pip_count").noconvert());
  py::class_<PatternLibrary>(m, "PatternLibrary")
    .def(py::init<std::vector<SampledPattern>>(), py::arg("patterns") = std::vector<SampledPattern>{})
    .def("sample", &PatternLibrary::sample, py::arg("name"), py::arg("pip_count").noconvert())
    .def("catalogue", [](const PatternLibrary& library) {
      py::list result;
      for (const auto& item : library.catalogue()) {
        result.append(py::dict("name"_a=std::string(item.name),
          "description"_a=std::string(item.description), "period_pips"_a=item.period_pips,
          "dimensions"_a=static_cast<int>(item.dimensions)));
      }
      return result;
    });
  m.def("sample", &sample, py::arg("name"), py::arg("pip_count"));
  m.def("catalogue", [] {
    py::list result;
    for (const auto& item : catalogue()) {
      result.append(py::dict("name"_a=item.name, "description"_a=item.description,
        "period_pips"_a=item.period_pips, "dimensions"_a=static_cast<int>(item.dimensions)));
    }
    return result;
  });
  m.def("bounce", &bounce); m.def("sway", &sway); m.def("circle", &circle);
  m.def("figure_eight", &figure_eight); m.def("step_touch", &step_touch);
  m.def("box_step", &box_step); m.def("helix", &helix); m.def("clay_background", &clay_background);
  m.def("single_stroke_roll", &single_stroke_roll); m.def("double_stroke_roll", &double_stroke_roll);
  m.def("multiple_bounce_roll", &multiple_bounce_roll);
  m.def("single_paradiddle", &single_paradiddle); m.def("flam", &flam); m.def("drag", &drag);
  m.def("five_stroke_roll", &five_stroke_roll);
}
