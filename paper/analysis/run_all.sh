#!/bin/sh
set -eu

analysis_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
review_dir=$(dirname "$analysis_dir")

mkdir -p "$analysis_dir/build" "$review_dir/results" "$review_dir/figures"
c++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror \
  "$analysis_dir/detector_replay.cpp" \
  -o "$analysis_dir/build/detector_replay"
c++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror \
  "$analysis_dir/test_detector.cpp" \
  -o "$analysis_dir/build/test_detector"
"$analysis_dir/build/test_detector"
python3 "$analysis_dir/generate_simulated_dataset.py"
python3 "$analysis_dir/evaluate.py"
