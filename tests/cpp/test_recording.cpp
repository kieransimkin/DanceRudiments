#include "dancerudiments/recording.hpp"
#include <climits>
#include <iostream>
using namespace dancerudiments;
void check(bool v) { if(!v)throw std::runtime_error("Recording regression"); }
template<class E=std::invalid_argument,class F>void rejects(F fn){bool caught=false;try{fn();}catch(const E&){caught=true;}check(caught);}
int main(){
 std::vector<std::string> axes{"x","y","z","rotation","energy","bass"};
 std::vector<std::vector<double>> values{{.1,.2,.3,.4,.5,.6},{-.1,-.2,-.3,-.4,-.5,-.6}};
 SampledRecording r("test",axes,values,120.,.25,-32);
 check(r.sample(-32)==values[0]);check(r.sample(-31)==values[1]);check(r.dimensions()==axes);
 values[0][0]=.9;check(r.sample(-32)[0]==.1);
 rejects<std::out_of_range>([&]{r.sample(-33);});rejects<std::out_of_range>([&]{r.sample(-30);});
 rejects<std::out_of_range>([&]{r.sample(INT_MIN);});rejects<std::out_of_range>([&]{r.sample(INT_MAX);});
 rejects([&]{SampledRecording bad("bad",axes,values,0.);});
 rejects([&]{SampledRecording bad("bad",{"x","x"},{{0.,0.}},120.);});
 rejects([&]{SampledRecording bad("bad",{"x"},{{0.,0.}},120.);});
 rejects([&]{SampledRecording bad("bad",{"x"},{{2.}},120.);});
 SampledRecording long_recording("long",{"x"},std::vector<std::vector<double>>(65536,{.2}),120.);
 check(long_recording.sample(65535)[0]==.2);
 const double data[]{.1,.2,.3,.4};
 check(recording_component(data,2,2,-1,0,1)==.4);
 check(std::isnan(recording_component(data,2,2,-1,-2,0)));
 check(std::isnan(recording_component(data,2,2,-1,1,0)));
 std::cout<<"Native N-dimensional recordings passed\n";
}
