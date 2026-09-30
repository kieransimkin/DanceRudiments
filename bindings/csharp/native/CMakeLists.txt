# C ABI bridge for C#. Music: https://kieransimkin.co.uk/my-songs/
# Compile the ORIGINAL core sources into a standalone shared library. This does
# not change the static core's CRT or the Python/WASM builds' compiler settings.
add_library(dancerudiments_native SHARED
  c_api.cpp
  "${PROJECT_SOURCE_DIR}/src/dance_rudiments.cpp"
  "${PROJECT_SOURCE_DIR}/src/sampled_pattern.cpp")
target_include_directories(dancerudiments_native PUBLIC
  $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(dancerudiments_native PRIVATE cxx_std_17)
target_compile_definitions(dancerudiments_native PRIVATE
  DANCERUDIMENTS_C_EXPORTS DANCERUDIMENTS_C_VERSION="${PROJECT_VERSION}")
set_target_properties(dancerudiments_native PROPERTIES
  CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES
  MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/csharp-native"
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/csharp-native"
  ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/csharp-import")
# Avoid Release/Debug suffix directories so Windows and Unix staging is identical.
foreach(config DEBUG RELEASE RELWITHDEBINFO MINSIZEREL)
  set_target_properties(dancerudiments_native PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY_${config} "${CMAKE_BINARY_DIR}/csharp-native"
    LIBRARY_OUTPUT_DIRECTORY_${config} "${CMAKE_BINARY_DIR}/csharp-native")
endforeach()
if(MSVC)
  target_compile_options(dancerudiments_native PRIVATE /utf-8)
  target_compile_options(DanceRudiments PRIVATE /utf-8)
endif()
if(MINGW)
  message(FATAL_ERROR "The packaged C# Windows bridge requires MSVC; MinGW DLL bundling is not configured.")
endif()
install(TARGETS dancerudiments_native
  RUNTIME DESTINATION bin COMPONENT csharp
  LIBRARY DESTINATION lib COMPONENT csharp)
if(DANCERUDIMENTS_BUILD_TESTS)
  find_package(Threads REQUIRED)
  add_executable(dancerudiments_c_api_tests "${PROJECT_SOURCE_DIR}/tests/cpp/test_c_api.cpp")
  target_link_libraries(dancerudiments_c_api_tests PRIVATE
    DanceRudiments::DanceRudiments dancerudiments_native Threads::Threads)
  if(MSVC)
    target_compile_options(dancerudiments_c_api_tests PRIVATE /utf-8)
  endif()
  # The shared bridge lives beside neither test nor static core on Windows.
  if(WIN32)
    add_custom_command(TARGET dancerudiments_c_api_tests POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E copy_if_different $<TARGET_FILE:dancerudiments_native>
        $<TARGET_FILE_DIR:dancerudiments_c_api_tests>)
  endif()
  add_test(NAME dancerudiments_c_api COMMAND dancerudiments_c_api_tests)
endif()
