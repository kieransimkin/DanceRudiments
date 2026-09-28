cmake_minimum_required(VERSION 3.20)
project(DanceRudiments VERSION 0.1.0 LANGUAGES CXX)

option(DANCERUDIMENTS_BUILD_TESTS "Build C++ tests" ON)
option(DANCERUDIMENTS_BUILD_PYTHON "Build the pybind11 Python module" OFF)
option(DANCERUDIMENTS_BUILD_WASM "Build the Emscripten JavaScript module" OFF)

add_library(DanceRudiments STATIC src/dance_rudiments.cpp)
add_library(DanceRudiments::DanceRudiments ALIAS DanceRudiments)
target_compile_features(DanceRudiments PUBLIC cxx_std_17)
target_include_directories(DanceRudiments PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)

if(DANCERUDIMENTS_BUILD_PYTHON)
  find_package(pybind11 CONFIG REQUIRED)
  pybind11_add_module(dancerudiments_python bindings/python/module.cpp)
  set_target_properties(dancerudiments_python PROPERTIES OUTPUT_NAME dancerudiments)
  target_link_libraries(dancerudiments_python PRIVATE DanceRudiments::DanceRudiments)
endif()

if(DANCERUDIMENTS_BUILD_WASM)
  if(NOT EMSCRIPTEN)
    message(FATAL_ERROR "DANCERUDIMENTS_BUILD_WASM requires Emscripten (use emcmake cmake).")
  endif()
  add_executable(dancerudiments_wasm bindings/typescript/wasm.cpp)
  target_link_libraries(dancerudiments_wasm PRIVATE DanceRudiments::DanceRudiments)
  set_target_properties(dancerudiments_wasm PROPERTIES OUTPUT_NAME dancerudiments)
  target_link_options(dancerudiments_wasm PRIVATE
    "--bind"
    "-sMODULARIZE=1"
    "-sEXPORT_ES6=1"
    "-sENVIRONMENT=web,node"
    "-sALLOW_MEMORY_GROWTH=1")
endif()

if(DANCERUDIMENTS_BUILD_TESTS)
  enable_testing()
  add_executable(dancerudiments_tests tests/cpp/test_main.cpp)
  target_link_libraries(dancerudiments_tests PRIVATE DanceRudiments::DanceRudiments)
  add_test(NAME dancerudiments_cpp COMMAND dancerudiments_tests)
endif()

include(GNUInstallDirs)
install(TARGETS DanceRudiments EXPORT DanceRudimentsTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT DanceRudimentsTargets NAMESPACE DanceRudiments::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/DanceRudiments)
