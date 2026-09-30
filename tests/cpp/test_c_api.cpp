// MIT. Kieran Simkin — https://kieransimkin.co.uk/my-songs/
#include "dancerudiments/c_api.h"
#include "dancerudiments/sampled_pattern.hpp"
#include <atomic>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <thread>
#include <vector>

static std::size_t checks = 0;
static void check(bool ok) { ++checks; if (!ok) throw std::runtime_error("C ABI check failed at " + std::to_string(checks)); }
static void same(dr_offset3 a, dancerudiments::Offset3 b) { check(a.x == b.x && a.y == b.y && a.z == b.z); }
int main() {
  try {
    check(sizeof(dr_offset3) == sizeof(double)*3);
    check(dr_abi_version() == 1 && dr_pips_per_beat() == 64 && std::strlen(dr_version()) > 0);
    uint32_t count = 0; check(dr_catalogue_count(&count) == DR_OK);
    const auto& native = dancerudiments::catalogue(); check(count == native.size());
    std::size_t samples = 0;
    for (uint32_t i = 0; i < count; ++i) {
      dr_info info{}; check(dr_catalogue_get(i, &info) == DR_OK);
      check(info.name == native[i].name && info.description == native[i].description);
      check(info.period_pips == native[i].period_pips && info.dimensions == static_cast<uint32_t>(native[i].dimensions));
      std::vector<dr_offset3> batch(info.period_pips);
      check(dr_sample_many(info.name, 0, 1, info.period_pips, batch.data()) == DR_OK);
      for (uint32_t pip = 0; pip < info.period_pips; ++pip) {
        dr_offset3 v{}; check(dr_sample(info.name, static_cast<int32_t>(pip), &v) == DR_OK);
        const auto expected = dancerudiments::sample(info.name, static_cast<int>(pip));
        same(v,expected); same(batch[pip],expected); ++samples;
      }
      for (int32_t pip : {INT32_MIN, -1, 0, INT32_MAX}) {
        dr_offset3 v{}; check(dr_sample(info.name, pip, &v) == DR_OK);
        same(v,dancerudiments::sample(info.name,pip));
      }
      dr_offset3 edge[9]{};
      check(dr_sample_many(info.name, INT32_MIN, INT32_MAX, 9, edge) == DR_OK);
      for (int64_t k=0;k<9;++k) {
        int p=static_cast<int>((static_cast<int64_t>(INT32_MIN)+k*INT32_MAX)%info.period_pips);
        same(edge[k],dancerudiments::sample(info.name,p));
      }
    }
    dr_offset3 v{.1,.2,.3};
    check(dr_sample("absent",0,&v) == DR_INVALID_ARGUMENT);
    check(v.x == .1 && std::strstr(dr_last_error(),"absent"));
    check(dr_sample(nullptr,0,&v) == DR_INVALID_ARGUMENT);
    check(dr_sample("circle",0,nullptr) == DR_INVALID_ARGUMENT);
    check(dr_catalogue_count(nullptr) == DR_INVALID_ARGUMENT);
    dr_info info{}; check(dr_catalogue_get(count,&info) == DR_OUT_OF_RANGE);
    check(dr_catalogue_get(0,nullptr) == DR_INVALID_ARGUMENT);
    check(dr_sample_many("circle",0,1,0,nullptr) == DR_OK);
    check(dr_sample_many("absent",0,1,0,nullptr) == DR_INVALID_ARGUMENT);
    check(dr_sample_many("circle",0,1,1048577,&v) == DR_INVALID_ARGUMENT);
    check(dr_sample_many("circle",0,1,1,nullptr) == DR_INVALID_ARGUMENT);

    // C++ owns deep copies, including UTF-8 metadata. Lifetime is explicit.
    dr_library* library = nullptr;
    dr_offset3 points[] = {{0,0,0},{.2,-.3,.4},{-.4,.5,-.6}};
    dr_pattern_definition definition{"csharp_test",u8"Écho — 日本語 🎵",points,3};
    check(dr_library_create(&definition,1,&library) == DR_OK && library);
    points[1].x = .99;
    check(dr_library_sample(library,"csharp_test",1,&v) == DR_OK && v.x == .2);
    check(dr_library_sample(library,"csharp_test",-1,&v) == DR_OK && v.z == -.6);
    uint32_t bank_count{}; check(dr_library_count(library,&bank_count)==DR_OK && bank_count == count+1);
    check(dr_library_get(library,count,&info)==DR_OK && std::strcmp(info.description,definition.description)==0);
    check(dr_library_sample(library,"circle",64,&v)==DR_OK); same(v,dancerudiments::circle(0));
    dr_offset3 reverse[5]{}; check(dr_library_sample_many(library,"csharp_test",-1,-1,5,reverse)==DR_OK);
    check(reverse[1].x == .2 && reverse[4].x == .2);
    check(dr_library_get(library,bank_count,&info)==DR_OUT_OF_RANGE);
    dr_library_destroy(library); dr_library_destroy(nullptr);
    check(dr_library_sample(nullptr,"circle",0,&v)==DR_INVALID_ARGUMENT);
    check(dr_library_count(nullptr,&bank_count)==DR_INVALID_ARGUMENT);
    check(dr_library_get(nullptr,0,&info)==DR_INVALID_ARGUMENT);
    check(dr_library_sample_many(nullptr,"circle",0,1,0,nullptr)==DR_INVALID_ARGUMENT);
    check(dr_library_create(nullptr,0,&library)==DR_OK && library);
    dr_library_destroy(library);
    library = reinterpret_cast<dr_library*>(1);
    check(dr_library_create(nullptr,1,&library)==DR_INVALID_ARGUMENT && library==nullptr);
    check(dr_library_create(&definition,1025,&library)==DR_INVALID_ARGUMENT && library==nullptr);
    check(dr_library_create(nullptr,0,nullptr)==DR_INVALID_ARGUMENT);
    definition.count=0; check(dr_library_create(&definition,1,&library)==DR_INVALID_ARGUMENT && !library);
    definition.count=3; points[0].x=std::numeric_limits<double>::quiet_NaN();
    check(dr_library_create(&definition,1,&library)==DR_INVALID_ARGUMENT && !library);
    points[0].x=0; definition.name="circle";
    check(dr_library_create(&definition,1,&library)==DR_INVALID_ARGUMENT && !library);
    definition.name="duplicate";
    dr_pattern_definition repeated[]={definition,definition};
    check(dr_library_create(repeated,2,&library)==DR_INVALID_ARGUMENT && !library);
    // Exact default reloads retain the core idempotence contract.
    const auto& circle=native[2];std::vector<dr_offset3> circle_values(circle.period_pips);
    check(dr_sample_many("circle",0,1,circle.period_pips,circle_values.data())==DR_OK);
    definition={"circle",circle.description.data(),circle_values.data(),circle.period_pips};
    check(dr_library_create(&definition,1,&library)==DR_OK);
    check(dr_library_count(library,&bank_count)==DR_OK && bank_count==count);
    dr_library_destroy(library);
    // Failure messages cannot leak between threads.
    std::atomic<int> ready{0}; std::atomic<bool> threads_ok{true};
    auto thread_test=[&](const char* name){
      dr_offset3 result{};
      if(dr_sample(name,0,&result)!=DR_INVALID_ARGUMENT)threads_ok=false;
      ++ready;while(ready.load()!=2)std::this_thread::yield();
      if(!std::strstr(dr_last_error(),name))threads_ok=false;
    };
    std::thread a(thread_test,"thread_alpha"),b(thread_test,"thread_beta");a.join();b.join();
    check(threads_ok.load());
    check(dr_sample("circle",0,&v)==DR_OK && dr_last_error()[0]=='\0');
    std::cout << "C ABI: " << count << " patterns; " << samples << " exact sample triples; " << checks << " checks passed\n";
  } catch(const std::exception& e) {std::cerr << e.what() << '\n';return 1;}
}
