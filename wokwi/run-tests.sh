#!/bin/sh
set -eu

: "${WOKWI_CLI_TOKEN:?Export WOKWI_CLI_TOKEN before running cloud simulations}"

wokwi_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
arduino_cli=${ARDUINO_CLI:-arduino-cli}
wokwi_cli=${WOKWI_CLI:-wokwi-cli}

command -v "$arduino_cli" >/dev/null 2>&1 || {
  printf '%s\n' 'arduino-cli is required' >&2
  exit 127
}
command -v "$wokwi_cli" >/dev/null 2>&1 || {
  printf '%s\n' 'wokwi-cli is required' >&2
  exit 127
}

"$arduino_cli" compile --fqbn esp32:esp32:esp32 \
  --build-path "$wokwi_dir/build" "$wokwi_dir/arduino-build/sketch"

(cd "$wokwi_dir" && "$wokwi_cli" lint .)

run_scenario() {
  scenario=$1
  timeout_ms=$2
  fail_text=${3:-}
  printf '\nRunning %s\n' "$scenario"
  if [ -n "$fail_text" ]; then
    "$wokwi_cli" "$wokwi_dir" \
      --scenario "$scenario" \
      --timeout "$timeout_ms" \
      --timeout-exit-code 1 \
      --fail-text "$fail_text"
  else
    "$wokwi_cli" "$wokwi_dir" \
      --scenario "$scenario" \
      --timeout "$timeout_ms" \
      --timeout-exit-code 1
  fi
}

run_scenario scenario-crash.yaml 25000
run_scenario scenario-pothole.yaml 10000
run_scenario scenario-cancel.yaml 30000 ALERT_DUE

printf '\n%s\n' 'All CrashGuard Wokwi scenarios passed.'
