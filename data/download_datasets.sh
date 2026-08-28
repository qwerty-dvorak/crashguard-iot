#!/bin/sh
set -eu

data_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
raw_dir="$data_dir/raw"
ptw_dir="$raw_dir/ptw_supplementary"
mkdir -p "$raw_dir" "$ptw_dir"

healthlink="$raw_dir/HealthLINK_Falls_Dataset.zip"
ptw_archive="$raw_dir/PMC6660605_SupplementaryFiles.zip"

if [ ! -f "$healthlink" ]; then
  curl -fL --retry 3 --output "$healthlink" \
    https://osf.io/download/n27yz/
fi

if [ ! -f "$ptw_archive" ]; then
  curl -fL --retry 3 --output "$ptw_archive" \
    https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6660605/supplementaryFiles
fi

printf '%s  %s\n' \
  0938d21a89475cbba2e377496b71862c8147e78e21974972e3ca2e0beef95b18 \
  "$healthlink" \
  76d9e3171ead05147bbd38de194e8d34ba800614c98d38836a8bfca9ab329497 \
  "$ptw_archive" | sha256sum -c -

if [ ! -f "$ptw_dir/mmc2.zip" ]; then
  unzip -q "$ptw_archive" -d "$ptw_dir"
fi
if [ ! -d "$ptw_dir/mmc2" ]; then
  mkdir -p "$ptw_dir/mmc2"
  unzip -q "$ptw_dir/mmc2.zip" -d "$ptw_dir/mmc2"
fi
if [ ! -d "$ptw_dir/mmc3" ]; then
  mkdir -p "$ptw_dir/mmc3"
  unzip -q "$ptw_dir/mmc3.zip" -d "$ptw_dir/mmc3"
fi

printf '%s\n' 'dataset archives verified and PTW supplements available'
