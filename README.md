# Decentralization metrics artifact

Code and data accompanying *How Informative Are Distribution-Based Decentralization
Metrics? Certificates under Capping and Attribution Uncertainty*.

This repository contains the calculator, analysis code, data, and reference
plots. The paper PDF, LaTeX source, bibliography, and TeX formatting files are
not included.

To copy this release into a fresh repository and enable its website, see
[PUBLISHING.md](PUBLISHING.md). The calculator is in [webapp/](webapp/).

This release uses **moved-mass Merge**: in each merged group, a largest holding
stays and the others move to it. The global budget is the sum of those moved
holdings. Shift uses the same resource-mass unit and also permits partial
reassignment. With an unknown omitted count, Merge attains the joint Shift upper
bound when the budget does not exceed the omitted mass. Beyond that regime,
the Shift upper bound gives a **conservative** Merge certificate. A certificate
guarantees enclosure under the stated observation and attribution assumptions;
it does not establish that those assumptions hold.

## Reproduce

Python 3.13 was used for the checked environment. From this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r analysis-code/requirements-fc27.txt
.venv/bin/python tools/verify_fc27_artifact.py
.venv/bin/python -m unittest discover -s analysis-code -p 'test*.py'
.venv/bin/python analysis-code/verify_bitcoin_joint_certificates.py
.venv/bin/python analysis-code/verify_eth_projection.py
.venv/bin/python review/fc27_prior_claims_consensus_check.py
.venv/bin/python analysis-code/plot_all_figures.py
```

Dependency installation may require the internet. Data verification, numerical
checks, and figure generation run offline. `FC27_REPRODUCIBILITY.md` explains
the inputs, denominator conventions, optional recomputation steps, and remaining
source limitations.

## Contents

- `analysis-code/`: certificate implementation, tests, verifiers, and current
  figure/summary scripts. Two legacy covered-holdings sensitivity scripts are
  retained because the regression suite exercises their whole-label merging
  constructions; they are not inputs to the current paper figures.
- `data/`: Bitcoin source rows compressed as JSON Lines, compact Ethereum
  validator records, derived CSVs, and provenance metadata. The large original
  Ethereum response is excluded; the compact projection reconstructs the
  effective-balance histogram and withdrawal-address grouping.
- `review/data/motepalli2025/` and its verifiers: all ten published validator
  vectors, source revision and hashes, exact certificates, and Aptos/Polygon
  Shift witnesses.
- Four `figure_*.pdf/.png` pairs: reference figures used by the paper.
- `webapp/`: local browser calculator, input data, and tests.
- `manifest.json`, `checksums.sha256`: the files and SHA-256 checksums of this
  release. Run the integrity check before scripts regenerate outputs.

No mapping from observed labels to actual controllers is established by these
files. Reproducing the included data calculations does not authenticate the
original Bitcoin extraction or independently verify the public node's Ethereum
response against consensus. The Ethereum request names the state root in the
saved finalized header.
The Bitcoin positive-label count is an external Gini input; the Ethereum grouping
uses observable withdrawal credentials under the paper's stated conditions.

## Calculator

```sh
python3 -m http.server 8000 --directory webapp
```

Open `http://localhost:8000/`. Calculations run locally, without uploading data.
`webapp/README.md` explains the formulas and normalization. Node.js is needed
only for the optional calculator checks:

```sh
node webapp/test_metrics.js
node webapp/test_ui.js
.venv/bin/python webapp/test_python_parity.py
```

## Rebuild this bundle

`tools/build_fc27_artifact.py` copies only the explicit release inputs, compresses
Bitcoin source rows deterministically, and writes a checksum manifest and ZIP.
With `--code-only`, it excludes the paper and its TeX build files, old AFT
artifacts, raw Ethereum responses,
development context, caches, and repository history.

```sh
python3 tools/build_fc27_artifact.py --code-only --output /tmp/fc27-rebuilt
```

The same canonical input bytes produce the same ZIP bytes. Regenerating plots
can change PDF metadata or rendering across library/platform versions, so the
numerical checks are separate from file-integrity checks.
