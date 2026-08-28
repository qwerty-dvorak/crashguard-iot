#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

#include "../wokwi/crash_detector.h"

namespace {

struct LegacyDetector {
  enum class State { Idle, Rotation, Tilt };
  State state = State::Idle;
  uint32_t impactMs = 0;
  uint32_t tiltStartMs = 0;
  bool detected = false;
  uint32_t detectionMs = 0;

  void update(const crashguard::Sample &sample,
              const crashguard::Features &features) {
    if (detected) return;
    switch (state) {
      case State::Idle:
        if (features.accelerationG >= 4.0f) {
          state = State::Rotation;
          impactMs = sample.timeMs;
        }
        break;
      case State::Rotation:
        if (features.angularRateDps >= 200.0f &&
            sample.timeMs - impactMs <= 500) {
          state = State::Tilt;
        } else if (sample.timeMs - impactMs > 500) {
          state = State::Idle;
        }
        break;
      case State::Tilt: {
        const bool atRest = features.tiltDeg >= 60.0f &&
                            features.accelerationG >= 0.70f &&
                            features.accelerationG <= 1.30f;
        if (atRest) {
          if (tiltStartMs == 0) tiltStartMs = sample.timeMs;
          if (sample.timeMs - tiltStartMs >= 3000) {
            detected = true;
            detectionMs = sample.timeMs;
          }
        } else {
          tiltStartMs = 0;
        }
        if (!detected && sample.timeMs - impactMs > 8000) {
          state = State::Idle;
          tiltStartMs = 0;
        }
        break;
      }
    }
  }
};

struct EventResult {
  std::string id;
  int label = 0;
  std::string scenario;
  bool baseline = false;
  bool legacy = false;
  bool proposed = false;
  int64_t baselineMs = -1;
  int64_t legacyMs = -1;
  int64_t proposedMs = -1;
  int64_t legacyConfirmationDelayMs = -1;
  int64_t proposedCandidateMs = -1;
  int64_t proposedConfirmationDelayMs = -1;
};

void writeResult(const EventResult &result) {
  if (result.id.empty()) return;
  std::cout << result.id << ',' << result.label << ',' << result.scenario << ','
            << static_cast<int>(result.baseline) << ','
            << static_cast<int>(result.legacy) << ','
            << static_cast<int>(result.proposed) << ','
            << result.baselineMs << ',' << result.legacyMs << ','
            << result.proposedMs << ','
            << (result.baseline ? 0 : -1) << ','
            << result.legacyConfirmationDelayMs << ','
            << result.proposedConfirmationDelayMs << '\n';
}

bool parseLine(const std::string &line, std::string &eventId, int &label,
               std::string &scenario, crashguard::Sample &sample) {
  std::stringstream stream(line);
  std::string field;
  if (!std::getline(stream, eventId, ',')) return false;
  if (!std::getline(stream, field, ',')) return false;
  label = std::atoi(field.c_str());
  if (!std::getline(stream, scenario, ',')) return false;
  if (!std::getline(stream, field, ',')) return false;
  sample.timeMs = static_cast<uint32_t>(std::strtoul(field.c_str(), nullptr, 10));
  float values[6]{};
  for (float &value : values) {
    if (!std::getline(stream, field, ',')) return false;
    value = std::strtof(field.c_str(), nullptr);
  }
  sample.axG = values[0];
  sample.ayG = values[1];
  sample.azG = values[2];
  sample.gxDps = values[3];
  sample.gyDps = values[4];
  sample.gzDps = values[5];
  return true;
}

}  // namespace

int main() {
  std::ios::sync_with_stdio(false);
  std::cout << "event_id,label,scenario,baseline_prediction,legacy_prediction,"
               "proposed_prediction,baseline_detection_ms,legacy_detection_ms,"
               "proposed_detection_ms,baseline_confirmation_delay_ms,"
               "legacy_confirmation_delay_ms,"
               "proposed_confirmation_delay_ms\n";

  std::string line;
  std::getline(std::cin, line);  // CSV header.
  std::string activeId;
  EventResult result;
  crashguard::Detector detector;
  LegacyDetector legacy;

  while (std::getline(std::cin, line)) {
    if (line.empty()) continue;
    std::string eventId;
    std::string scenario;
    int label = 0;
    crashguard::Sample sample{};
    if (!parseLine(line, eventId, label, scenario, sample)) {
      std::cerr << "Invalid input row: " << line.substr(0, 120) << '\n';
      return 2;
    }

    if (activeId != eventId) {
      writeResult(result);
      activeId = eventId;
      result = EventResult{};
      result.id = eventId;
      result.label = label;
      result.scenario = scenario;
      detector.reset();
      detector.setReferenceGravity(0.0f, 0.0f, 1.0f);
      legacy = LegacyDetector{};
    }

    const float acceleration = std::sqrt(sample.axG * sample.axG +
                                         sample.ayG * sample.ayG +
                                         sample.azG * sample.azG);
    if (!result.baseline && acceleration >= 2.0f) {
      result.baseline = true;
      result.baselineMs = sample.timeMs;
    }

    const crashguard::Event events = detector.update(sample);
    if (crashguard::hasEvent(events, crashguard::CandidateStarted)) {
      result.proposedCandidateMs = sample.timeMs;
    }
    if (!result.proposed &&
        crashguard::hasEvent(events, crashguard::CrashConfirmed)) {
      result.proposed = true;
      result.proposedMs = sample.timeMs;
      result.proposedConfirmationDelayMs =
          result.proposedMs - result.proposedCandidateMs;
    }

    legacy.update(sample, detector.features());
    if (!result.legacy && legacy.detected) {
      result.legacy = true;
      result.legacyMs = legacy.detectionMs;
      result.legacyConfirmationDelayMs =
          result.legacyMs - legacy.impactMs;
    }
  }
  writeResult(result);
  return 0;
}
