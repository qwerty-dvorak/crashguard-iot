# CrashGuard Review 2

[![ESP32 build and Wokwi simulation](https://github.com/qwerty-dvorak/crashguard-iot/actions/workflows/wokwi.yml/badge.svg)](https://github.com/qwerty-dvorak/crashguard-iot/actions/workflows/wokwi.yml)

Public repository: <https://github.com/qwerty-dvorak/crashguard-iot>

This repository contains the research report, production ESP32 firmware,
Wokwi circuit and automation scenarios, dataset acquisition and generation
scripts, and the exact-code replay analysis.

The main deliverables are:

- [report.pdf](report.pdf): compiled 20-page research report
- [report.tex](report.tex) and [references.bib](references.bib): editable LaTeX sources
- [wokwi/sketch.ino](wokwi/sketch.ino): ESP32 firmware for the physical circuit
- [wokwi/diagram.json](wokwi/diagram.json): Wokwi circuit file, using Wokwi's required spelling
- [Wokwi scenarios](wokwi): crash, pothole rejection, and cancel tests
- [Wokwi CI workflow](.github/workflows/wokwi.yml): pinned ESP32 build and cloud hardware simulation
- [Wokwi validation record](results/wokwi_validation.json): tool versions, firmware hashes, observations, and limitations
- [analysis/run_all.sh](analysis/run_all.sh): repeatable data and evaluation pipeline
- [results/summary.json](results/summary.json): machine-readable metrics and detector parameters
- [data/manifest.sha256](data/manifest.sha256): hashes for downloaded archives and generated data

No physical-hardware, road-crash, battery-runtime, or network-delivery result
is claimed. The event metrics come from deterministic dataset replay. The
three Wokwi tests are virtual-hardware acceptance results. See the research
integrity statement and limitations in the report before citing any number.

## Reproduce the experiments

```sh
gh repo clone qwerty-dvorak/crashguard-iot
cd crashguard-iot

sudo xbps-install -S base-devel python3 python3-pip arduino-cli curl unzip \
  texlive texlive-most texlive-latexmk

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r analysis/requirements.txt
sh data/download_datasets.sh
./analysis/run_all.sh
sha256sum -c data/manifest.sha256
latexmk -pdf report.tex
```

See the [Wokwi instructions](wokwi/README.md) for firmware and simulator commands.
