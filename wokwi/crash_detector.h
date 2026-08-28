#pragma once

#include <math.h>
#include <stdint.h>

namespace crashguard {

struct Sample {
  uint32_t timeMs;
  float axG;
  float ayG;
  float azG;
  float gxDps;
  float gyDps;
  float gzDps;
};

struct Features {
  float accelerationG;
  float angularRateDps;
  float tiltDeg;
};

struct Config {
  float highImpactG = 2.0f;
  float lowImpactG = 0.35f;
  float rotationDps = 90.0f;
  float tiltDeg = 55.0f;
  float restMinG = 0.70f;
  float restMaxG = 1.30f;
  float restMaxRotationDps = 30.0f;
  float activityAccelerationDeltaG = 0.08f;
  float activityRotationDps = 4.0f;
  uint32_t rideQualificationMs = 1000;
  uint32_t rideMemoryMs = 5000;
  uint32_t correlationMs = 750;
  uint32_t verificationTimeoutMs = 6000;
  uint32_t restHoldMs = 2000;
  uint32_t cancelWindowMs = 15000;
};

enum class State : uint8_t {
  Idle,
  Correlating,
  VerifyingRest,
  Countdown,
  AlertSent
};

enum Event : uint16_t {
  NoEvent = 0,
  RideBecameActive = 1u << 0,
  CandidateStarted = 1u << 1,
  RotationConfirmed = 1u << 2,
  CandidateRejected = 1u << 3,
  CrashConfirmed = 1u << 4,
  Cancelled = 1u << 5,
  AlertDue = 1u << 6
};

inline Event operator|(Event lhs, Event rhs) {
  return static_cast<Event>(static_cast<uint16_t>(lhs) |
                            static_cast<uint16_t>(rhs));
}

inline Event &operator|=(Event &lhs, Event rhs) {
  lhs = lhs | rhs;
  return lhs;
}

inline bool hasEvent(Event value, Event flag) {
  return (static_cast<uint16_t>(value) & static_cast<uint16_t>(flag)) != 0;
}

class Detector {
 public:
  explicit Detector(const Config &config = Config()) : config_(config) {
    reset();
  }

  void reset() {
    state_ = State::Idle;
    referenceX_ = 0.0f;
    referenceY_ = 0.0f;
    referenceZ_ = 1.0f;
    referenceNorm_ = 1.0f;
    rideActiveUntilMs_ = 0;
    activityEvidenceMs_ = 0;
    lastActivityUpdateMs_ = 0;
    haveActivityClock_ = false;
    lastRotationMs_ = 0;
    haveRotationHistory_ = false;
    candidateStartMs_ = 0;
    restStartMs_ = 0;
    countdownStartMs_ = 0;
    lastFeatures_ = {1.0f, 0.0f, 0.0f};
  }

  bool setReferenceGravity(float xG, float yG, float zG) {
    const float norm = magnitude(xG, yG, zG);
    if (!isfinite(norm) || norm < 0.70f || norm > 1.30f) {
      return false;
    }
    referenceX_ = xG;
    referenceY_ = yG;
    referenceZ_ = zG;
    referenceNorm_ = norm;
    return true;
  }

  Event update(const Sample &sample) {
    Event events = NoEvent;
    lastFeatures_ = calculateFeatures(sample);

    const bool wasRideActive = isDeadlineActive(sample.timeMs,
                                                 rideActiveUntilMs_);
    const bool highRotation =
        lastFeatures_.angularRateDps >= config_.rotationDps;
    const bool recentRotation =
        highRotation ||
        (haveRotationHistory_ &&
         elapsed(sample.timeMs, lastRotationMs_) <= config_.correlationMs);

    if (highRotation) {
      lastRotationMs_ = sample.timeMs;
      haveRotationHistory_ = true;
    }

    switch (state_) {
      case State::Idle: {
        const bool impact = lastFeatures_.accelerationG >= config_.highImpactG ||
                            lastFeatures_.accelerationG <= config_.lowImpactG;
        if (wasRideActive && impact) {
          state_ = recentRotation ? State::VerifyingRest : State::Correlating;
          candidateStartMs_ = sample.timeMs;
          restStartMs_ = 0;
          events |= CandidateStarted;
          if (recentRotation) {
            events |= RotationConfirmed;
          }
        }
        break;
      }

      case State::Correlating:
        if (highRotation) {
          state_ = State::VerifyingRest;
          restStartMs_ = 0;
          events |= RotationConfirmed;
        } else if (elapsed(sample.timeMs, candidateStartMs_) >
                   config_.correlationMs) {
          state_ = State::Idle;
          events |= CandidateRejected;
        }
        break;

      case State::VerifyingRest: {
        const bool stableTilt = lastFeatures_.tiltDeg >= config_.tiltDeg &&
                                lastFeatures_.accelerationG >= config_.restMinG &&
                                lastFeatures_.accelerationG <= config_.restMaxG &&
                                lastFeatures_.angularRateDps <=
                                    config_.restMaxRotationDps;
        if (stableTilt) {
          if (restStartMs_ == 0) {
            restStartMs_ = sample.timeMs;
          }
          if (elapsed(sample.timeMs, restStartMs_) >= config_.restHoldMs) {
            state_ = State::Countdown;
            countdownStartMs_ = sample.timeMs;
            events |= CrashConfirmed;
          }
        } else {
          restStartMs_ = 0;
        }

        if (state_ == State::VerifyingRest &&
            elapsed(sample.timeMs, candidateStartMs_) >
                config_.verificationTimeoutMs) {
          state_ = State::Idle;
          events |= CandidateRejected;
        }
        break;
      }

      case State::Countdown:
        if (elapsed(sample.timeMs, countdownStartMs_) >=
            config_.cancelWindowMs) {
          state_ = State::AlertSent;
          events |= AlertDue;
        }
        break;

      case State::AlertSent:
        break;
    }

    const bool activity =
        fabsf(lastFeatures_.accelerationG - 1.0f) >=
            config_.activityAccelerationDeltaG ||
        lastFeatures_.angularRateDps >= config_.activityRotationDps;
    if (state_ == State::Idle) {
      uint32_t stepMs = 0;
      if (haveActivityClock_) {
        stepMs = elapsed(sample.timeMs, lastActivityUpdateMs_);
        if (stepMs > 200) stepMs = 0;
      }
      lastActivityUpdateMs_ = sample.timeMs;
      haveActivityClock_ = true;
      if (activity) {
        activityEvidenceMs_ += stepMs;
        if (activityEvidenceMs_ > config_.rideQualificationMs) {
          activityEvidenceMs_ = config_.rideQualificationMs;
        }
      } else {
        const uint32_t decay = stepMs / 2;
        activityEvidenceMs_ = activityEvidenceMs_ > decay
                                  ? activityEvidenceMs_ - decay
                                  : 0;
      }
      if (activityEvidenceMs_ >= config_.rideQualificationMs) {
        const bool wasInactive = !wasRideActive;
        rideActiveUntilMs_ = sample.timeMs + config_.rideMemoryMs;
        if (wasInactive) {
          events |= RideBecameActive;
        }
      }
    }
    return events;
  }

  Event cancel() {
    if (state_ != State::Countdown) {
      return NoEvent;
    }
    state_ = State::Idle;
    restStartMs_ = 0;
    haveRotationHistory_ = false;
    return Cancelled;
  }

  void rearm() {
    state_ = State::Idle;
    restStartMs_ = 0;
    haveRotationHistory_ = false;
  }

  State state() const { return state_; }
  Features features() const { return lastFeatures_; }
  const Config &config() const { return config_; }

 private:
  static float magnitude(float x, float y, float z) {
    return sqrtf(x * x + y * y + z * z);
  }

  static uint32_t elapsed(uint32_t now, uint32_t then) {
    return now - then;
  }

  static bool isDeadlineActive(uint32_t now, uint32_t deadline) {
    return deadline != 0 && static_cast<int32_t>(deadline - now) >= 0;
  }

  Features calculateFeatures(const Sample &sample) const {
    Features result{};
    result.accelerationG = magnitude(sample.axG, sample.ayG, sample.azG);
    result.angularRateDps =
        magnitude(sample.gxDps, sample.gyDps, sample.gzDps);

    const float denominator = result.accelerationG * referenceNorm_;
    if (denominator < 1.0e-6f) {
      result.tiltDeg = 0.0f;
    } else {
      float cosine = (sample.axG * referenceX_ + sample.ayG * referenceY_ +
                      sample.azG * referenceZ_) /
                     denominator;
      if (cosine > 1.0f) cosine = 1.0f;
      if (cosine < -1.0f) cosine = -1.0f;
      result.tiltDeg = acosf(cosine) * 57.2957795131f;
    }
    return result;
  }

  Config config_;
  State state_;
  float referenceX_;
  float referenceY_;
  float referenceZ_;
  float referenceNorm_;
  uint32_t rideActiveUntilMs_;
  uint32_t activityEvidenceMs_;
  uint32_t lastActivityUpdateMs_;
  bool haveActivityClock_;
  uint32_t lastRotationMs_;
  bool haveRotationHistory_;
  uint32_t candidateStartMs_;
  uint32_t restStartMs_;
  uint32_t countdownStartMs_;
  Features lastFeatures_;
};

}  // namespace crashguard
