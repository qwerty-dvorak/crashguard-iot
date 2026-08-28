# Reproducible analysis

The experiment uses a deterministic generator and the exact C++ detector
included by `sketch.ino`. It does not replace physical crash validation.

Install the native prerequisites on Void Linux if they are absent:

```sh
sudo xbps-install -S base-devel python3 python3-pip
```

Create an isolated Python environment and run the complete pipeline:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r analysis/requirements.txt
./analysis/run_all.sh
```

Run these commands from the cloned repository root. The script generates the
compressed sample-level dataset, event predictions, metrics, plots, JSON
summary, and LaTeX result macros. The random seed is fixed at 20260828.
