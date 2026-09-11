#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>

#include "../wokwi/crash_detector.h"

namespace {

crashguard::Sample sample(uint32_t timeMs, float ax, float ay, float az,
                          float gx = 0.0f, float gy = 0.0f,
                          float gz = 0.0f) {
  return {timeMs, ax, ay, az, gx, gy, gz};
}

void qualifyRide(crashguard::Detector &detector, uint32_t startMs = 0) {
  for (uint32_t offset = 0; offset <= 1300; offset += 10) {
    detector.update(sample(startMs + offset, 0.0f, 0.0f, 1.0f,
                           0.0f, 0.0f, 8.0f));
  }
}

bool feedTiltUntilConfirmed(crashguard::Detector &detector, uint32_t startMs) {
  for (uint32_t offset = 0; offset <= 2300; offset += 10) {
    const auto event = detector.update(
        sample(startMs + offset, 0.0f, 0.94f, 0.342f));
    if (crashguard::hasEvent(event, crashguard::CrashConfirmed)) return true;
  }
  return false;
}

void testRotationBeforeImpact() {
  crashguard::Detector detector;
  qualifyRide(detector);
  detector.update(sample(1500, 0.0f, 0.0f, 1.0f, 130.0f));
  const auto candidate = detector.update(sample(1600, 0.0f, 0.0f, 3.0f));
  assert(crashguard::hasEvent(candidate, crashguard::CandidateStarted));
  assert(crashguard::hasEvent(candidate, crashguard::RotationConfirmed));
  assert(feedTiltUntilConfirmed(detector, 1610));
}

void testPotholeRejected() {
  crashguard::Detector detector;
  qualifyRide(detector);
  detector.update(sample(1500, 0.0f, 0.0f, 3.2f));
  bool rejected = false;
  for (uint32_t timeMs = 1510; timeMs < 2500; timeMs += 10) {
    const auto event = detector.update(sample(timeMs, 0.0f, 0.0f, 1.0f));
    rejected |= crashguard::hasEvent(event, crashguard::CandidateRejected);
  }
  assert(rejected);
  assert(detector.state() == crashguard::State::Idle);
}

void testParkedTipoverRejected() {
  crashguard::Detector detector;
  for (uint32_t timeMs = 0; timeMs < 3000; timeMs += 10) {
    detector.update(sample(timeMs, 0.0f, 0.0f, 1.0f));
  }
  for (uint32_t timeMs = 3000; timeMs < 3500; timeMs += 10) {
    detector.update(sample(timeMs, 0.0f, 0.0f, 1.0f, 130.0f));
  }
  const auto impact = detector.update(sample(3500, 0.0f, 0.0f, 3.0f));
  assert(!crashguard::hasEvent(impact, crashguard::CandidateStarted));
  assert(!feedTiltUntilConfirmed(detector, 3510));
}

void testCancelWindow() {
  crashguard::Detector detector;
  qualifyRide(detector);
  detector.update(sample(1500, 0.0f, 0.0f, 1.0f, 130.0f));
  detector.update(sample(1600, 0.0f, 0.0f, 3.0f));
  assert(feedTiltUntilConfirmed(detector, 1610));
  assert(detector.state() == crashguard::State::Countdown);
  const auto event = detector.cancel();
  assert(crashguard::hasEvent(event, crashguard::Cancelled));
  assert(detector.state() == crashguard::State::Idle);
}

}  // namespace

int main() {
  testRotationBeforeImpact();
  testPotholeRejected();
  testParkedTipoverRejected();
  testCancelWindow();
  std::cout << "detector tests passed\n";
  return 0;
}
