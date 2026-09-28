#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "dancerudiments/dance_rudiments.hpp"

namespace py = pybind11;
using namespace dancerudiments;
using namespace pybind11::literals;

PYBIND11_MODULE(dancerudiments, m) {
  m.doc() = "Integer-pip rhythmic position functions";
  py::class_<Offset3>(m, "Offset3")
    .def_readonly("x", &Offset3::x).def_readonly("y", &Offset3::y).def_readonly("z", &Offset3::z)
    .def("as_tuple", [](const Offset3& v) { return py::make_tuple(v.x, v.y, v.z); });
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
