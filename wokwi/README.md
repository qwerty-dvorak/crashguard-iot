# CrashGuard Wokwi project

`sketch.ino` is the production ESP32 firmware. The Wokwi simulation changes
the virtual MPU-6050 registers from automation scenarios. There is no hidden
synthetic sensor branch in the firmware.

The diagram uses Wokwi's official ESP32-DevKitC V4 virtual board while the
production target remains ESP32 DevKit V1. Both expose the same ESP32 GPIOs
used by this design. UART0 TX/RX are connected explicitly to Wokwi's serial
monitor so command-line scenarios can observe firmware events.

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
RAM (9%). The generated `build/sketch.ino.merged.bin` contains the
bootloader, partition table, and application image recommended for ESP32
simulation. The merged image and `build/sketch.ino.elf` match the paths in
`wokwi.toml`.

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

Running Wokwi cloud simulations requires a Wokwi CI token from the dashboard.
Export it only in the current shell and use the checked-in test runner when a
deliberate revalidation is needed:

```sh
export WOKWI_CLI_TOKEN='wok_replace_with_your_token'
./run-tests.sh
```

The CLI token is an external account credential and is deliberately not
stored in this repository. Each execution consumes Wokwi CI quota, so no
automatic GitHub Actions workflow is enabled. Firmware compilation and
diagram linting can be repeated without a token or Wokwi simulation minutes.

All three scenarios passed on 28 August 2026 with Wokwi CLI 0.26.1 and
Simulation API `1.0.0-20260825-g9f67b160`. The cancellation test keeps
GPIO26 low for 16 seconds after cancellation and fails if `ALERT_SENT`
appears. See [`results/wokwi_validation.json`](../results/wokwi_validation.json)
for the exact claim scope and hashes. These are virtual-hardware results, not
physical crash, power, mounting, or network-delivery measurements.
