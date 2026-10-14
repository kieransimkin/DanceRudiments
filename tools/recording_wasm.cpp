#include "dancerudiments/recording_view.hpp"
extern unsigned char __heap_base;
extern "C" {
unsigned int table_base() { return reinterpret_cast<unsigned long>(&__heap_base); }
double sample_recording(const double* data,int count,int dimensions,int first,int pip,int axis) {
  return dancerudiments::recording_component(data,count,dimensions,first,pip,axis);
}
}
