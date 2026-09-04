#!/usr/bin/env python3
"""Render the Review 3 replay dashboard from the deterministic signal set."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "data" / "generated" / "exemplar_signals.csv"
OUTPUT = ROOT / "figures" / "replay_dashboard.pdf"

data = np.genfromtxt(SOURCE, delimiter=",", names=True, dtype=None, encoding="utf-8")
rows = data[data["scenario"] == "crash_lowside"]
time_s = rows["time_ms"] / 1000.0
acceleration = np.sqrt(rows["ax_g"] ** 2 + rows["ay_g"] ** 2 + rows["az_g"] ** 2)
rotation = np.sqrt(rows["gx_dps"] ** 2 + rows["gy_dps"] ** 2 + rows["gz_dps"] ** 2)
tilt = np.degrees(
    np.arccos(np.clip(rows["az_g"] / np.maximum(acceleration, 1.0e-9), -1.0, 1.0))
)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
fig = plt.figure(figsize=(9.2, 5.2), facecolor="#edf2f7")
grid = fig.add_gridspec(3, 4, height_ratios=[0.75, 1.4, 1.4], hspace=0.48, wspace=0.55)

cards = [
    ("Acceleration", f"{acceleration.max():.2f} g", "#d1495b"),
    ("Angular rate", f"{rotation.max():.0f} deg/s", "#ed8b00"),
    ("Final tilt", f"{tilt[-1]:.1f} deg", "#00798c"),
    ("Detector", "CRASH", "#7b2cbf"),
]
for index, (label, value, color) in enumerate(cards):
    axis = fig.add_subplot(grid[0, index])
    axis.set_facecolor("white")
    for spine in axis.spines.values():
        spine.set_color("#cbd5e1")
    axis.set_xticks([])
    axis.set_yticks([])
    axis.text(0.07, 0.72, label, transform=axis.transAxes, fontsize=9, color="#475569")
    axis.text(0.07, 0.20, value, transform=axis.transAxes, fontsize=15,
              fontweight="bold", color=color)

ax_acc = fig.add_subplot(grid[1, :2])
ax_rot = fig.add_subplot(grid[1, 2:])
ax_tilt = fig.add_subplot(grid[2, :3])
ax_alert = fig.add_subplot(grid[2, 3])
for axis in (ax_acc, ax_rot, ax_tilt, ax_alert):
    axis.set_facecolor("white")
    for spine in axis.spines.values():
        spine.set_color("#cbd5e1")

ax_acc.plot(time_s, acceleration, color="#d1495b", lw=1.2)
ax_acc.axhline(2.0, color="#334155", ls="--", lw=0.8)
ax_acc.set(title="Acceleration history", ylabel="g", xlim=(2.5, 8.5))
ax_rot.plot(time_s, rotation, color="#ed8b00", lw=1.2)
ax_rot.axhline(90.0, color="#334155", ls="--", lw=0.8)
ax_rot.set(title="Angular-rate history", ylabel="deg/s", xlim=(2.5, 8.5))
ax_tilt.plot(time_s, tilt, color="#00798c", lw=1.2)
ax_tilt.axhline(55.0, color="#334155", ls="--", lw=0.8)
ax_tilt.set(title="Tilt history", ylabel="degree", xlabel="Replay time (s)", xlim=(2.5, 8.5))
for axis in (ax_acc, ax_rot, ax_tilt):
    axis.grid(alpha=0.18)
    axis.tick_params(labelsize=8)
    axis.title.set_fontsize(10)

ax_alert.set_xticks([])
ax_alert.set_yticks([])
ax_alert.text(0.08, 0.82, "Alert timeline", transform=ax_alert.transAxes,
              fontsize=10, fontweight="bold", color="#334155")
ax_alert.text(0.08, 0.58, "Crash confirmed", transform=ax_alert.transAxes,
              fontsize=9, color="#b91c1c")
ax_alert.text(0.08, 0.39, "Local alarm: ON", transform=ax_alert.transAxes,
              fontsize=8.5, color="#334155")
ax_alert.text(0.08, 0.22, "Cancel: 15 s", transform=ax_alert.transAxes,
              fontsize=8.5, color="#334155")
ax_alert.text(0.08, 0.07, "Cloud: not tested", transform=ax_alert.transAxes,
              fontsize=8.5, color="#64748b")

fig.suptitle("CrashGuard replay dashboard - deterministic low-side exemplar",
             x=0.06, ha="left", fontsize=14, fontweight="bold", color="#0f172a")
fig.savefig(OUTPUT, bbox_inches="tight")
plt.close(fig)
print(OUTPUT)
