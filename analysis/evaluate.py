#!/usr/bin/env python3
"""Replay the firmware detector, audit external data, and render results."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import resample_poly

from generate_simulated_dataset import (
    DURATION_S,
    SAMPLE_HZ,
    SCENARIOS,
    SEED,
    TRIALS_PER_SCENARIO,
)


def wilson(successes: int, total: int) -> tuple[float, float]:
    if total == 0:
        return (float("nan"), float("nan"))
    z = 1.959963984540054
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    half = (
        z
        * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return center - half, center + half


def detector_config(review_dir: Path) -> dict[str, float]:
    text = (review_dir / "wokwi" / "crash_detector.h").read_text(encoding="utf-8")
    names = (
        "highImpactG",
        "lowImpactG",
        "rotationDps",
        "tiltDeg",
        "restMinG",
        "restMaxG",
        "restMaxRotationDps",
        "activityAccelerationDeltaG",
        "activityRotationDps",
        "rideQualificationMs",
        "rideMemoryMs",
        "correlationMs",
        "verificationTimeoutMs",
        "restHoldMs",
        "cancelWindowMs",
    )
    output: dict[str, float] = {}
    for name in names:
        match = re.search(rf"\b{name}\s*=\s*([0-9.]+)(?:f)?;", text)
        if not match:
            raise RuntimeError(f"cannot find detector setting {name}")
        output[name] = float(match.group(1))
    return output


def replay_detector(review_dir: Path) -> list[dict[str, str]]:
    executable = review_dir / "analysis" / "build" / "detector_replay"
    dataset = review_dir / "data" / "generated" / "simulated_imu.csv.gz"
    output = review_dir / "results" / "event_results.csv"
    with output.open("wb") as destination:
        replay = subprocess.Popen(
            [str(executable)], stdin=subprocess.PIPE, stdout=destination
        )
        assert replay.stdin is not None
        with gzip.open(dataset, "rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                replay.stdin.write(block)
        replay.stdin.close()
        return_code = replay.wait()
    if return_code != 0:
        raise RuntimeError(f"detector replay failed with {return_code}")
    with output.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def metric_summary(rows: list[dict[str, str]]) -> dict[str, dict[str, float | int]]:
    output: dict[str, dict[str, float | int]] = {}
    for model, column in (
        ("Acceleration-only baseline", "baseline_prediction"),
        ("Review-1 ordered logic", "legacy_prediction"),
        ("CrashGuard v2", "proposed_prediction"),
    ):
        labels = np.array([int(row["label"]) for row in rows], dtype=int)
        predictions = np.array([int(row[column]) for row in rows], dtype=int)
        tp = int(np.sum((labels == 1) & (predictions == 1)))
        tn = int(np.sum((labels == 0) & (predictions == 0)))
        fp = int(np.sum((labels == 0) & (predictions == 1)))
        fn = int(np.sum((labels == 1) & (predictions == 0)))
        sensitivity = tp / (tp + fn)
        specificity = tn / (tn + fp)
        precision = tp / (tp + fp) if tp + fp else 0.0
        f1 = 2 * precision * sensitivity / (precision + sensitivity)
        sens_low, sens_high = wilson(tp, tp + fn)
        spec_low, spec_high = wilson(tn, tn + fp)
        delay_column = column.replace("prediction", "confirmation_delay_ms")
        latencies = [
            int(row[delay_column])
            for row in rows
            if int(row["label"]) == 1 and int(row[delay_column]) >= 0
        ]
        output[model] = {
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "sensitivity": sensitivity,
            "specificity": specificity,
            "precision": precision,
            "f1": f1,
            "sensitivity_ci_low": sens_low,
            "sensitivity_ci_high": sens_high,
            "specificity_ci_low": spec_low,
            "specificity_ci_high": spec_high,
            "median_confirmation_delay_ms":
                float(np.median(latencies)) if latencies else -1.0,
        }
    return output


def load_ptw_file(path: Path) -> np.ndarray:
    rows: list[list[float]] = []
    with path.open(encoding="latin-1", errors="replace") as handle:
        reader = csv.reader(handle, delimiter="\t")
        next(reader, None)
        for row in reader:
            if len(row) < 7:
                continue
            try:
                values = [float(row[index]) for index in range(7)]
            except ValueError:
                continue
            if all(math.isfinite(value) for value in values):
                rows.append(values)
    return np.asarray(rows, dtype=float)


def external_ptw_features(
    review_dir: Path, config: dict[str, float]
) -> list[dict[str, object]]:
    root = review_dir / "data" / "raw" / "ptw_supplementary"
    fall_root = root / "mmc3" / "Falls scenarios"
    manoeuvre_root = root / "mmc2" / "Extreme manoeuvres"
    event_times = {
        "Fall on a slippery straight road section": 40.132,
        "Fall with leaning of the motorcycle": 34.288,
        "Fall in the roundabout": 35.876,
        "Fall in a curve": 43.486,
    }
    records: list[dict[str, object]] = []
    paths: list[tuple[Path, int, float | None]] = []
    for name, time_s in event_times.items():
        paths.append((next((fall_root / name).glob("*.csv")), 1, time_s))
    for path in sorted(manoeuvre_root.glob("*/*.csv")):
        paths.append((path, 0, None))

    for path, label, event_time in paths:
        raw = load_ptw_file(path)
        time = raw[:, 0]
        channels = raw[:, 1:7]
        filtered = resample_poly(channels, 1, 10, axis=0, window=("kaiser", 5.0))
        filtered_time = np.linspace(time[0], time[-1], len(filtered))
        acceleration_g = np.linalg.norm(filtered[:, :3], axis=1) / 9.80665
        angular_dps = np.linalg.norm(filtered[:, 3:6], axis=1)
        if event_time is not None:
            selection = (filtered_time >= event_time - 1.5) & (
                filtered_time <= event_time + 1.5
            )
        else:
            selection = np.ones(len(filtered_time), dtype=bool)
        records.append(
            {
                "recording": path.stem,
                "label": label,
                "samples_100hz": int(np.sum(selection)),
                "peak_acceleration_g": float(np.max(acceleration_g[selection])),
                "minimum_acceleration_g": float(np.min(acceleration_g[selection])),
                "peak_angular_rate_dps": float(np.max(angular_dps[selection])),
                "passes_review1_acceleration_4g": int(
                    np.any(acceleration_g[selection] >= 4.0)
                ),
                "passes_v2_acceleration": int(
                    np.any(
                        (acceleration_g[selection] >= config["highImpactG"])
                        | (acceleration_g[selection] <= config["lowImpactG"])
                    )
                ),
                "passes_review1_rotation_200dps": int(
                    np.any(angular_dps[selection] >= 200.0)
                ),
                "passes_v2_rotation": int(
                    np.any(angular_dps[selection] >= config["rotationDps"])
                ),
            }
        )

    output = review_dir / "results" / "external_ptw_features.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(records[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(records)
    return records


def plot_performance(
    metrics: dict[str, dict[str, float | int]], figures: Path
) -> None:
    names = list(metrics)
    x = np.arange(len(names))
    sensitivity = np.array([float(metrics[name]["sensitivity"]) for name in names])
    specificity = np.array([float(metrics[name]["specificity"]) for name in names])
    sens_error = np.array(
        [
            [
                sensitivity[i] - float(metrics[name]["sensitivity_ci_low"])
                for i, name in enumerate(names)
            ],
            [
                float(metrics[name]["sensitivity_ci_high"]) - sensitivity[i]
                for i, name in enumerate(names)
            ],
        ]
    )
    spec_error = np.array(
        [
            [
                specificity[i] - float(metrics[name]["specificity_ci_low"])
                for i, name in enumerate(names)
            ],
            [
                float(metrics[name]["specificity_ci_high"]) - specificity[i]
                for i, name in enumerate(names)
            ],
        ]
    )
    fig, axis = plt.subplots(figsize=(7.2, 3.7), constrained_layout=True)
    width = 0.34
    axis.bar(
        x - width / 2,
        sensitivity,
        width,
        yerr=sens_error,
        capsize=3,
        label="Sensitivity",
        color="#d1495b",
    )
    axis.bar(
        x + width / 2,
        specificity,
        width,
        yerr=spec_error,
        capsize=3,
        label="Specificity",
        color="#00798c",
    )
    axis.set_ylim(0, 1.08)
    axis.set_ylabel("Event-level proportion")
    axis.set_xticks(x, names)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="lower right")
    fig.savefig(figures / "performance_comparison.pdf")
    plt.close(fig)


def plot_exemplars(
    review_dir: Path, figures: Path, config: dict[str, float]
) -> None:
    path = review_dir / "data" / "generated" / "exemplar_signals.csv"
    data = np.genfromtxt(path, delimiter=",", names=True, dtype=None, encoding="utf-8")
    scenarios = ("pothole", "parked_tipover", "crash_lowside")
    fig, axes = plt.subplots(3, 3, figsize=(8.0, 6.3), sharex=True, constrained_layout=True)
    for column, scenario in enumerate(scenarios):
        rows = data[data["scenario"] == scenario]
        time = rows["time_ms"] / 1000.0
        acceleration = np.sqrt(rows["ax_g"] ** 2 + rows["ay_g"] ** 2 + rows["az_g"] ** 2)
        angular = np.sqrt(
            rows["gx_dps"] ** 2 + rows["gy_dps"] ** 2 + rows["gz_dps"] ** 2
        )
        tilt = np.rad2deg(
            np.arccos(np.clip(rows["az_g"] / np.maximum(acceleration, 1.0e-9), -1, 1))
        )
        axes[0, column].plot(time, acceleration, color="#d1495b", linewidth=0.8)
        axes[0, column].axhline(
            config["highImpactG"], color="black", linestyle="--", linewidth=0.7
        )
        axes[1, column].plot(time, angular, color="#edae49", linewidth=0.8)
        axes[1, column].axhline(
            config["rotationDps"], color="black", linestyle="--", linewidth=0.7
        )
        axes[2, column].plot(time, tilt, color="#00798c", linewidth=0.8)
        axes[2, column].axhline(
            config["tiltDeg"], color="black", linestyle="--", linewidth=0.7
        )
        axes[0, column].set_title(scenario.replace("_", " "))
        axes[2, column].set_xlabel("Time (s)")
    axes[0, 0].set_ylabel(r"$\|a\|$ (g)")
    axes[1, 0].set_ylabel(r"$\|\omega\|$ (degree/s)")
    axes[2, 0].set_ylabel(r"Tilt (degree)")
    for axis in axes.flat:
        axis.grid(alpha=0.2)
        axis.set_xlim(2.8, 8.0)
    fig.savefig(figures / "simulated_profiles.pdf")
    plt.close(fig)


def plot_external(
    records: list[dict[str, object]], figures: Path, config: dict[str, float]
) -> None:
    names = [str(record["recording"]) for record in records]
    labels = np.array([int(record["label"]) for record in records])
    acceleration = np.array([float(record["peak_acceleration_g"]) for record in records])
    angular = np.array([float(record["peak_angular_rate_dps"]) for record in records])
    colors = np.where(labels == 1, "#d1495b", "#00798c")
    x = np.arange(len(names))
    fig, axes = plt.subplots(2, 1, figsize=(8.0, 5.2), sharex=True, constrained_layout=True)
    axes[0].bar(x, acceleration, color=colors)
    axes[0].axhline(config["highImpactG"], color="black", linestyle="--", linewidth=0.8, label="v2 threshold")
    axes[0].axhline(4.0, color="black", linestyle=":", linewidth=0.8, label="Review-1 threshold")
    axes[0].set_ylabel("Peak acceleration (g)")
    axes[0].legend(fontsize=8)
    axes[1].bar(x, angular, color=colors)
    axes[1].axhline(config["rotationDps"], color="black", linestyle="--", linewidth=0.8)
    axes[1].axhline(200.0, color="black", linestyle=":", linewidth=0.8)
    axes[1].set_ylabel("Peak angular rate (degree/s)")
    axes[1].set_xticks(x, [name.replace(" ", "\n") for name in names], rotation=40, ha="right", fontsize=6)
    for axis in axes:
        axis.grid(axis="y", alpha=0.2)
    fig.savefig(figures / "external_ptw_features.pdf")
    plt.close(fig)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_macros(
    review_dir: Path,
    metrics: dict[str, dict[str, float | int]],
    external: list[dict[str, object]],
    config: dict[str, float],
) -> None:
    v2 = metrics["CrashGuard v2"]
    baseline = metrics["Acceleration-only baseline"]
    legacy = metrics["Review-1 ordered logic"]
    positive_external = [record for record in external if int(record["label"]) == 1]
    generated = review_dir / "results" / "generated_macros.tex"
    lines = [
        "% Generated by analysis/evaluate.py. Do not edit by hand.",
        rf"\newcommand{{\SimulationSeed}}{{{SEED}}}",
        rf"\newcommand{{\SimulationEvents}}{{{len(SCENARIOS) * TRIALS_PER_SCENARIO}}}",
        rf"\newcommand{{\SimulationSamples}}{{{len(SCENARIOS) * TRIALS_PER_SCENARIO * int(DURATION_S * SAMPLE_HZ):,}}}",
        rf"\newcommand{{\PositiveEvents}}{{{2 * TRIALS_PER_SCENARIO}}}",
        rf"\newcommand{{\NegativeEvents}}{{{7 * TRIALS_PER_SCENARIO}}}",
        rf"\newcommand{{\VTwoSensitivity}}{{{100 * float(v2['sensitivity']):.1f}\%}}",
        rf"\newcommand{{\VTwoSpecificity}}{{{100 * float(v2['specificity']):.1f}\%}}",
        rf"\newcommand{{\VTwoFOne}}{{{float(v2['f1']):.3f}}}",
        rf"\newcommand{{\VTwoTP}}{{{int(v2['tp'])}}}",
        rf"\newcommand{{\VTwoTN}}{{{int(v2['tn'])}}}",
        rf"\newcommand{{\VTwoFP}}{{{int(v2['fp'])}}}",
        rf"\newcommand{{\VTwoFN}}{{{int(v2['fn'])}}}",
        rf"\newcommand{{\VTwoSensitivityLow}}{{{100 * float(v2['sensitivity_ci_low']):.1f}\%}}",
        rf"\newcommand{{\VTwoSensitivityHigh}}{{{100 * float(v2['sensitivity_ci_high']):.1f}\%}}",
        rf"\newcommand{{\VTwoSpecificityLow}}{{{100 * float(v2['specificity_ci_low']):.1f}\%}}",
        rf"\newcommand{{\VTwoConfirmationDelayMs}}{{{float(v2['median_confirmation_delay_ms']):.0f}}}",
        rf"\newcommand{{\VTwoImpactThreshold}}{{{config['highImpactG']:.2f}}}",
        rf"\newcommand{{\VTwoLowImpactThreshold}}{{{config['lowImpactG']:.2f}}}",
        rf"\newcommand{{\VTwoRotationThreshold}}{{{config['rotationDps']:.0f}}}",
        rf"\newcommand{{\VTwoTiltThreshold}}{{{config['tiltDeg']:.0f}}}",
        rf"\newcommand{{\VTwoRestHoldMs}}{{{config['restHoldMs']:.0f}}}",
        rf"\newcommand{{\VTwoCorrelationMs}}{{{config['correlationMs']:.0f}}}",
        rf"\newcommand{{\VTwoRideQualificationMs}}{{{config['rideQualificationMs']:.0f}}}",
        rf"\newcommand{{\VTwoRideMemoryMs}}{{{config['rideMemoryMs']:.0f}}}",
        rf"\newcommand{{\BaselineSensitivity}}{{{100 * float(baseline['sensitivity']):.1f}\%}}",
        rf"\newcommand{{\BaselineSpecificity}}{{{100 * float(baseline['specificity']):.1f}\%}}",
        rf"\newcommand{{\BaselineFOne}}{{{float(baseline['f1']):.3f}}}",
        rf"\newcommand{{\LegacySensitivity}}{{{100 * float(legacy['sensitivity']):.1f}\%}}",
        rf"\newcommand{{\LegacySpecificity}}{{{100 * float(legacy['specificity']):.1f}\%}}",
        rf"\newcommand{{\LegacyFOne}}{{{float(legacy['f1']):.3f}}}",
        rf"\newcommand{{\LegacyConfirmationDelayMs}}{{{float(legacy['median_confirmation_delay_ms']):.0f}}}",
        rf"\newcommand{{\ExternalFallCount}}{{{len(positive_external)}}}",
        rf"\newcommand{{\ExternalManoeuvreCount}}{{{len(external) - len(positive_external)}}}",
        rf"\newcommand{{\ExternalFourGPass}}{{{sum(int(record['passes_review1_acceleration_4g']) for record in positive_external)}}}",
        rf"\newcommand{{\ExternalTwoHundredPass}}{{{sum(int(record['passes_review1_rotation_200dps']) for record in positive_external)}}}",
        rf"\newcommand{{\ExternalVTwoImpactPass}}{{{sum(int(record['passes_v2_acceleration']) for record in positive_external)}}}",
        rf"\newcommand{{\ExternalVTwoRotationPass}}{{{sum(int(record['passes_v2_rotation']) for record in positive_external)}}}",
    ]
    generated.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    review_dir = Path(__file__).resolve().parents[1]
    (review_dir / "results").mkdir(exist_ok=True)
    figures = review_dir / "figures"
    figures.mkdir(exist_ok=True)

    config = detector_config(review_dir)
    rows = replay_detector(review_dir)
    metrics = metric_summary(rows)
    external = external_ptw_features(review_dir, config)
    plot_performance(metrics, figures)
    plot_exemplars(review_dir, figures, config)
    plot_external(external, figures, config)
    write_macros(review_dir, metrics, external, config)

    dataset = review_dir / "data" / "generated" / "simulated_imu.csv.gz"
    summary = {
        "simulation": {
            "seed": SEED,
            "sample_hz": SAMPLE_HZ,
            "duration_s": DURATION_S,
            "trials_per_scenario": TRIALS_PER_SCENARIO,
            "scenarios": list(SCENARIOS),
            "dataset_sha256": sha256(dataset),
        },
        "detector_config": config,
        "metrics": metrics,
        "external_ptw_recordings": external,
    }
    with (review_dir / "results" / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
