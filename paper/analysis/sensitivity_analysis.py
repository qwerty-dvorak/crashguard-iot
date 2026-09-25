#!/usr/bin/env python3
"""Parametric Threshold Sensitivity and Calibration Sweep for CrashGuard.

Evaluates how sensitivity, specificity, and low-side recall respond to
systematic variations in:
1. Rest tilt threshold (Theta): 40 deg to 70 deg
2. Rotation corroboration threshold (Omega): 60 dps to 150 dps
3. Rest hold duration (T_hold): 1000 ms to 3500 ms

Uses fast in-memory replay over the 270 fresh events (and/or primary events).
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from detector_engine import CrashGuardDetector, Sample


def load_events_memory(path: Path):
    is_gz = path.name.endswith(".gz")
    open_fn = gzip.open if is_gz else open
    events = []
    active_id = None
    cur_samples = []
    cur_label = 0
    cur_scenario = ""

    with open_fn(path, "rt", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if not row or len(row) < 10:
                continue
            eid, label, scen, t = row[0], int(row[1]), row[2], int(row[3])
            s = Sample(
                time_ms=t,
                ax_g=float(row[4]),
                ay_g=float(row[5]),
                az_g=float(row[6]),
                gx_dps=float(row[7]),
                gy_dps=float(row[8]),
                gz_dps=float(row[9]),
            )
            if eid != active_id:
                if active_id is not None:
                    events.append((active_id, cur_label, cur_scenario, cur_samples))
                active_id = eid
                cur_label = label
                cur_scenario = scen
                cur_samples = [s]
            else:
                cur_samples.append(s)

        if active_id is not None:
            events.append((active_id, cur_label, cur_scenario, cur_samples))

    return events


def replay_loaded(events, config=None):
    detector = CrashGuardDetector(**(config or {}))
    labels = []
    scenarios = []
    predictions = []

    for eid, label, scen, samples in events:
        labels.append(label)
        scenarios.append(scen)
        detector.reset()
        detector.set_reference_gravity(0.0, 0.0, 1.0)
        detected = 0
        for s in samples:
            _, confirmed = detector.update(s)
            if confirmed:
                detected = 1
                break
        predictions.append(detected)

    return np.array(labels, dtype=int), np.array(scenarios), np.array(predictions, dtype=int)


def evaluate_threshold_sweep(events):
    print("Running in-memory parametric sweeps...")

    # Tilt sweep (40 to 70 deg in steps of 2.5 deg)
    tilt_values = np.linspace(40.0, 70.0, 13)
    tilt_results = []
    for tilt in tilt_values:
        labels, scenarios, preds = replay_loaded(events, {"tilt_deg": float(tilt)})
        tp = int(np.sum((labels == 1) & (preds == 1)))
        tn = int(np.sum((labels == 0) & (preds == 0)))
        fp = int(np.sum((labels == 0) & (preds == 1)))
        fn = int(np.sum((labels == 1) & (preds == 0)))

        low_mask = (scenarios == "crash_lowside")
        low_recall = int(np.sum(preds[low_mask] == 1)) / int(np.sum(low_mask)) if np.any(low_mask) else 0.0

        high_mask = (scenarios == "crash_highside")
        high_recall = int(np.sum(preds[high_mask] == 1)) / int(np.sum(high_mask)) if np.any(high_mask) else 0.0

        sens = tp / (tp + fn) if (tp + fn) else 0.0
        spec = tn / (tn + fp) if (tn + fp) else 0.0
        f1 = (2 * tp) / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0

        tilt_results.append({
            "tilt_deg": float(tilt),
            "sensitivity": sens,
            "specificity": spec,
            "f1": f1,
            "lowside_recall": low_recall,
            "highside_recall": high_recall,
            "fp": fp,
            "fn": fn,
        })

    # Rotation sweep (60 to 150 dps in 10 steps)
    rot_values = np.linspace(60.0, 150.0, 10)
    rot_results = []
    for rot in rot_values:
        labels, scenarios, preds = replay_loaded(events, {"rotation_dps": float(rot)})
        tp = int(np.sum((labels == 1) & (preds == 1)))
        tn = int(np.sum((labels == 0) & (preds == 0)))
        fp = int(np.sum((labels == 0) & (preds == 1)))
        fn = int(np.sum((labels == 1) & (preds == 0)))

        low_mask = (scenarios == "crash_lowside")
        low_recall = int(np.sum(preds[low_mask] == 1)) / int(np.sum(low_mask)) if np.any(low_mask) else 0.0

        rot_results.append({
            "rotation_dps": float(rot),
            "sensitivity": tp / (tp + fn) if (tp + fn) else 0.0,
            "specificity": tn / (tn + fp) if (tn + fp) else 0.0,
            "lowside_recall": low_recall,
            "fp": fp,
        })

    # Rest hold duration sweep (1000 to 3500 ms in 6 steps)
    hold_values = [1000, 1500, 2000, 2500, 3000, 3500]
    hold_results = []
    for hold in hold_values:
        labels, scenarios, preds = replay_loaded(events, {"rest_hold_ms": hold})
        tp = int(np.sum((labels == 1) & (preds == 1)))
        tn = int(np.sum((labels == 0) & (preds == 0)))
        fp = int(np.sum((labels == 0) & (preds == 1)))
        fn = int(np.sum((labels == 1) & (preds == 0)))

        low_mask = (scenarios == "crash_lowside")
        low_recall = int(np.sum(preds[low_mask] == 1)) / int(np.sum(low_mask)) if np.any(low_mask) else 0.0

        hold_results.append({
            "rest_hold_ms": hold,
            "sensitivity": tp / (tp + fn) if (tp + fn) else 0.0,
            "specificity": tn / (tn + fp) if (tn + fp) else 0.0,
            "lowside_recall": low_recall,
            "fp": fp,
        })

    return {
        "tilt_sweep": tilt_results,
        "rotation_sweep": rot_results,
        "hold_sweep": hold_results,
    }


def plot_sensitivity(sweep_data: dict, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.4), constrained_layout=True)

    # Panel 1: Rest Tilt Gate
    tilt_data = sweep_data["tilt_sweep"]
    tilts = [d["tilt_deg"] for d in tilt_data]
    sens = [d["sensitivity"] * 100 for d in tilt_data]
    spec = [d["specificity"] * 100 for d in tilt_data]
    lowside = [d["lowside_recall"] * 100 for d in tilt_data]

    axes[0].plot(tilts, sens, "o-", color="#d1495b", label="Overall Sensitivity", lw=1.5)
    axes[0].plot(tilts, lowside, "s--", color="#edae49", label="Low-Side Recall", lw=1.5)
    axes[0].plot(tilts, spec, "^-", color="#00798c", label="Specificity", lw=1.5)
    axes[0].axvline(55.0, color="black", linestyle=":", lw=1.2, label="Selected Gate (55°)")
    axes[0].set_xlabel(r"Rest Tilt Threshold $\Theta_{\mathrm{tilt}}$ (deg)")
    axes[0].set_ylabel("Proportion (%)")
    axes[0].set_title("(a) Rest Tilt Gate Sensitivity")
    axes[0].set_ylim(-2, 105)
    axes[0].grid(alpha=0.25)
    axes[0].legend(fontsize=7, loc="lower left")

    # Panel 2: Rotation Corroboration Gate
    rot_data = sweep_data["rotation_sweep"]
    rots = [d["rotation_dps"] for d in rot_data]
    r_sens = [d["sensitivity"] * 100 for d in rot_data]
    r_low = [d["lowside_recall"] * 100 for d in rot_data]
    r_spec = [d["specificity"] * 100 for d in rot_data]

    axes[1].plot(rots, r_sens, "o-", color="#d1495b", label="Overall Sensitivity", lw=1.5)
    axes[1].plot(rots, r_low, "s--", color="#edae49", label="Low-Side Recall", lw=1.5)
    axes[1].plot(rots, r_spec, "^-", color="#00798c", label="Specificity", lw=1.5)
    axes[1].axvline(90.0, color="black", linestyle=":", lw=1.2, label="Selected Gate (90°/s)")
    axes[1].set_xlabel(r"Rotation Threshold $\Omega_{\mathrm{rot}}$ (deg/s)")
    axes[1].set_title("(b) Rotational Corroboration Gate")
    axes[1].set_ylim(-2, 105)
    axes[1].grid(alpha=0.25)
    axes[1].legend(fontsize=7, loc="lower left")

    # Panel 3: Rest Hold Duration
    hold_data = sweep_data["hold_sweep"]
    holds = [d["rest_hold_ms"] / 1000.0 for d in hold_data]
    h_sens = [d["sensitivity"] * 100 for d in hold_data]
    h_low = [d["lowside_recall"] * 100 for d in hold_data]
    h_spec = [d["specificity"] * 100 for d in hold_data]

    axes[2].plot(holds, h_sens, "o-", color="#d1495b", label="Overall Sensitivity", lw=1.5)
    axes[2].plot(holds, h_low, "s--", color="#edae49", label="Low-Side Recall", lw=1.5)
    axes[2].plot(holds, h_spec, "^-", color="#00798c", label="Specificity", lw=1.5)
    axes[2].axvline(2.0, color="black", linestyle=":", lw=1.2, label="Selected Hold (2.0 s)")
    axes[2].set_xlabel(r"Rest Hold Duration $T_{\mathrm{hold}}$ (s)")
    axes[2].set_title("(c) Rest Hold Temporal Filter")
    axes[2].set_ylim(-2, 105)
    axes[2].grid(alpha=0.25)
    axes[2].legend(fontsize=7, loc="lower left")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved sensitivity figure to {output_path}")


def main():
    root = Path(__file__).resolve().parents[1]
    dataset = root / "data" / "generated" / "simulated_imu.csv.gz"
    out_json = root / "results" / "sensitivity_analysis.json"
    out_fig = root / "figures" / "threshold_sensitivity.pdf"

    print(f"Loading {dataset}...")
    events = load_events_memory(dataset)
    print(f"Loaded {len(events)} events into memory.")

    data = evaluate_threshold_sweep(events)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved sweep metrics to {out_json}")

    plot_sensitivity(data, out_fig)


if __name__ == "__main__":
    main()
