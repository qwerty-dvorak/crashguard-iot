# CrashGuard Review 3 report

This directory contains the Assessment 6 report on IoT integration, testing,
performance evaluation, dashboard design, and fault handling.

Build from the repository root on Void Linux:

```sh
sudo xbps-install -S python3 python3-matplotlib texlive texlive-most \
  texlive-latexmk poppler-utils
./analysis/run_all.sh
sha256sum -c data/manifest.sha256
python3 review3/make_dashboard.py
latexmk -pdf -cd review3/report.tex
```

The report imports deterministic metrics and figures from the repository root,
so run the analysis pipeline before compiling if those artifacts are absent.
No physical-hardware, current Blynk phone-delivery, network-latency, or measured
battery-runtime result is claimed.
