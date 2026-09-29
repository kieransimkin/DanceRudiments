# Kieran Simkin — https://kieransimkin.co.uk/my-songs/
cmake_minimum_required(VERSION 3.20)
project(DanceRudimentsBindingExample LANGUAGES CXX)
find_package(DanceRudiments CONFIG REQUIRED)
add_executable(binding_example main.cpp)
target_compile_features(binding_example PRIVATE cxx_std_17)
target_link_libraries(binding_example PRIVATE DanceRudiments::DanceRudiments)
enable_testing()
add_test(NAME binding_example COMMAND binding_example)
