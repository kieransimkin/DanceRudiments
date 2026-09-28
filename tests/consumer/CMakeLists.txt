cmake_minimum_required(VERSION 3.20)
project(DanceRudimentsConsumer LANGUAGES CXX)

find_package(DanceRudiments CONFIG REQUIRED)
add_executable(dancerudiments_consumer main.cpp)
target_link_libraries(dancerudiments_consumer PRIVATE DanceRudiments::DanceRudiments)
enable_testing()
add_test(NAME dancerudiments_consumer COMMAND dancerudiments_consumer)
