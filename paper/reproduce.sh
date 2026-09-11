#!/bin/sh
set -eu
artifact_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$artifact_dir/results"
python3 "$artifact_dir/analysis/prepare_data.py"
sh "$artifact_dir/analysis/run_all.sh" > "$artifact_dir/results/original-replay.log" 2>&1
python3 "$artifact_dir/analysis/create_harness.py"
python3 "$artifact_dir/analysis/run_experiments.py" > "$artifact_dir/results/experiments.log" 2>&1
python3 "$artifact_dir/analysis/make_figures.py"
python3 "$artifact_dir/analysis/provenance.py"
cd "$artifact_dir"
latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex > results/latex-build.log 2>&1
