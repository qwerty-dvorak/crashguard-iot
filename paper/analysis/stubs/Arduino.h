#pragma once
#include <cstdint>
#include <cstddef>
#include <cmath>
#include <cstdio>
#include <string>
#include <stdexcept>
#include <array>
struct String:std::string {using std::string::string; String(float v,int digits){char b[64];std::snprintf(b,sizeof b,"%.*f",digits,v);assign(b);}};
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define INPUT_PULLUP 2
inline uint64_t clockUs=0;
inline bool stopOnLongDelay=false;
inline std::array<int,40> pins{};
inline int toneHz=0;
inline uint32_t millis(){return clockUs/1000;}
inline uint32_t micros(){return clockUs;}
inline void delay(int ms){clockUs+=ms*1000;if(stopOnLongDelay && ms==1000)throw std::runtime_error("safe_stop");}
inline void pinMode(int,int){}
inline void digitalWrite(int p,int v){pins[p]=v;}
inline int digitalRead(int p){return pins[p];}
inline void tone(int,int f){toneHz=f;}
inline void noTone(int){toneHz=0;}
inline int analogReadMilliVolts(int){return 1850;}
struct SerialType{void begin(int){};void println(const char* s){std::puts(s);}template<class... A>void printf(const char* f,A... a){std::printf(f,a...);}};
inline SerialType Serial;
