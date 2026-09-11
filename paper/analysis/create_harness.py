from pathlib import Path
p=Path(__file__).parent
(p/'stubs').mkdir(exist_ok=True)
(p/'cloud').mkdir(exist_ok=True)
(p/'stubs/Arduino.h').write_text(r'''#pragma once
#include <cstdint>
#include <cstddef>
#include <cmath>
#include <cstdio>
#include <string>
#include <stdexcept>
#include <array>
using String=std::string;
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
'''.replace('using String=std::string;',r'''struct String:std::string {using std::string::string; String(float v,int digits){char b[64];std::snprintf(b,sizeof b,"%.*f",digits,v);assign(b);}};'''))
(p/'stubs/WiFi.h').write_text('''#pragma once
#define WL_CONNECTED 3
#define WIFI_STA 1
struct WifiType {int statusCode=3; int status(){return statusCode;} void mode(int){} template<class... A>void begin(A...){} }; inline WifiType WiFi;
''')
(p/'stubs/Wire.h').write_text('''#pragma once
#include <array>
struct WireType {int error=0,length=14,index=0;std::array<int,7> raw={0,0,2048,0,0,0,0};void begin(int,int,int){} void beginTransmission(int){} void write(int){} int endTransmission(bool){return error;}int requestFrom(int,int,bool){index=0;return length;}int read(){int v=raw[index/2];int out=(index%2)?v&255:(v>>8)&255;++index;return out;}};inline WireType Wire;
''')
(p/'cloud/secrets.h').write_text('''#define BLYNK_TEMPLATE_ID "SIMULATION"
#define BLYNK_TEMPLATE_NAME "LOCAL_TEST_DOUBLE"
#define BLYNK_AUTH_TOKEN "NON_NETWORK_TEST_VALUE"
#define CRASHGUARD_WIFI_SSID "LOCAL"
#define CRASHGUARD_WIFI_PASSWORD "LOCAL"
''')
(p/'cloud/BlynkSimpleEsp32_SSL.h').write_text('''#pragma once
struct BlynkType{bool online=true,connectOk=true;int calls=0;std::string code,description;bool connected(){return online;}bool connect(int ms){if(!connectOk)clockUs+=ms*1000;return connectOk;}void config(const char*){}void logEvent(const char* c,const std::string& d){++calls;code=c;description=d;}void run(){}};inline BlynkType Blynk;
''')
