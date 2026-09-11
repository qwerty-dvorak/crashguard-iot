#pragma once
struct BlynkType{bool online=true,connectOk=true;int calls=0;std::string code,description;bool connected(){return online;}bool connect(int ms){if(!connectOk)clockUs+=ms*1000;return connectOk;}void config(const char*){}void logEvent(const char* c,const std::string& d){++calls;code=c;description=d;}void run(){}};inline BlynkType Blynk;
