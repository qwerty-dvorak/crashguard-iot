#include <cassert>
#include <iostream>
#include "../wokwi/sketch.ino"
void sampleAt(uint32_t t,int az=2048,int gx=0,int ay=0){clockUs=uint64_t(t)*1000;Wire.raw={0,ay,az,0,gx,0,0};loop();}
void crash(){for(uint32_t t=0;t<=1300;t+=10)sampleAt(t,2048,131);sampleAt(1500,2048,2132);sampleAt(1600,6144);for(uint32_t t=1610;t<=3610;t+=10)sampleAt(t,700,0,1925);assert(detector.state()==crashguard::State::Countdown);}
int main(int argc,char**argv){assert(argc==2);std::string c=argv[1];pins[27]=HIGH;
 if(c=="boot_absent"){Wire.error=1;stopOnLongDelay=true;try{setup();}catch(const std::runtime_error&){assert(pins[26]==LOW);std::cout<<"RESULT safe_stop alarm=0\n";return 0;}return 1;}
 if(c=="short_read"){Wire.length=10;loop();assert(detector.state()==crashguard::State::Idle);std::cout<<"RESULT skipped state=IDLE\n";}
 else if(c=="bus_error"){Wire.error=1;loop();assert(detector.state()==crashguard::State::Idle);std::cout<<"RESULT skipped state=IDLE\n";}
 else if(c=="calibration_motion"){Wire.raw[4]=1640;assert(!calibrateStationaryReference());std::cout<<"RESULT calibration_rejected\n";}
 else if(c=="calibration_still"){assert(calibrateStationaryReference());std::cout<<"RESULT calibration_accepted samples=200\n";}
 else if(c=="battery_adc"){assert(std::fabs(readBatteryVoltage()-3.7f)<0.001);std::cout<<"RESULT voltage=3.700\n";}
 else if(c=="cancel"){crash();sampleAt(4000,700,0,1925);pins[27]=LOW;sampleAt(4010,700,0,1925);pins[27]=HIGH;for(uint32_t t=4020;t<=20000;t+=10)sampleAt(t,700,0,1925);assert(pins[26]==LOW);assert(detector.state()==crashguard::State::Idle);std::cout<<"RESULT cancelled alarm=0\n";}
 else if(c=="deadline"){crash();assert(pins[26]==HIGH && toneHz==2400);sampleAt(18600,700,0,1925);assert(detector.state()==crashguard::State::Countdown);sampleAt(18610,700,0,1925);assert(detector.state()==crashguard::State::AlertDue);for(uint32_t t=18620;t<19000;t+=10)sampleAt(t,700,0,1925);
#if CRASHGUARD_HAS_BLYNK
 assert(Blynk.calls==1);
#endif
 std::cout<<"RESULT confirmation_ms=3610 deadline_ms=18610 one_shot=1\n";}
 else if(c=="sample_gap"){for(uint32_t t=0;t<=1300;t+=10)sampleAt(t,2048,131);sampleAt(1500,2048,2132);sampleAt(1600,6144);sampleAt(1610,700,0,1925);Wire.length=0;sampleAt(2000);sampleAt(3000);Wire.length=14;sampleAt(3610,700,0,1925);assert(detector.state()==crashguard::State::Countdown);std::cout<<"RESULT gap_spans_rest confirmation_ms=3610\n";}
#if CRASHGUARD_HAS_BLYNK
 else if(c=="wifi_down"){crash();WiFi.statusCode=0;sampleAt(18610,700,0,1925);assert(Blynk.calls==0 && pins[26]==HIGH);std::cout<<"RESULT wifi_skipped alarm=1\n";}
 else if(c=="cloud_down"){crash();Blynk.online=false;Blynk.connectOk=false;sampleAt(18610,700,0,1925);assert(Blynk.calls==0 && pins[26]==HIGH);assert(millis()==23610);std::cout<<"RESULT cloud_skipped blocking_ms=5000 alarm=1\n";}
 else if(c=="submitted"){crash();sampleAt(18610,700,0,1925);assert(Blynk.calls==1 && Blynk.code=="crash_confirmed" && Blynk.description.size()<=300);std::cout<<"RESULT simulated_sink_events=1 description_bytes="<<Blynk.description.size()<<"\n";}
 else if(c=="no_retry"){crash();WiFi.statusCode=0;sampleAt(18610,700,0,1925);WiFi.statusCode=3;sampleAt(19000,700,0,1925);assert(Blynk.calls==0);std::cout<<"RESULT recovery_events=0\n";}
#endif
 else {return 2;}return 0;}
