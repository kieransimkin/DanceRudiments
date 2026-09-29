cmake_minimum_required(VERSION 3.20)
project(DanceRudiments VERSION 0.1.3 LANGUAGES CXX)

option(DANCERUDIMENTS_BUILD_DEMO_TOOLS "Build the native demo exporter" OFF)
option(DANCERUDIMENTS_BUILD_TESTS "Build C++ tests" ON)
option(DANCERUDIMENTS_BUILD_PYTHON "Build the pybind11 Python module" OFF)
option(DANCERUDIMENTS_BUILD_WASM "Build the Emscripten JavaScript module" OFF)

add_library(DanceRudiments STATIC src/dance_rudiments.cpp src/sampled_pattern.cpp)
add_library(DanceRudiments::DanceRudiments ALIAS DanceRudiments)
set_target_properties(DanceRudiments PROPERTIES POSITION_INDEPENDENT_CODE ON)
if(WIN32)
  # Avoid colliding with the dancerudiments Python module's MSVC import library.
  set_target_properties(DanceRudiments PROPERTIES OUTPUT_NAME DanceRudimentsCore)
endif()
target_compile_features(DanceRudiments PUBLIC cxx_std_17)
target_include_directories(DanceRudiments PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)

if(DANCERUDIMENTS_BUILD_PYTHON)
  set(PYBIND11_FINDPYTHON ON)
  find_package(pybind11 CONFIG REQUIRED)
  pybind11_add_module(dancerudiments_python bindings/python/module.cpp)
  set_target_properties(dancerudiments_python PROPERTIES OUTPUT_NAME dancerudiments)
  target_link_libraries(dancerudiments_python PRIVATE DanceRudiments::DanceRudiments)
  if(MINGW)
    target_link_options(dancerudiments_python PRIVATE -static-libgcc -static-libstdc++)
    get_filename_component(DANCERUDIMENTS_MINGW_BIN "${CMAKE_CXX_COMPILER}" DIRECTORY)
    set(DANCERUDIMENTS_WINPTHREAD_DLL "${DANCERUDIMENTS_MINGW_BIN}/libwinpthread-1.dll")
    if(EXISTS "${DANCERUDIMENTS_WINPTHREAD_DLL}")
      install(FILES "${DANCERUDIMENTS_WINPTHREAD_DLL}" DESTINATION .)
    endif()
  endif()
  install(TARGETS dancerudiments_python LIBRARY DESTINATION . RUNTIME DESTINATION .)
endif()

if(DANCERUDIMENTS_BUILD_WASM)
  if(NOT EMSCRIPTEN)
    message(FATAL_ERROR "DANCERUDIMENTS_BUILD_WASM requires Emscripten (use emcmake cmake).")
  endif()
  add_executable(dancerudiments_wasm bindings/typescript/wasm.cpp)
  target_compile_options(DanceRudiments PRIVATE -fexceptions)
  target_compile_options(dancerudiments_wasm PRIVATE -fexceptions)
  target_link_libraries(dancerudiments_wasm PRIVATE DanceRudiments::DanceRudiments)
  set_target_properties(dancerudiments_wasm PROPERTIES OUTPUT_NAME dancerudiments)
  target_link_options(dancerudiments_wasm PRIVATE
    "--bind"
    "-fexceptions"
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
  add_executable(dancerudiments_pattern_tests tests/cpp/test_sampled_pattern.cpp)
  target_link_libraries(dancerudiments_pattern_tests PRIVATE DanceRudiments::DanceRudiments)
  add_test(NAME dancerudiments_patterns COMMAND dancerudiments_pattern_tests)
  add_executable(dancerudiments_default_tests tests/cpp/test_default_registration.cpp)
  target_link_libraries(dancerudiments_default_tests PRIVATE DanceRudiments::DanceRudiments)
  add_test(NAME dancerudiments_defaults COMMAND dancerudiments_default_tests)
  add_executable(dancerudiments_continuum_tests tests/cpp/test_continuum.cpp)
  target_link_libraries(dancerudiments_continuum_tests PRIVATE DanceRudiments::DanceRudiments)
  add_test(NAME dancerudiments_continuum COMMAND dancerudiments_continuum_tests)
  add_executable(dancerudiments_club_tests tests/cpp/test_club.cpp)
  target_link_libraries(dancerudiments_club_tests PRIVATE DanceRudiments::DanceRudiments)
  add_test(NAME dancerudiments_club COMMAND dancerudiments_club_tests)
  add_executable(dancerudiments_dancefloor_tests tests/cpp/test_dancefloor.cpp)
  target_link_libraries(dancerudiments_dancefloor_tests PRIVATE DanceRudiments::DanceRudiments)
  add_test(NAME dancerudiments_dancefloor COMMAND dancerudiments_dancefloor_tests)
endif()

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
configure_package_config_file(
  cmake/DanceRudimentsConfig.cmake.in
  "${CMAKE_CURRENT_BINARY_DIR}/DanceRudimentsConfig.cmake"
  INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/DanceRudiments")
write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/DanceRudimentsConfigVersion.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion)
install(TARGETS DanceRudiments EXPORT DanceRudimentsTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(FILES
  "${CMAKE_CURRENT_BINARY_DIR}/DanceRudimentsConfig.cmake"
  "${CMAKE_CURRENT_BINARY_DIR}/DanceRudimentsConfigVersion.cmake"
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/DanceRudiments")
install(EXPORT DanceRudimentsTargets NAMESPACE DanceRudiments::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/DanceRudiments)

# Export the ACTUAL catalogue used by the tag, never a handwritten JS mirror.
if(DANCERUDIMENTS_BUILD_DEMO_TOOLS)
  add_executable(dancerudiments_export_demo tools/export_default_catalogue.cpp)
  target_link_libraries(dancerudiments_export_demo PRIVATE DanceRudiments::DanceRudiments)
endif()
install(FILES collections/initial/THIRD_PARTY_NOTICES.md
  DESTINATION "${CMAKE_INSTALL_DATADIR}/DanceRudiments")
install(FILES collections/initial/sources/d3-ease/LICENSE
  DESTINATION "${CMAKE_INSTALL_DATADIR}/DanceRudiments" RENAME D3-ease-LICENSE)
