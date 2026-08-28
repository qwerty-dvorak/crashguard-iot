# CrashGuard Wokwi project

`sketch.ino` is the production ESP32 firmware. The Wokwi simulation changes
the virtual MPU-6050 registers from automation scenarios. There is no hidden
synthetic sensor branch in the firmware.

The virtual piezo is connected directly to GPIO25 because it models a
low-current piezo element. The physical circuit in the report drives a 5 V
passive piezo transducer through an NPN transistor. This matches the
firmware's 2.4 kHz `tone()` output while keeping transducer current out of the
GPIO. The firmware pin and alarm semantics are otherwise identical.

## Build the firmware

If Arduino CLI is absent:

```sh
sudo xbps-install -S arduino-cli
```

Install the Espressif board core in user storage and compile:

```sh
arduino-cli config add board_manager.additional_urls \
  https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32
arduino-cli compile --fqbn esp32:esp32:esp32 \
  --build-path build arduino-build/sketch
```

Arduino CLI requires the main `.ino` filename to match its directory. The
small file in `arduino-build/sketch/` only includes the root `sketch.ino`, so
the CLI and Wokwi compile one firmware source rather than maintained copies.

Verified with ESP32 Arduino core 3.3.11 and all compiler warnings enabled:
392,947 bytes of program storage (29%) and 29,808 bytes of statically allocated
RAM (9%). The generated `build/sketch.ino.bin` and `.elf` files match
the paths in `wokwi.toml`.

For hardware cloud delivery, copy `secrets.h.example` to `secrets.h`, enter
the phone-hotspot credentials and Blynk device token, then rebuild. The file is
optional so the same source builds offline for Wokwi.

## Validate and run

Install the official Wokwi CLI in your user account:

```sh
curl -L https://wokwi.com/ci/install.sh | sh
export PATH="$HOME/bin:$PATH"
```

Diagram linting does not execute firmware:

```sh
wokwi-cli lint .
```

Running CI simulations requires a Wokwi CI token from the Wokwi dashboard:

```sh
export WOKWI_CLI_TOKEN='wok_replace_with_your_token'
wokwi-cli . --scenario scenario-crash.yaml --timeout 25000 \
  --expect-text ALERT_SENT
wokwi-cli . --scenario scenario-pothole.yaml --timeout 10000 \
  --expect-text CANDIDATE_REJECTED
wokwi-cli . --scenario scenario-cancel.yaml --timeout 12000 \
  --expect-text ALERT_CANCELLED
```

The CLI token is an external account credential and is deliberately not
stored in this repository.
