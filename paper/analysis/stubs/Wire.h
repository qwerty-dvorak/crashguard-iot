#pragma once
#include <array>
struct WireType {int error=0,length=14,index=0;std::array<int,7> raw={0,0,2048,0,0,0,0};void begin(int,int,int){} void beginTransmission(int){} void write(int){} int endTransmission(bool){return error;}int requestFrom(int,int,bool){index=0;return length;}int read(){int v=raw[index/2];int out=(index%2)?v&255:(v>>8)&255;++index;return out;}};inline WireType Wire;
