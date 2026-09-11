# CrashGuard: motorcycle crash detection and IoT alerts

The complete, self-contained research artifact is in [paper/](paper/).

- [Read the research paper](paper/report.pdf)
- [LaTeX manuscript](paper/report.tex) and [references](paper/references.bib)
- [ESP32 firmware and circuit](paper/wokwi/)
- [Simulation and evaluation scripts](paper/analysis/)
- [Experimental results and logs](paper/results/)
- [Dataset provenance and source attribution](paper/data/README.md)

## Reproduce the paper

```sh
git clone https://github.com/qwerty-dvorak/crashguard-iot.git
cd crashguard-iot/paper
python3 -m pip install -r analysis/requirements.txt
sh reproduce.sh
```

A C++17 compiler and LaTeX installation with latexmk are required. The `paper/` directory contains all project inputs needed by the build; its pipeline verifies and extracts the bundled public PTW supplement, generates both simulated motion datasets, runs the firmware scenarios, and compiles the PDF. See [paper/README.md](paper/README.md) for details.

The paper evaluates 945 simulated events, 14 firmware scenarios, 39 DC interface combinations, nine battery-discharge cases, and public motorcycle signal gates. The source code and experimental records distinguish detector performance, local warning behaviour, and the simulated event-service boundary.
