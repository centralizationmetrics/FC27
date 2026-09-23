# FC27 data and figure reproduction

These instructions reproduce the reported metrics and observable validator
grouping from the supplied inputs. They do not authenticate the inputs against
a blockchain state or validate a mapping from labels to controllers.

Run commands from the repository root. The checked environment used Python
3.13.3, NumPy 2.4.4, and Matplotlib 3.10.9. The two direct plotting dependencies
are pinned in `analysis-code/requirements-fc27.txt`; pip installs their
dependencies. The basic certificate tests and validator-projection verifier use
only the Python standard library; the joint figure-calculation tests use NumPy.

## Attribution budget used by this version

The paper and figure labels use `rho` (ρ) for both attribution models. Existing
code arguments and metadata fields named `alpha` retain their historical names
and represent the same Shift moved-mass budget; no numerical convention changes.

Both models bound the fraction of the full resource total that is reassigned.
Merge transfers only whole labels: for each group, keep a largest holding and
move the others to it. Its total cost is
`sum(group total − largest member)`. Shift permits partial transfers and
additional controllers, with the same moved-mass unit.

The reported power-sum Merge lower endpoint is sharp. With an unknown omitted
count, its upper endpoint also equals Shift's when `rho <= omitted mass`:
choose omitted holdings totaling the budget and merge them into the largest
observed holding. Beyond that range the Shift upper endpoint is **conservative** for
Merge. The old `S_p(x) + rho^p` affected-mass formula is not used.
Complete-observation Merge endpoints can instead be computed exactly by
selecting whole donor labels, as stated in the paper.

The key updated HHI results are:

| Calculation | Merge result | Shift result |
|---|---|---|
| Introductory example, budget .30 | Sharp [.3125, .6800] | Sharp [.1025, .6800] |
| Bitcoin joint uncertainty, budget .30 | Conservative [.000564857452, .098050518418] | Sharp [.000007500645, .098050518418] |
| Aptos, budget .15 | Conservative [.01101758246, .04211789934] | Sharp [.00686489207, .04211789934] |
| Polygon, budget .15 | Conservative [.05074221955, .10393208755] | Sharp [.02936482954, .10393208755] |

Displayed decimals are approximations; the scripts retain the underlying inputs.
The published-summary Bitcoin/Ethereum guarantee uses a .15 Merge budget,
with conservative Bitcoin upper .0374661 below Ethereum lower .0477924375.
The previous .20 guarantee does not follow under this model.
Solving the same conservative inequality gives a sufficient budget below
0.17505315350899764; this is not the exact breakdown of the unobserved lists.

## Clean environment

```sh
python3.13 -m venv .venv-fc27
.venv-fc27/bin/python -m pip install -r analysis-code/requirements-fc27.txt
mkdir -p .fc27-cache/matplotlib
export MPLCONFIGDIR="$PWD/.fc27-cache/matplotlib"
.venv-fc27/bin/python -m unittest discover -s analysis-code -p 'test*.py'
```

The certificate command reports its test count and result. Installing dependencies
requires network access; all data verification and figure commands below run offline.
The existing development environment can instead use `.figvenv/bin/python`.
Rasterization and PDF metadata can differ with platform fonts and library
dependencies, so numerical reproduction is checked separately from image bytes.

## Included inputs and what they establish

| Input | Purpose and scope |
|---|---|
| `data/top_mill_adresses.json` | The one-million-row Bitcoin balance release. The historical filename is retained. Scripts also accept the same JSON Lines bytes compressed as `.json.gz`. |
| `data/bitcoin_top1m_capping_convergence_summary.csv` | Precomputed Bitcoin capping endpoints. Its denominator is the dated 19,925,284 BTC supply convention; the Gini count is the stipulated 55 million positive labels. |
| `data/bitcoin_joint_certificates_summary.csv` | Joint capping/Merge and capping/Shift endpoints for CR, NC, and HHI, using the same dated supply. The omitted 6.864% is included; no omitted count is assumed. |
| `data/eth_active_validator_projection_2026-09-22.csv.gz` | Compact per-validator projection of the pinned-state Ethereum response for active validators, sufficient to reconstruct its effective-balance histogram and withdrawal-address partition. |
| Projection `.metadata.json` and `.sha256` sidecars | Column units, hashes, derivation source, row count, and provenance limitations. |
| `data/eth_active_effective_balance_histogram_2026-09-22.csv` | Active validator-label baseline, in integer gwei. |
| `data/eth_execution_withdrawal_address_groups_2026-09-22.csv` | Observable partition, in integer gwei, including counts by credential prefix. The moved-mass cost is independently reconstructed from the per-validator projection. |
| `data/eth_validators_effective_2026-09-22.header.json` and `.request.json` | Saved finalized header and request record, including the fixed state root, slot, exact URL, download time, and raw-response checksum. |
| `data/eth_merge_shift_calibration_metadata.json` | Grouping rule, conditional interpretation, source hashes, and figure inputs. |

The full Ethereum validator response is **not included** in the submission
artifact. Its local filename is
`data/eth_validators_effective_2026-09-22.json.gz`; its uncompressed JSON has
437,767,229 bytes, and the local gzip has 65,778,750 bytes. The compact
projection is 4,309,244 bytes. It retains 901,915 rows and four fields:

- `index`: integer validator index;
- `status`: Beacon API validator status (here `active_ongoing` or `active_exiting`);
- `effective_balance`: integer gwei, copied from the validator's protocol field;
- `withdrawal_credentials`: the full 32-byte hexadecimal credential.

Rows are sorted by integer validator index. The CSV uses UTF-8 and LF line
endings. Gzip uses compression level 9, a zero modification time, and an empty
filename header. The uncompressed CSV checksum identifies the canonical data
even if another gzip implementation encodes it differently.

| Object | SHA-256 |
|---|---|
| Bitcoin JSON Lines | `d9392e4a598a4471cfef60ac5559aee2abf93036479b49b91986be5ce4904149` |
| Full Ethereum response, uncompressed | `273c82e554242c8305b20de991bfb3839445a80ddc2ea3a9547c3b62c5a0426b` |
| Gzipped Ethereum projection | `7b12437e26865c2a6bc79d94c833008d8ad5f6aa3efd79e6bd7f3bfaa081b146` |
| Uncompressed projection CSV | `fc635b18eebfc2a6d1fd03bf6fe77d062130121c341dda1da296ad577d626554` |
| Effective-balance histogram | `ca82d5fe9141bcaf094029f7868418568df1acd692ab58ad121977e1042940d4` |
| Withdrawal-address groups | `8c1be804e79b9af170df58736d24d7c1f490525f115bf9f89b1b6bcd2eab3442` |

## Verify grouping without the full Ethereum response

```sh
.venv-fc27/bin/python analysis-code/verify_eth_projection.py
.venv-fc27/bin/python analysis-code/verify_eth_conditional.py
```

The verifier checks both compressed and uncompressed projection hashes,
rejects duplicate validator indices, groups `0x01` and `0x02` credentials by
their final 20-byte execution address regardless of prefix, and retains each
`0x00` validator as a singleton. It reconstructs the histogram and partition
in memory, then compares their canonical CSV bytes with the existing files.
It also computes the moved-mass cost by retaining a largest effective balance in each group: 39,414,513 ETH out of 43,367,095 ETH, or 0.908857579692622. It does not rewrite those files. Expected output includes:

```text
validator_count: 901915
group_count: 44163
effective_balance_gwei: 43367095000000000
histogram_and_groups: both match the supplied CSVs byte for byte
```

This confirms the grouping from individual validator records rather than
merely recomputing metrics from already aggregated groups.

The conditional verifier checks the Merge endpoints using integer gwei and
rational arithmetic. Each validator is assigned to one controller. The groups
with recorded withdrawal addresses remain separate; unresolved validators'
whole holdings may join those groups or one another. The 285,126 ETH in these
holdings bounds the additional moved mass from the withdrawal-address partition.
No holding is split. Leaving the unresolved validators separate gives the HHI
minimum 0.05324504817951941; merging them all into the largest group gives the
maximum 0.05610184312026344. The half-stake count range is [61, 65]. All endpoints
are attained. `data/eth_conditional_exact_check.json` records exact fractions.

CSV fields `conditional_merge_*` and `unresolved_00_rho` replace the former
`conditional_shift_*` and `unresolved_00_alpha` fields. Metadata likewise uses
`conditional_merge`. The `stress_shift_*` fields still use the full Shift ball
at budget 0.10. Figure 2 labels the conditional Merge certificate M and uses a
red band with upward diagonal hatching. These checks verify the calculation,
not the controller assumption.

## Reproduce figures using the supplied precomputed capping summary

```sh
.venv-fc27/bin/python analysis-code/verify_eth_projection.py
.venv-fc27/bin/python analysis-code/plot_all_figures.py
```

`plot_all_figures.py` reads the supplied Bitcoin capping CSV for appendix Figure 3,
recomputes joint Bitcoin capping/attribution and family bands from the released balance rows for
Figures 1 and 4, and produces Figure 2 from the Ethereum compact histogram and
partition when the full response is absent. In that compact-input mode it
checks the histogram/group hashes before use. The projection verifier above
provides the independent record-to-group step.

Outputs are PDF and PNG versions of:

- `figure_bitcoin_top1m_capping_convergence`;
- `figure_attribution_two_models`;
- `figure_eth_merge_shift_calibration`;
- `figure_family_parameter_sensitivity`.

The third filename is historical: the FC27 figure shows the observable
withdrawal-address partition and conditional Merge calculation, not the older
synthetic provider-share scenario. Older app/demo datasets are not inputs to
these four figures.

## Recompute Bitcoin summaries before plotting

To include the raw released Bitcoin rows to capping-summary step, run:

```sh
.venv-fc27/bin/python analysis-code/summarize_bitcoin_top1m_capping_convergence.py
.venv-fc27/bin/python analysis-code/summarize_bitcoin_joint_certificates.py
.venv-fc27/bin/python analysis-code/verify_bitcoin_joint_certificates.py
.venv-fc27/bin/python analysis-code/verify_eth_projection.py
.venv-fc27/bin/python analysis-code/plot_all_figures.py
```

The first script parses balances in integer satoshis and requires the exact
released sum, 1,855,762,831,566,030 satoshis. It refreshes the capping CSV. The
second refreshes the joint CR/NC/HHI summary used for checking Figure 1 and the
Bitcoin table. The third independently checks the reported HHI endpoints and
head-metric thresholds at budgets 0, 0.10, and 0.30 using integer satoshis and
rational arithmetic. Plotting does not silently rerun the first script.
The verifier also records feasible whole-label Merge witnesses in
`data/bitcoin_merge_upper_gaps.json`. Their gaps below the conservative upper bound are
about 1.005e-8 at budget 0.10 and 1.082e-6 at budget 0.30.

All Bitcoin paper figures divide by 19,925,284 BTC, giving coverage
0.931360793435130 and omitted mass 0.06863920656487005. Figures 1 and 4 include
every completion under the observed share cap and the stated attribution
bound. All attribution budgets are fractions of this same full supply.
The Gini count of 55 million is a stipulated
calibration input, not recovered from this file. See
`data/readme_top_mill_addresses.md` for the release, source links, and
multi-address-record limitations.

The older `summarize_attribution_hhi_two_models.py` and its CSV describe the
legacy analysis normalized within the covered holdings. They are not inputs
to the current FC27 figures or numerical table.

### Exact Bitcoin inputs

The source is version 1 of the cited Kaggle release. Balances sum to
18,557,628.31566030 BTC when parsed in integer satoshis. Relative to the
19,925,284 BTC denominator, the joint calculation uses:

| Quantity | Value |
|---|---:|
| Omitted resource share | 0.06863920656487005 |
| Largest observed share | 0.012476488638054544 |
| Smallest observed share / cap on each omitted share | 5.017745292865086e-8 |

The displayed shares are decimal approximations; the independent verifier
derives exact fractions from integer satoshis and the stated denominator.
Four source rows contain multiple decoded addresses, and one decoded address
occurs in two rows. The four multi-address rows contain 5.98014231 BTC.
The calculation therefore treats records as labels. The release omits its
SQL, block identifier, UTC cutoff, BigQuery job metadata, and
multi-address-script rule. Further source and representation details are in
`data/readme_top_mill_addresses.md`.

## Optional: reproduce the projection from the original Ethereum response

These commands require the full checksummed raw response, which is not shipped.
They perform no API request. `--raw` also accepts a gzip-compressed raw response
and checks the checksum of its decompressed bytes.

```sh
.venv-fc27/bin/python analysis-code/verify_eth_projection.py \
  --raw data/eth_validators_effective_2026-09-22.json.gz
.venv-fc27/bin/python analysis-code/verify_eth_projection.py \
  --raw data/eth_validators_effective_2026-09-22.json.gz \
  --write-projection data/eth_active_validator_projection_2026-09-22.csv.gz
```

The second command writes only the projection and its two sidecars, after
checking the reconstructed histogram and group CSVs against the supplied
versions. Repeated generation in the checked environment produces identical
compressed projection bytes. It never alters the existing histogram or
partition. If the full response is locally present, the normal figure
generator also rebuilds those two compact inputs using its original extraction
routine; in a submission bundle without that response, it uses the checked
compact inputs instead.

## Reproduce the published validator-vector comparisons

```sh
python3 review/fc27_prior_claims_consensus_check.py
python3 review/fc27_prior_claims_ten_systems_check.py
python3 review/fc27_breakdown_budgets.py
```

This standard-library script checks the Appendix B.6 reanalysis using exact
rational arithmetic. The authors' two validator-weight CSVs, a pinned source
revision, hashes, and generated witness vectors are in
`review/data/motepalli2025/`. Both HHI rankings are preserved at a 10% budget;
at 15%, every permitted Merge preserves the ordering, while two explicit
Shifts reverse it without changing positive supports. These budgets are
sensitivity assumptions, not measured attribution errors. Include this
directory and the script when assembling the paper's reproduction artifact.
The script also verifies the one-third and two-thirds threshold-count
intervals: at the 15% budget, their Aptos--Polygon orderings survive both
models even though the HHI ordering can reverse under Shift.
The second script uses all ten archived vectors to recreate
`review/data/motepalli2025/ten_system_certificates.json`, including exact
certificate endpoints and counts of certified pairwise orderings for HHI and
the one-third and two-thirds threshold counts. It also checks explicit
two-new-controller Shift reversals for all 45 strict HHI pairwise orderings
at the 15% budget.

The breakdown script computes all strict pairwise HHI, one-third-count, and
two-thirds-count comparison budgets. It encloses every boundary in a rational
interval of width at most 2^-40 and records the pairs and summary statistics
in `review/data/motepalli2025/breakdown_budgets.json`. Shift entries locate loss
of the strict observed order (which can include a tie for counts); Merge entries
are lower bounds from conservative certificates. HHI equality at an unattained lower
endpoint is not treated as a reversal witness. Aptos--Polygon breaks down at
approximately 0.120711690249 under Shift; the conservative Merge guarantee reaches
approximately 0.172861314055. The corresponding median Shift budgets over all
strict pairs are 0.043845786963 (HHI), 0.062900388765 (NC_1/3), and
0.075980949125 (NC_2/3).

The selected snapshots are dated 25 October 2024 and are pinned to author
repository commit `713a10ab25e7e0c1e2b745696151237be2a86256`. Normalize the
`tokens` column by its sum in each file. Aptos has 191 rows, including 11
zero weights; Polygon has 105 positive rows. The input manifest in that
directory records filenames and checksums.

## Provenance limits that remain unresolved

The saved finalized header records slot 15,271,392 and state root
`0xb795a983525b03e3b656fcfede4575944e523aaa261546cb930a4287d85505cf`.
On 22 September 2026, the validator request named that root directly and used
`status=active`; the recorded download completed at
2026-09-22T12:53:14.981840Z. The returned records include 897,382
`active_ongoing` and 4,533 `active_exiting` validators, with no
`active_slashed` records. Their total effective balance is 43,367,095 ETH.
The fixed-root request removes ambiguity from a mutable `finalized` URL, but
the public node's response has not been independently authenticated against
consensus. Credential equality has not been validated as controller identity.

The partition has 7,507 nonsingleton groups containing 865,259 validators
and 95.7% of included effective balance. Its 8,918 `0x00` singletons contain
285,126 ETH, giving conditional radius
285,126 / 43,367,095 = 0.006574708312834881. This radius assumes the
address-bearing validators' withdrawal-address partition matches their actual
controller partition. The projection verifies grouping from the returned
records; it cannot establish that attribution assumption.

Protocol activation and maximum-effective-balance rules constrain validators,
not controllers, and do not supply a minimum controller share. The paper's
Ethereum credential references and EIP-7251 document the relevant fields.

Likewise, reproducing the Bitcoin release does not reproduce its original
chain-state extraction: the release omits its query and block identifier, and
the supply denominator comes from an independent dated source.

## Check the mathematical implementation and calculator

```sh
.venv-fc27/bin/python review/fc27_attribution_exact_checks.py
.venv-fc27/bin/python review/fc27_capping_checks.py
node webapp/test_metrics.js
node webapp/test_ui.js
.venv-fc27/bin/python webapp/test_python_parity.py
```

The attribution check enumerates whole-label partitions and tests the exact
Merge subset formula, inclusion in Shift, and conservative bounds with rational
arithmetic. The calculator checks compare its joint endpoints with Python and
exercise normalization and conservative/sharp display logic. They do not replace a
visual browser check. See `webapp/README.md` for running the calculator.

## Rebuild the code artifact

See `README.md` for the code-only build command and `PUBLISHING.md` for GitHub Pages setup.
