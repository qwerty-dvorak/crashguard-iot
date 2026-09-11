# Reproducible experiment pipeline

Run `sh reproduce.sh` from the artifact root. The scripts compile and run the shared detector, generate the primary and fresh-seed datasets, process the bundled public PTW archive, execute the actual firmware against local peripheral doubles, and render every report figure. Native executables are generated under `analysis/build/` or as ignored harness binaries. `provenance.py` records source identity and file hashes relative to this directory.
