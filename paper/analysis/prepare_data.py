#!/usr/bin/env python3
"""Verify and extract the bundled public PTW supplementary archive."""
from pathlib import Path
import hashlib, zipfile
r=Path(__file__).resolve().parents[1]
archive=r/'data/raw/PMC6660605_SupplementaryFiles.zip'
expected='76d9e3171ead05147bbd38de194e8d34ba800614c98d38836a8bfca9ab329497'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected, 'PTW archive checksum mismatch'
destination=r/'data/raw/ptw_supplementary'
def extract(source,target):
 target.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(source) as z:
  for name in z.namelist():
   assert (target/name).resolve().is_relative_to(target.resolve()), 'Unsafe archive path'
  z.extractall(target)
extract(archive,destination)
for name in ['mmc2','mmc3']: extract(destination/(name+'.zip'),destination/name)
print('Bundled public PTW archive verified and extracted.')
