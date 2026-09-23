# Input manifest and exact certificate reproduction

Source: Motepalli and Jacobsen, *Decentralization in PoS Blockchain Consensus: Quantification and Advancement*, Table III, 2025. [Paper](https://arxiv.org/pdf/2504.14351). Both selected validator snapshots are dated 25 October 2024.

Public author repository: https://github.com/sm86/destake

Pinned commit: `713a10ab25e7e0c1e2b745696151237be2a86256`.

Inputs are unchanged bytes downloaded on 2026-09-05:

| Local filename | Path within source repository | SHA-256 |
|---|---|---|
| 25102024_aptos.csv | data/tnsm/25102024_aptos.csv | b6884e2bfd934c58675ddbd265a400801d718fdc4dd747d99d04c4a447b24b4c |
| 25102024_polygon.csv | data/tnsm/25102024_polygon.csv | 5d07515da892bd8afdedb0ae8065c9d316313650f2da1958fed7b3e7bcb02865 |
| empiricial-analysis-tnsm.csv | tnsm/results/empiricial-analysis-tnsm.csv | Reproduces the authors' rounded HHI values; not a computational input. |

Normalize each `tokens` column by its sum. Aptos has 191 rows, 11 with zero weights; only its 180 positive weights are used. Polygon has 105 positive rows. Dropping zero weights does not change HHI. The dataset contains validator labels and weights, not an independently verified map to controllers. The denominator is observed active-validator token weight, not circulating coin supply.

From the repository root, run:

```sh
python3 review/fc27_prior_claims_consensus_check.py
```

The standard-library script uses exact rational arithmetic. It recreates `certificate_results.json`, `aptos_shift_015_witness.csv`, and `polygon_shift_015_witness.csv`. Witness CSV shares are exact fractions, aligned with the descending positive observed vector. The largest Aptos share gains 3/20, funded proportionally by the other positive shares. The five largest Polygon shares are lowered to a common level, and the other 100 each gain 3/2000. The script verifies exact mass conservation, unchanged positive supports, total variation 3/20, and an HHI order reversal under Shift. Merge uses the same moved-mass budget but permits only whole-label merges. Coarsening monotonicity and the sharp Shift upper endpoint give safe Merge bounds that exclude reversal at 3/20; both models preserve ordering at 1/10.

The same output includes observed counts and Merge/Shift intervals for the smallest number of positive validator weights reaching exactly one-third or two-thirds of the supplied stake. At a 15% budget, the sharp Shift count intervals are Aptos [10, 34] versus Polygon [2, 7] at one-third, and Aptos [38, 72] versus Polygon [8, 18] at two-thirds. Thus these two orderings survive even though the HHI ordering can reverse. Counts are recomputed under the manuscript's positive-holding convention; the source paper reports percentages over all validator rows, including zero-weight Aptos rows.

The budgets are sensitivity assumptions. This example does not claim actual attribution errors or a historical reversal of controller concentration. General Shift endpoints permit finite extensions, but the reversal witnesses use no additional labels.

## All ten published validator vectors

The eight additional source CSVs are copied unchanged from the same pinned author-repository commit. Their filenames and SHA-256 hashes are recorded in `review/fc27_prior_claims_ten_systems_check.py`. Run:

```sh
python3 review/fc27_prior_claims_ten_systems_check.py
```

The script uses exact rational arithmetic to recreate `ten_system_certificates.json`. It verifies that HHI values from each vector agree with the authors' three-decimal table values, recomputes the one-third and two-thirds threshold counts on positive weights, and tests all unordered chain pairs at the same moved-stake budget of 3/20. Of 45 strict observed HHI orderings, safe Merge intervals certify 2 and sharp Shift intervals certify none. In this case the script also constructs a reversal for every HHI pair: move 3/20 into the initially lower-HHI vector's largest label, then drain 3/20 from the initially higher-HHI vector using LevelCap and assign half to each of two new controllers. The smallest resulting HHI reversal margin exceeds 0.0015. For the one-third threshold count the observed, Merge-certified, and Shift-certified numbers are 42, 12, and 2; for two-thirds they are 45, 23, and 11. An overlapping interval alone does not establish reversal for the threshold counts.

These are comparisons of the archived files under our explicit conventions, not independently authenticated or necessarily simultaneous chain states. The filename prefixes suggest that Binance and Osmosis use older files than the other eight, whereas the article's Section IV-B names Binance and Celestia as the older snapshots. We cannot resolve the date difference from these CSVs and do not infer an exact state time from a filename alone. Count percentages printed in the source study need not equal our counts divided by the number of positive weights: the source counts all validator rows, including zero-weight rows in some files, and some printed percentages differ from counts computed at exact one-third or two-thirds thresholds.
