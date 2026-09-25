#!/usr/bin/env python3
"""Deterministic Python detection engine and baseline replay.

Implements:
1. CrashGuard detector (exact port of wokwi/crash_detector.h)
2. Boubezoul et al. (2013) published motorcycle fall detection algorithm
3. Strict ordered rule comparison baseline
4. Acceleration-only comparison baseline
5. McNemar's paired statistical hypothesis test
"""

from __future__ import annotations

import csv
import gzip
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats


@dataclass
class Sample:
    time_ms: int
    ax_g: float
    ay_g: float
    az_g: float
    gx_dps: float
    gy_dps: float
    gz_dps: float


@dataclass
class Features:
    acceleration_g: float
    angular_rate_dps: float
    tilt_deg: float


class CrashGuardDetector:
    """Exact Python replica of crashguard::Detector from wokwi/crash_detector.h."""

    def __init__(
        self,
        high_impact_g: float = 2.0,
        low_impact_g: float = 0.35,
        rotation_dps: float = 90.0,
        tilt_deg: float = 55.0,
        rest_min_g: float = 0.70,
        rest_max_g: float = 1.30,
        rest_max_rotation_dps: float = 30.0,
        activity_accel_delta_g: float = 0.08,
        activity_rotation_dps: float = 4.0,
        ride_qualification_ms: int = 1000,
        ride_memory_ms: int = 5000,
        correlation_ms: int = 750,
        verification_timeout_ms: int = 6000,
        rest_hold_ms: int = 2000,
        cancel_window_ms: int = 15000,
    ):
        self.high_impact_g = high_impact_g
        self.low_impact_g = low_impact_g
        self.rotation_dps = rotation_dps
        self.tilt_deg = tilt_deg
        self.rest_min_g = rest_min_g
        self.rest_max_g = rest_max_g
        self.rest_max_rotation_dps = rest_max_rotation_dps
        self.activity_accel_delta_g = activity_accel_delta_g
        self.activity_rotation_dps = activity_rotation_dps
        self.ride_qualification_ms = ride_qualification_ms
        self.ride_memory_ms = ride_memory_ms
        self.correlation_ms = correlation_ms
        self.verification_timeout_ms = verification_timeout_ms
        self.rest_hold_ms = rest_hold_ms
        self.cancel_window_ms = cancel_window_ms

        self.reset()

    def reset(self) -> None:
        self.state = "IDLE"
        self.ref_x = 0.0
        self.ref_y = 0.0
        self.ref_z = 1.0
        self.ref_norm = 1.0

        self.ride_active_until_ms = 0
        self.activity_evidence_ms = 0
        self.last_activity_update_ms = 0
        self.have_activity_clock = False

        self.last_rotation_ms = 0
        self.have_rotation_history = False

        self.candidate_start_ms = 0
        self.rest_start_ms = 0
        self.countdown_start_ms = 0
        self.last_features = Features(1.0, 0.0, 0.0)

    def set_reference_gravity(self, x_g: float, y_g: float, z_g: float) -> bool:
        norm = math.sqrt(x_g * x_g + y_g * y_g + z_g * z_g)
        if not math.isfinite(norm) or norm < 0.70 or norm > 1.30:
            return False
        self.ref_x = x_g
        self.ref_y = y_g
        self.ref_z = z_g
        self.ref_norm = norm
        return True

    def calculate_features(self, s: Sample) -> Features:
        accel = math.sqrt(s.ax_g * s.ax_g + s.ay_g * s.ay_g + s.az_g * s.az_g)
        gyro = math.sqrt(s.gx_dps * s.gx_dps + s.gy_dps * s.gy_dps + s.gz_dps * s.gz_dps)
        denom = accel * self.ref_norm
        if denom < 1e-6:
            tilt = 0.0
        else:
            cosine = (s.ax_g * self.ref_x + s.ay_g * self.ref_y + s.az_g * self.ref_z) / denom
            cosine = max(-1.0, min(1.0, cosine))
            tilt = math.acos(cosine) * 57.2957795131
        return Features(accel, gyro, tilt)

    def update(self, s: Sample) -> Tuple[bool, bool]:
        """Returns (candidate_started, crash_confirmed)."""
        candidate_started = False
        crash_confirmed = False

        self.last_features = self.calculate_features(s)
        was_ride_active = (self.ride_active_until_ms != 0) and ((self.ride_active_until_ms - s.time_ms) >= 0)

        high_rotation = self.last_features.angular_rate_dps >= self.rotation_dps
        recent_rotation = high_rotation or (
            self.have_rotation_history and (s.time_ms - self.last_rotation_ms <= self.correlation_ms)
        )

        if high_rotation:
            self.last_rotation_ms = s.time_ms
            self.have_rotation_history = True

        if self.state == "IDLE":
            impact = (self.last_features.acceleration_g >= self.high_impact_g) or (
                self.last_features.acceleration_g <= self.low_impact_g
            )
            if was_ride_active and impact:
                self.state = "VERIFYING_REST" if recent_rotation else "CORRELATING"
                self.candidate_start_ms = s.time_ms
                self.rest_start_ms = 0
                candidate_started = True

        elif self.state == "CORRELATING":
            if high_rotation:
                self.state = "VERIFYING_REST"
                self.rest_start_ms = 0
            elif (s.time_ms - self.candidate_start_ms) > self.correlation_ms:
                self.state = "IDLE"

        elif self.state == "VERIFYING_REST":
            stable_tilt = (
                self.last_features.tilt_deg >= self.tilt_deg
                and self.rest_min_g <= self.last_features.acceleration_g <= self.rest_max_g
                and self.last_features.angular_rate_dps <= self.rest_max_rotation_dps
            )
            if stable_tilt:
                if self.rest_start_ms == 0:
                    self.rest_start_ms = s.time_ms
                if (s.time_ms - self.rest_start_ms) >= self.rest_hold_ms:
                    self.state = "COUNTDOWN"
                    self.countdown_start_ms = s.time_ms
                    crash_confirmed = True
            else:
                self.rest_start_ms = 0

            if self.state == "VERIFYING_REST" and (s.time_ms - self.candidate_start_ms) > self.verification_timeout_ms:
                self.state = "IDLE"

        # Update ride activity evidence
        activity = (
            abs(self.last_features.acceleration_g - 1.0) >= self.activity_accel_delta_g
            or self.last_features.angular_rate_dps >= self.activity_rotation_dps
        )
        if self.state == "IDLE":
            step_ms = 0
            if self.have_activity_clock:
                step_ms = s.time_ms - self.last_activity_update_ms
                if step_ms > 200:
                    step_ms = 0
            self.last_activity_update_ms = s.time_ms
            self.have_activity_clock = True

            if activity:
                self.activity_evidence_ms = min(self.ride_qualification_ms, self.activity_evidence_ms + step_ms)
            else:
                decay = step_ms // 2
                self.activity_evidence_ms = max(0, self.activity_evidence_ms - decay)

            if self.activity_evidence_ms >= self.ride_qualification_ms:
                self.ride_active_until_ms = s.time_ms + self.ride_memory_ms

        return candidate_started, crash_confirmed


class Boubezoul2013Detector:
    """Published motorcycle fall detection algorithm (Boubezoul et al., 2013).
    
    Ref: A. Boubezoul, S. Espié, B. Larnaudie, S. Bouaziz,
    'A Simple Fall Detection Algorithm for Powered Two Wheelers',
    Control Engineering Practice 21(3): 286-297, 2013.
    """

    def __init__(
        self,
        omega_roll_th_dps: float = 60.0,
        impact_high_g: float = 2.5,
        impact_low_g: float = 0.40,
        critical_tilt_deg: float = 55.0,
        rest_min_g: float = 0.70,
        rest_max_g: float = 1.30,
        rest_max_omega_dps: float = 30.0,
        fall_window_ms: int = 2000,
        rest_hold_ms: int = 1500,
        timeout_ms: int = 6000,
    ):
        self.omega_roll_th_dps = omega_roll_th_dps
        self.impact_high_g = impact_high_g
        self.impact_low_g = impact_low_g
        self.critical_tilt_deg = critical_tilt_deg
        self.rest_min_g = rest_min_g
        self.rest_max_g = rest_max_g
        self.rest_max_omega_dps = rest_max_omega_dps
        self.fall_window_ms = fall_window_ms
        self.rest_hold_ms = rest_hold_ms
        self.timeout_ms = timeout_ms

        self.reset()

    def reset(self) -> None:
        self.state = "IDLE"  # IDLE, FALL_IN_PROGRESS, REST_VERIFICATION
        self.trigger_ms = 0
        self.rest_start_ms = 0
        self.detected = False
        self.detection_ms = -1

    def update(self, s: Sample, f: Features) -> None:
        if self.detected:
            return

        # Roll rate magnitude or shock
        roll_rate = abs(s.gx_dps)
        is_fall_inception = (
            roll_rate >= self.omega_roll_th_dps
            or f.acceleration_g >= self.impact_high_g
            or f.acceleration_g <= self.impact_low_g
        )

        if self.state == "IDLE":
            if is_fall_inception:
                self.state = "FALL_IN_PROGRESS"
                self.trigger_ms = s.time_ms

        elif self.state == "FALL_IN_PROGRESS":
            if f.tilt_deg >= self.critical_tilt_deg:
                self.state = "REST_VERIFICATION"
                self.rest_start_ms = s.time_ms
            elif (s.time_ms - self.trigger_ms) > self.fall_window_ms:
                self.state = "IDLE"

        elif self.state == "REST_VERIFICATION":
            at_rest = (
                f.tilt_deg >= self.critical_tilt_deg
                and self.rest_min_g <= f.acceleration_g <= self.rest_max_g
                and f.angular_rate_dps <= self.rest_max_omega_dps
            )
            if at_rest:
                if (s.time_ms - self.rest_start_ms) >= self.rest_hold_ms:
                    self.detected = True
                    self.detection_ms = s.time_ms
            else:
                self.rest_start_ms = s.time_ms  # Reset hold

            if not self.detected and (s.time_ms - self.trigger_ms) > self.timeout_ms:
                self.state = "IDLE"


class OrderedRuleDetector:
    """Strict ordered comparison rule matching detector_replay.cpp."""

    def __init__(self):
        self.state = "IDLE"  # IDLE, ROTATION, TILT
        self.impact_ms = 0
        self.tilt_start_ms = 0
        self.detected = False
        self.detection_ms = -1

    def update(self, s: Sample, f: Features) -> None:
        if self.detected:
            return
        if self.state == "IDLE":
            if f.acceleration_g >= 4.0:
                self.state = "ROTATION"
                self.impact_ms = s.time_ms
        elif self.state == "ROTATION":
            if f.angular_rate_dps >= 200.0 and (s.time_ms - self.impact_ms <= 500):
                self.state = "TILT"
            elif (s.time_ms - self.impact_ms) > 500:
                self.state = "IDLE"
        elif self.state == "TILT":
            at_rest = f.tilt_deg >= 60.0 and (0.70 <= f.acceleration_g <= 1.30)
            if at_rest:
                if self.tilt_start_ms == 0:
                    self.tilt_start_ms = s.time_ms
                if (s.time_ms - self.tilt_start_ms) >= 3000:
                    self.detected = True
                    self.detection_ms = s.time_ms
            else:
                self.tilt_start_ms = 0

            if not self.detected and (s.time_ms - self.impact_ms) > 8000:
                self.state = "IDLE"
                self.tilt_start_ms = 0


def replay_events(
    source_path: Path,
    custom_cg_config: Optional[Dict[str, float]] = None,
) -> List[Dict[str, object]]:
    """Replay IMU stream from a file (raw CSV or gzip) and compute all detector outputs."""
    is_gz = source_path.name.endswith(".gz")
    open_fn = gzip.open if is_gz else open

    results: List[Dict[str, object]] = []
    active_id: Optional[str] = None
    cur_res: Dict[str, object] = {}

    detector = CrashGuardDetector(**(custom_cg_config or {}))
    detector.set_reference_gravity(0.0, 0.0, 1.0)
    boubezoul = Boubezoul2013Detector()
    ordered = OrderedRuleDetector()

    cg_candidate_ms = -1

    with open_fn(source_path, "rt", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)

        for row in reader:
            if not row or len(row) < 10:
                continue
            event_id = row[0]
            label = int(row[1])
            scenario = row[2]
            time_ms = int(row[3])
            s = Sample(
                time_ms=time_ms,
                ax_g=float(row[4]),
                ay_g=float(row[5]),
                az_g=float(row[6]),
                gx_dps=float(row[7]),
                gy_dps=float(row[8]),
                gz_dps=float(row[9]),
            )

            if event_id != active_id:
                if cur_res:
                    results.append(cur_res)
                active_id = event_id
                cur_res = {
                    "event_id": event_id,
                    "label": label,
                    "scenario": scenario,
                    "baseline_prediction": 0,
                    "ordered_prediction": 0,
                    "boubezoul_prediction": 0,
                    "crashguard_prediction": 0,
                    "baseline_detection_ms": -1,
                    "ordered_detection_ms": -1,
                    "boubezoul_detection_ms": -1,
                    "crashguard_detection_ms": -1,
                    "baseline_confirmation_delay_ms": -1,
                    "ordered_confirmation_delay_ms": -1,
                    "boubezoul_confirmation_delay_ms": -1,
                    "crashguard_confirmation_delay_ms": -1,
                }
                detector.reset()
                detector.set_reference_gravity(0.0, 0.0, 1.0)
                boubezoul.reset()
                ordered = OrderedRuleDetector()
                cg_candidate_ms = -1

            f = detector.calculate_features(s)

            # 1. Baseline
            if cur_res["baseline_prediction"] == 0 and f.acceleration_g >= 2.0:
                cur_res["baseline_prediction"] = 1
                cur_res["baseline_detection_ms"] = s.time_ms
                cur_res["baseline_confirmation_delay_ms"] = 0

            # 2. CrashGuard
            cand_started, confirmed = detector.update(s)
            if cand_started:
                cg_candidate_ms = s.time_ms
            if cur_res["crashguard_prediction"] == 0 and confirmed:
                cur_res["crashguard_prediction"] = 1
                cur_res["crashguard_detection_ms"] = s.time_ms
                cur_res["crashguard_confirmation_delay_ms"] = (
                    s.time_ms - cg_candidate_ms if cg_candidate_ms >= 0 else 0
                )

            # 3. Boubezoul (2013)
            boubezoul.update(s, f)
            if cur_res["boubezoul_prediction"] == 0 and boubezoul.detected:
                cur_res["boubezoul_prediction"] = 1
                cur_res["boubezoul_detection_ms"] = boubezoul.detection_ms
                cur_res["boubezoul_confirmation_delay_ms"] = (
                    boubezoul.detection_ms - boubezoul.trigger_ms if boubezoul.trigger_ms >= 0 else 0
                )

            # 4. Strict Ordered
            ordered.update(s, f)
            if cur_res["ordered_prediction"] == 0 and ordered.detected:
                cur_res["ordered_prediction"] = 1
                cur_res["ordered_detection_ms"] = ordered.detection_ms
                cur_res["ordered_confirmation_delay_ms"] = (
                    ordered.detection_ms - ordered.impact_ms if ordered.impact_ms >= 0 else 0
                )

        if cur_res:
            results.append(cur_res)

    return results


def mcnemar_test(
    pred_a: np.ndarray,
    pred_b: np.ndarray,
    ground_truth: np.ndarray,
) -> Dict[str, float]:
    """Perform McNemar's paired test with continuity correction and exact binomial p-value."""
    correct_a = (pred_a == ground_truth)
    correct_b = (pred_b == ground_truth)

    b = int(np.sum(correct_a & ~correct_b))  # A correct, B wrong
    c = int(np.sum(~correct_a & correct_b))  # A wrong, B correct
    a = int(np.sum(correct_a & correct_b))   # both correct
    d = int(np.sum(~correct_a & ~correct_b)) # both wrong

    total_discordant = b + c
    if total_discordant == 0:
        return {
            "statistic": 0.0,
            "p_value": 1.0,
            "b": b,
            "c": c,
            "a": a,
            "d": d,
            "method": "exact_binomial",
        }

    # Edwards continuity correction
    statistic = float((abs(b - c) - 1.0) ** 2 / total_discordant) if abs(b - c) >= 1.0 else 0.0
    p_asymptotic = float(1.0 - stats.chi2.cdf(statistic, df=1))

    # Exact two-sided binomial p-value
    exact_res = stats.binomtest(min(b, c), total_discordant, 0.5, alternative="two-sided")
    p_exact = float(exact_res.pvalue)

    return {
        "statistic": statistic,
        "p_value": p_exact if total_discordant < 25 else p_asymptotic,
        "p_exact": p_exact,
        "p_asymptotic": p_asymptotic,
        "b": b,
        "c": c,
        "a": a,
        "d": d,
        "method": "exact_binomial" if total_discordant < 25 else "mcnemar_continuity",
    }
