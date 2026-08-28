# CrashGuard firmware and Wokwi project

`sketch.ino` is the production ESP32 firmware. The Wokwi simulation changes
the virtual MPU-6050 registers from automation scenarios. There is no hidden
synthetic sensor branch in the firmware.

The diagram and physical design target an ESP32-DevKitC development board.
UART0 TX/RX are connected explicitly to Wokwi's serial monitor so automated
scenarios can observe firmware events.

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

Install the Espressif board core and pinned Blynk library in user storage,
then compile:

```sh
arduino-cli config add board_manager.additional_urls \
  https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32
arduino-cli lib install Blynk@1.3.5
arduino-cli compile --fqbn esp32:esp32:esp32 \
  --build-path build arduino-build/sketch
```

Arduino CLI requires the main `.ino` filename to match its directory. The
small file in `arduino-build/sketch/` only includes the root `sketch.ino`, so
the CLI and Wokwi compile one firmware source rather than maintained copies.

The generated `build/sketch.ino.merged.bin` contains the
bootloader, partition table, and application image recommended for ESP32
simulation. The merged image and `build/sketch.ino.elf` match the paths in
`wokwi.toml`.

## Configure Blynk IoT

In Blynk Console, create a template for an ESP32 using Wi-Fi. Under the
template's **Events** page, create a custom event named `Crash confirmed` with
the exact code `crash_confirmed`. Enable timeline recording and notifications
for that event. Then create a device from the template and copy its Template
ID, Template Name, and device Auth Token.

For physical hardware, copy `secrets.h.example` to `secrets.h` and fill in
those Blynk values plus the phone-hotspot credentials. At startup the ESP32
starts Wi-Fi asynchronously. Only after the 15-second cancellation deadline
does it make a bounded SSL connection to Blynk and call
`Blynk.logEvent("crash_confirmed", description)`. Detection, the local alarm,
and cancellation do not depend on cloud availability.
`BLYNK_EVENT_SUBMITTED` means the firmware called the event API while the
library reported an authenticated connection; it does not prove server or
phone receipt. Delivery still depends on Blynk's event and notification
settings.

For Wokwi, copy `secrets.wokwi.h.example` to `secrets.h`. It uses Wokwi's
documented open `Wokwi-GUEST` network on channel 6. Use a dedicated test
device token, not a production token, and remove or rotate it after testing.
The real `secrets.h` is ignored by Git. Without this file, the same firmware
still simulates safely and reports `BLYNK_EVENT_SKIPPED reason=not_configured`
instead of claiming cloud delivery.

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

A prior source revision passed all three offline scenarios on 28 August 2026.
The cancellation test keeps GPIO26 low for 16 seconds after cancellation and
fails if `ALERT_DUE` appears. The checked-in crash scenario validates the
offline Blynk handoff. After adding a real test-device token and rebuilding,
run the opt-in cloud scenario explicitly:

```sh
wokwi-cli . --scenario scenario-crash-blynk.yaml --timeout 35000 \
  --timeout-exit-code 1
```

This command deliberately is not part of `run-tests.sh`: it consumes Wokwi
quota and sends a real Blynk event. See
[`results/wokwi_validation.json`](../results/wokwi_validation.json) for the
exact claim scope. Wokwi results are not physical crash, power, mounting, or
network-delivery measurements.
