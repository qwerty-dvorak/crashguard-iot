#!/usr/bin/env python3
"""Generate a deterministic physics-informed motorcycle IMU dataset.

The generator is not a claim of road-crash validation. It is a controlled
robustness experiment for the exact firmware detector. Each event contains
gravity projected into the motorcycle body frame, manoeuvre acceleration,
angular-rate dynamics, sensor noise, and bias.
"""

from __future__ import annotations

import csv
import gzip
import io
import math
from pathlib import Path

import numpy as np

SEED = 20260828
SAMPLE_HZ = 100
DURATION_S = 10.0
TRIALS_PER_SCENARIO = 75
SCENARIOS = (
    "normal_riding",
    "pothole",
    "speed_breaker",
    "hard_brake",
    "sharp_turn",
    "parked_tipover",
    "impact_recovery",
    "crash_lowside",
    "crash_highside",
)
POSITIVE_SCENARIOS = {"crash_lowside", "crash_highside"}


def smooth_step(time: np.ndarray, start: float, end: float) -> np.ndarray:
    x = np.clip((time - start) / max(end - start, 1.0e-6), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def gaussian(time: np.ndarray, center: float, sigma: float) -> np.ndarray:
    return np.exp(-0.5 * ((time - center) / sigma) ** 2)


def pulse(time: np.ndarray, start: float, end: float) -> np.ndarray:
    return smooth_step(time, start, start + 0.15) - smooth_step(
        time, end - 0.15, end
    )


def simulate_event(
    scenario: str, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    time = np.arange(0.0, DURATION_S, 1.0 / SAMPLE_HZ)
    n = len(time)
    active = scenario != "parked_tipover"

    roll = np.zeros(n)
    pitch = np.zeros(n)
    yaw = np.zeros(n)
    linear = np.zeros((n, 3))

    if active:
        roll += np.deg2rad(
            2.5 * np.sin(2 * np.pi * (0.35 + rng.uniform(-0.05, 0.05)) * time)
        )
        pitch += np.deg2rad(1.4 * np.sin(2 * np.pi * 0.22 * time + 0.6))
        yaw += np.deg2rad(3.0 * np.sin(2 * np.pi * 0.18 * time))
        linear[:, 2] += 0.035 * np.sin(2 * np.pi * 8.0 * time)
        linear[:, 0] += 0.025 * np.sin(2 * np.pi * 1.2 * time)

    event_time = rng.uniform(3.8, 5.2)
    if scenario == "normal_riding":
        linear[:, 1] += 0.08 * np.sin(2 * np.pi * 0.3 * time)

    elif scenario == "pothole":
        peak = rng.uniform(1.3, 5.2)
        linear[:, 2] += peak * gaussian(time, event_time, rng.uniform(0.018, 0.045))
        linear[:, 2] -= 0.45 * gaussian(time, event_time + 0.10, 0.06)
        pitch += np.deg2rad(rng.uniform(2.0, 9.0)) * (
            smooth_step(time, event_time - 0.12, event_time)
            - smooth_step(time, event_time + 0.02, event_time + 0.25)
        )

    elif scenario == "speed_breaker":
        peak = rng.uniform(0.8, 3.0)
        linear[:, 2] += peak * gaussian(time, event_time, rng.uniform(0.07, 0.14))
        pitch += np.deg2rad(rng.uniform(5.0, 17.0)) * (
            smooth_step(time, event_time - 0.25, event_time)
            - smooth_step(time, event_time + 0.10, event_time + 0.45)
        )

    elif scenario == "hard_brake":
        deceleration = rng.uniform(0.45, 1.05)
        linear[:, 0] -= deceleration * pulse(time, event_time - 0.25, event_time + 0.8)
        pitch += np.deg2rad(rng.uniform(5.0, 15.0)) * pulse(
            time, event_time - 0.2, event_time + 0.9
        )

    elif scenario == "sharp_turn":
        lean = np.deg2rad(rng.uniform(28.0, 53.0))
        turn = pulse(time, event_time - 0.6, event_time + rng.uniform(1.2, 2.5))
        roll += lean * turn
        linear[:, 1] += rng.uniform(0.25, 0.75) * turn

    elif scenario == "parked_tipover":
        final_roll = np.deg2rad(rng.uniform(65.0, 100.0))
        roll += final_roll * smooth_step(time, event_time - 0.55, event_time + 0.10)
        linear[:, 2] += rng.uniform(1.2, 5.5) * gaussian(
            time, event_time + 0.08, rng.uniform(0.02, 0.05)
        )

    elif scenario == "impact_recovery":
        angle = np.deg2rad(rng.uniform(48.0, 78.0))
        hold = rng.uniform(0.7, 2.1)
        roll += angle * (
            smooth_step(time, event_time - 0.35, event_time + 0.10)
            - smooth_step(time, event_time + hold, event_time + hold + 0.5)
        )
        linear[:, 2] += rng.uniform(1.2, 4.5) * gaussian(
            time, event_time, rng.uniform(0.025, 0.06)
        )

    elif scenario in POSITIVE_SCENARIOS:
        if scenario == "crash_lowside":
            final_roll = np.deg2rad(rng.uniform(48.0, 105.0))
            rotation_duration = rng.uniform(0.55, 1.10)
            impact = rng.uniform(0.8, 5.5)
            vertical_loss = rng.uniform(0.35, 0.85)
        else:
            final_roll = np.deg2rad(rng.uniform(70.0, 135.0))
            rotation_duration = rng.uniform(0.30, 0.70)
            impact = rng.uniform(3.0, 11.5)
            vertical_loss = rng.uniform(0.55, 0.95)
        roll += final_roll * smooth_step(
            time, event_time - rotation_duration, event_time + 0.20
        )
        yaw += 0.35 * final_roll * smooth_step(
            time, event_time - 0.4, event_time + 0.35
        )
        linear[:, 2] -= vertical_loss * gaussian(
            time, event_time - 0.15, rng.uniform(0.07, 0.13)
        )
        direction = rng.normal(size=3)
        direction /= np.linalg.norm(direction)
        linear += (
            impact
            * gaussian(time, event_time, rng.uniform(0.018, 0.055))[:, None]
            * direction[None, :]
        )
        ring = gaussian(time, event_time + 0.25, 0.22)
        linear[:, 2] += 0.18 * np.sin(2 * np.pi * 12.0 * time) * ring

    sin_roll = np.sin(roll)
    cos_roll = np.cos(roll)
    sin_pitch = np.sin(pitch)
    cos_pitch = np.cos(pitch)
    gravity_body = np.column_stack(
        (-sin_pitch, sin_roll * cos_pitch, cos_roll * cos_pitch)
    )
    acceleration = gravity_body + linear

    gyro = np.column_stack(
        (
            np.gradient(roll, time),
            np.gradient(pitch, time),
            np.gradient(yaw, time),
        )
    )
    gyro = np.rad2deg(gyro)

    accel_bias = rng.normal(0.0, 0.018, size=3)
    gyro_bias = rng.normal(0.0, 0.8, size=3)
    acceleration += accel_bias + rng.normal(0.0, 0.022, size=(n, 3))
    gyro += gyro_bias + rng.normal(0.0, 1.5, size=(n, 3))

    # Match the configured MPU-6050 full-scale ranges used by the firmware.
    acceleration = np.clip(acceleration, -16.0, 16.0)
    gyro = np.clip(gyro, -2000.0, 2000.0)
    return acceleration, gyro


def main() -> None:
    review_dir = Path(__file__).resolve().parents[1]
    output_dir = review_dir / "data" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "simulated_imu.csv.gz"
    exemplar_path = output_dir / "exemplar_signals.csv"
    rng = np.random.default_rng(SEED)

    # mtime=0 and an empty embedded filename make the compressed bytes
    # reproducible, not merely the decompressed CSV values.
    with output_path.open("wb") as raw_handle:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_handle, mtime=0
        ) as compressed_handle:
            with io.TextIOWrapper(
                compressed_handle, newline="", encoding="utf-8"
            ) as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(
                    (
                        "event_id",
                        "label",
                        "scenario",
                        "time_ms",
                        "ax_g",
                        "ay_g",
                        "az_g",
                        "gx_dps",
                        "gy_dps",
                        "gz_dps",
                    )
                )
                exemplar_rows: list[tuple[object, ...]] = []
                event_number = 0
                for scenario in SCENARIOS:
                    for trial in range(TRIALS_PER_SCENARIO):
                        event_id = f"SIM-{event_number:04d}"
                        label = int(scenario in POSITIVE_SCENARIOS)
                        acceleration, gyro = simulate_event(scenario, rng)
                        for index in range(acceleration.shape[0]):
                            row = (
                                event_id,
                                label,
                                scenario,
                                index * 10,
                                *(f"{value:.6f}" for value in acceleration[index]),
                                *(f"{value:.6f}" for value in gyro[index]),
                            )
                            writer.writerow(row)
                            if trial == 0 and scenario in {
                                "pothole",
                                "parked_tipover",
                                "crash_lowside",
                            }:
                                exemplar_rows.append(row)
                        event_number += 1

    with exemplar_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            (
                "event_id",
                "label",
                "scenario",
                "time_ms",
                "ax_g",
                "ay_g",
                "az_g",
                "gx_dps",
                "gy_dps",
                "gz_dps",
            )
        )
        writer.writerows(exemplar_rows)

    print(f"generated {event_number} events at {output_path}")


if __name__ == "__main__":
    main()
