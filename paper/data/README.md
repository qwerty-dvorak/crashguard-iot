# Data sources and reproduction

The public powered-two-wheeler data accompany Boubezoul et al. (2019), *Dataset on Powered Two Wheelers Fall and Critical Events Detection*, Data in Brief 23, 103828, DOI https://doi.org/10.1016/j.dib.2019.103828.

- Original supplementary-file endpoint: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6660605/supplementaryFiles
- Bundled archive: `raw/PMC6660605_SupplementaryFiles.zip`
- SHA-256: `76d9e3171ead05147bbd38de194e8d34ba800614c98d38836a8bfca9ab329497`
- `python3 analysis/prepare_data.py` verifies the archive and extracts its original `mmc2` critical-manoeuvre and `mmc3` fall recordings.

The third-party archive retains its source authorship and publication terms. Generated motion data are separate project simulation outputs: `generated/simulated_imu.csv.gz` contains 675 events (seed 20260828), and `../results/fresh_imu.csv` contains 270 events (seed 20260911). The complete pipeline regenerates both datasets. `../results/manifest.sha256` records experiment-source and result checksums.
