#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <Wire.h>

#include "crash_detector.h"

#if __has_include("secrets.h")
#include "secrets.h"
#define CRASHGUARD_HAS_SECRETS 1
#else
#define CRASHGUARD_HAS_SECRETS 0
#endif

namespace {

constexpr uint8_t kMpuAddress = 0x68;
constexpr int kSdaPin = 21;
constexpr int kSclPin = 22;
constexpr int kLedPin = 26;
constexpr int kBuzzerPin = 25;
constexpr int kCancelPin = 27;
constexpr int kBatteryPin = 34;
constexpr uint32_t kSamplePeriodUs = 10000;
constexpr size_t kCalibrationSamples = 200;
constexpr float kAccelLsbPerG = 2048.0f;
constexpr float kGyroLsbPerDps = 16.4f;

crashguard::Detector detector;
uint32_t nextSampleUs = 0;
bool lastButtonPressed = false;
float gyroOffsetX = 0.0f;
float gyroOffsetY = 0.0f;
float gyroOffsetZ = 0.0f;

bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(kMpuAddress);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission(true) == 0;
}

bool readRaw(crashguard::Sample &sample) {
  Wire.beginTransmission(kMpuAddress);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(kMpuAddress, static_cast<uint8_t>(14), true) != 14) {
    return false;
  }

  auto readI16 = []() -> int16_t {
    return static_cast<int16_t>((Wire.read() << 8) | Wire.read());
  };

  const int16_t rawAx = readI16();
  const int16_t rawAy = readI16();
  const int16_t rawAz = readI16();
  (void)readI16();  // Temperature is not used by the detector.
  const int16_t rawGx = readI16();
  const int16_t rawGy = readI16();
  const int16_t rawGz = readI16();

  sample.timeMs = millis();
  sample.axG = rawAx / kAccelLsbPerG;
  sample.ayG = rawAy / kAccelLsbPerG;
  sample.azG = rawAz / kAccelLsbPerG;
  sample.gxDps = rawGx / kGyroLsbPerDps - gyroOffsetX;
  sample.gyDps = rawGy / kGyroLsbPerDps - gyroOffsetY;
  sample.gzDps = rawGz / kGyroLsbPerDps - gyroOffsetZ;
  return true;
}

bool configureMpu6050() {
  Wire.begin(kSdaPin, kSclPin, 400000);
  delay(100);

  Wire.beginTransmission(kMpuAddress);
  if (Wire.endTransmission(true) != 0) return false;

  // PLL clock, 44 Hz DLPF, 100 Hz sample rate, +/-2000 dps, +/-16 g.
  return writeRegister(0x6B, 0x01) && writeRegister(0x1A, 0x03) &&
         writeRegister(0x19, 0x09) && writeRegister(0x1B, 0x18) &&
         writeRegister(0x1C, 0x18);
}

bool calibrateStationaryReference() {
  double ax = 0.0;
  double ay = 0.0;
  double az = 0.0;
  double gx = 0.0;
  double gy = 0.0;
  double gz = 0.0;
  double gyroEnergy = 0.0;
  crashguard::Sample sample{};

  for (size_t i = 0; i < kCalibrationSamples; ++i) {
    if (!readRaw(sample)) return false;
    ax += sample.axG;
    ay += sample.ayG;
    az += sample.azG;
    gx += sample.gxDps;
    gy += sample.gyDps;
    gz += sample.gzDps;
    gyroEnergy += sample.gxDps * sample.gxDps +
                  sample.gyDps * sample.gyDps +
                  sample.gzDps * sample.gzDps;
    delay(10);
  }

  const float count = static_cast<float>(kCalibrationSamples);
  const float meanAx = ax / count;
  const float meanAy = ay / count;
  const float meanAz = az / count;
  const float gyroRms = sqrt(gyroEnergy / count);
  const float gravityNorm = sqrt(meanAx * meanAx + meanAy * meanAy +
                                 meanAz * meanAz);
  if (gravityNorm < 0.85f || gravityNorm > 1.15f || gyroRms > 5.0f) {
    Serial.printf("CALIBRATION_RETRY gravity=%.3f gyro_rms=%.2f\n",
                  gravityNorm, gyroRms);
    return false;
  }

  gyroOffsetX = gx / count;
  gyroOffsetY = gy / count;
  gyroOffsetZ = gz / count;
  return detector.setReferenceGravity(meanAx, meanAy, meanAz);
}

const char *stateName(crashguard::State state) {
  switch (state) {
    case crashguard::State::Idle: return "IDLE";
    case crashguard::State::Correlating: return "CORRELATING";
    case crashguard::State::VerifyingRest: return "VERIFYING_REST";
    case crashguard::State::Countdown: return "COUNTDOWN";
    case crashguard::State::AlertSent: return "ALERT_SENT";
  }
  return "UNKNOWN";
}

void setLocalAlarm(bool enabled) {
  digitalWrite(kLedPin, enabled ? HIGH : LOW);
  if (enabled) {
    tone(kBuzzerPin, 2400);
  } else {
    noTone(kBuzzerPin);
    digitalWrite(kBuzzerPin, LOW);
  }
}

#if CRASHGUARD_HAS_SECRETS
String urlEncode(const String &input) {
  const char hex[] = "0123456789ABCDEF";
  String encoded;
  encoded.reserve(input.length() * 3);
  for (size_t i = 0; i < input.length(); ++i) {
    const uint8_t c = static_cast<uint8_t>(input[i]);
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
        (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.') {
      encoded += static_cast<char>(c);
    } else {
      encoded += '%';
      encoded += hex[c >> 4];
      encoded += hex[c & 0x0f];
    }
  }
  return encoded;
}
#endif

bool sendBlynkCrashEvent(const crashguard::Features &features) {
#if CRASHGUARD_HAS_SECRETS
  if (WiFi.status() != WL_CONNECTED) return false;

  String description = "CrashGuard confirmed an inertial event; ";
  description += "confirmation state a=" + String(features.accelerationG, 2) + "g, ";
  description += "omega=" + String(features.angularRateDps, 0) + "dps, ";
  description += "tilt=" + String(features.tiltDeg, 0) + "deg. ";
  description += "Location unavailable: no GNSS or companion GPS fix.";

  const String url = String("https://blynk.cloud/external/api/logEvent") +
                     "?token=" + CRASHGUARD_BLYNK_TOKEN +
                     "&code=crash_confirmed&description=" +
                     urlEncode(description);
  HTTPClient https;
  https.setConnectTimeout(5000);
  if (!https.begin(url)) return false;
  const int status = https.GET();
  https.end();
  return status >= 200 && status < 300;
#else
  (void)features;
  return false;
#endif
}

void connectNetworkWithoutBlockingDetection() {
#if CRASHGUARD_HAS_SECRETS
  WiFi.mode(WIFI_STA);
  WiFi.begin(CRASHGUARD_WIFI_SSID, CRASHGUARD_WIFI_PASSWORD);
  Serial.println("WIFI_CONNECTING");
#else
  Serial.println("CLOUD_DISABLED copy secrets.h.example to secrets.h");
#endif
}

void printEvent(crashguard::Event events, const crashguard::Features &f) {
  if (crashguard::hasEvent(events, crashguard::RideBecameActive)) {
    Serial.println("RIDE_ACTIVE");
  }
  if (crashguard::hasEvent(events, crashguard::CandidateStarted)) {
    Serial.printf("CANDIDATE a=%.2f omega=%.1f tilt=%.1f\n",
                  f.accelerationG, f.angularRateDps, f.tiltDeg);
  }
  if (crashguard::hasEvent(events, crashguard::RotationConfirmed)) {
    Serial.println("ROTATION_CONFIRMED");
  }
  if (crashguard::hasEvent(events, crashguard::CandidateRejected)) {
    Serial.println("CANDIDATE_REJECTED");
  }
  if (crashguard::hasEvent(events, crashguard::CrashConfirmed)) {
    setLocalAlarm(true);
    Serial.println("CRASH_CONFIRMED countdown=15s");
  }
  if (crashguard::hasEvent(events, crashguard::AlertDue)) {
    const bool delivered = sendBlynkCrashEvent(f);
    Serial.printf("ALERT_SENT cloud_delivery=%s\n", delivered ? "ok" : "not_available");
  }
}

float readBatteryVoltage() {
  // Production circuit uses a 100k/100k divider and 100 nF ADC capacitor.
  return 2.0f * analogReadMilliVolts(kBatteryPin) / 1000.0f;
}

}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(kLedPin, OUTPUT);
  pinMode(kBuzzerPin, OUTPUT);
  pinMode(kCancelPin, INPUT_PULLUP);
  pinMode(kBatteryPin, INPUT);
  setLocalAlarm(false);

  if (!configureMpu6050()) {
    Serial.println("FATAL MPU6050_NOT_FOUND");
    while (true) delay(1000);
  }

  Serial.println("CALIBRATING keep vehicle stationary and upright");
  while (!calibrateStationaryReference()) delay(250);
  connectNetworkWithoutBlockingDetection();
  nextSampleUs = micros();
  Serial.printf("READY sample_hz=100 battery=%.2fV\n", readBatteryVoltage());
}

void loop() {
  const bool buttonPressed = digitalRead(kCancelPin) == LOW;
  if (buttonPressed && !lastButtonPressed) {
    const crashguard::Event event = detector.cancel();
    if (crashguard::hasEvent(event, crashguard::Cancelled)) {
      setLocalAlarm(false);
      Serial.println("ALERT_CANCELLED");
    } else if (detector.state() == crashguard::State::AlertSent) {
      setLocalAlarm(false);
      detector.rearm();
      Serial.println("ALERT_ACKNOWLEDGED");
    }
  }
  lastButtonPressed = buttonPressed;

  const uint32_t nowUs = micros();
  if (static_cast<int32_t>(nowUs - nextSampleUs) < 0) return;
  nextSampleUs += kSamplePeriodUs;
  if (static_cast<int32_t>(nowUs - nextSampleUs) >
      static_cast<int32_t>(5 * kSamplePeriodUs)) {
    nextSampleUs = nowUs + kSamplePeriodUs;
    Serial.println("WARN sample_deadline_missed");
  }

  crashguard::Sample sample{};
  if (!readRaw(sample)) {
    Serial.println("WARN MPU6050_READ_FAILED");
    return;
  }
  const crashguard::Event events = detector.update(sample);
  printEvent(events, detector.features());

  static crashguard::State lastState = crashguard::State::Idle;
  if (detector.state() != lastState) {
    Serial.printf("STATE %s\n", stateName(detector.state()));
    lastState = detector.state();
  }
}
