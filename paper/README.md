# CrashGuard: self-contained research artifact

Repository: https://github.com/qwerty-dvorak/crashguard-iot/tree/main/paper

- [Research paper (PDF)](report.pdf)
- [LaTeX manuscript](report.tex) and [bibliography](references.bib)
- [Firmware and circuit](wokwi/)
- [Analysis and simulation scripts](analysis/)
- [Results, logs, and data partitions](results/)
- [Data source and attribution](data/README.md)

This directory includes every project source, figure, and data input needed to reproduce the paper. Its build and experiments use only paths within this directory. The bundled public PTW supplement is verified before extraction; generated motion data are separate from those recordings.

## Reproduce

Install a C++17 compiler, Python 3 with the dependencies below, and TeX Live with latexmk, IEEEtran bibliography style, circuitikz, and the packages in `report.tex`.

```sh
git clone https://github.com/qwerty-dvorak/crashguard-iot.git
cd crashguard-iot/paper
python3 -m pip install -r analysis/requirements.txt
sh reproduce.sh
```

To rebuild only the manuscript:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex
```

## Experiments

945 simulated events (945,000 samples), 14 exact-firmware scenarios, 39 DC interface operating points, nine time-stepped discharge cases, and gate-level analysis of four public PTW falls and seven critical manoeuvres. The local service double captures firmware event submission without external credentials. Fault-characterization assertions reproduce the documented continuity and recovery deficiencies.

The paper uses justified journal-style prose, twelve paper-specific introduction paragraphs, recent references including 2026 studies, explicit vector notation, and an explanatory paragraph for every table, figure, and displayed equation.
