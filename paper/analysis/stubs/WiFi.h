#pragma once
#define WL_CONNECTED 3
#define WIFI_STA 1
struct WifiType {int statusCode=3; int status(){return statusCode;} void mode(int){} template<class... A>void begin(A...){} }; inline WifiType WiFi;
