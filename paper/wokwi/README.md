# ESP32 firmware and circuit

`sketch.ino` is the application firmware; `crash_detector.h` is the portable detector shared with the replay executable. `diagram.json` defines the virtual circuit. The three YAML scenarios describe crash confirmation, road-shock rejection, and rider cancellation.

The reproducible experiment pipeline compiles this exact sketch through `analysis/firmware_harness.cpp`, using the local peripheral doubles. These tests require no production credentials or external simulator service.

To compile a hardware binary with Arduino CLI and an installed ESP32 board core, run from the artifact root:

```sh
mkdir -p wokwi/arduino/sketch
cp wokwi/sketch.ino wokwi/crash_detector.h wokwi/arduino/sketch/
arduino-cli compile --fqbn esp32:esp32:esp32 --build-path wokwi/build wokwi/arduino/sketch
```

The credential-free build preserves local detection and cancellation. An authenticated deployment uses the Blynk ESP32 SSL client and a private `secrets.h` defining the template, device token, SSID, and password. Production account credentials are excluded from version control. The fixed `analysis/cloud/secrets.h` values are exclusively for the local test double and cannot authenticate a cloud device.
