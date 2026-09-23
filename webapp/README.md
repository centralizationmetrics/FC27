# FC27 decentralization certificate calculator

A static calculator accompanying *How Informative Are Distribution-Based
Decentralization Metrics? Certificates under Capping and Attribution Uncertainty*.
Every calculation runs in the browser. Nothing is uploaded.

## Run

From the artifact or repository root:

```sh
python3 -m http.server 8000 --directory webapp
```

Open `http://localhost:8000/`. No build step or external JavaScript library is
required. A local HTTP server is needed to load bundled datasets.

## Models and displayed intervals

Both attribution budgets count **resource moved**, as a fraction of the same
full resource total used to normalize the observed holdings.

- **Merge(ρ):** combine whole labels into groups. Retain a largest holding in
  each group and move the others to it. The total cost is
  `sum(group total − largest member) ≤ ρ`.
- **Shift(ρ):** move at most ρ of the resource between provisional controllers;
  partial holdings and additional controllers are allowed.

For example, combining 70% and 20% holdings costs 20%, and produces a 90%
holding. Three pairs of labels each holding 1/6 cost 1/2 in total.

All attribution rows and plots include omitted holdings whenever `T_N > 0`.
Observed contributions are not treated as a complete controller distribution.
Each omitted holding is at most the smallest observed holding; its count is
unrestricted except for the separate count-aware Gini calculation.

| Metric | What is implemented |
|---|---|
| CR and NC | Sharp capping and joint Shift intervals. Joint Merge intervals are sharp when the budget is at most the omitted mass, and conservative otherwise. |
| HHI and S_p, p > 1 | Sharp capping and joint Shift intervals. Merge retains the capping lower endpoint; its upper bound is sharp when the budget is at most the omitted mass, and conservative otherwise. |
| Hill_q, q > 1 | Intervals obtained by the decreasing transformation S_q^(1/(1−q)). |
| Gini | Sharp capping interval given a feasible total positive-label count. No attribution interval is computed. |
| Entropy | Sharp capping lower endpoint; unbounded upper endpoint with positive omitted mass. No attribution interval is computed. |

An **exact** badge means the observation fixes a value; **interval** means sharp
endpoints (possibly limiting values); **conservative** means a valid outer bound that
can be wider than the attainable range. In particular, the shared Merge/Shift
upper bound need not be attained by a whole-label merge. “Not computed” states
a limitation of this calculator, not an impossibility theorem.

The former `S_p(x) + ρ^p` Merge formula is not valid for this moved-mass model
and is not used. The paper's current composition and complete-observation
results give the formulas implemented in `metrics.js`.

## Inputs and normalization

Bundled Bitcoin vectors divide balance records by the dated 19,925,284 BTC
supply convention. The top-1M vector reproduces the paper's observed input;
the top-10k subset loads faster. The external 55-million-label count is only a
Gini scenario. Records need not identify distinct addresses or controllers;
see `../data/readme_top_mill_addresses.md` for source limitations.

The bundled Ethereum actual-balance vector is a historical **app-only demo**.
It is not the paper's effective-balance/withdrawal-address calculation. The
latter is reproduced by the Python scripts in the artifact.

Uploads accept JSON arrays or objects with `shares` / `shares_descending`, and
CSV, TSV, or text with one balance per line. For delimited rows, the rightmost
numeric field is used. Headers and nonpositive/nonfinite values are omitted.
Power and Hill orders are restricted to finite values up to 6 (p ≥ 1, q ≥ 0).
Values are sorted and normalized by their sum, giving a complete distribution
of labels by default; this does not identify their controllers.

`N` selects a visible prefix. Leave omitted mass blank to keep the dataset
normalization. If an omitted-mass override is supplied, the visible vector is
rescaled to sum to `1 − T_N`. Changing `N` restores the automatic denominator.
This avoids combining normalized-to-one shares with extra missing mass.
The total-positive-count input affects only Gini; incompatible counts produce
an explicit message instead of an invalid interval.

The three plot cards illustrate capping, joint attribution, and power order.
They are interactive illustrations, not numbered reproductions of every paper
figure. The Python artifact generates the four publication figures.

## Files and checks

- `metrics.js`: dependency-free browser/Node endpoint implementation.
- `app.js`, `index.html`, `style.css`: controls, tiles, and canvas plots.
- `data/`: bundled browser datasets.
- `prepare_data.py`: refresh Bitcoin datasets; refresh the historical Ethereum
  demo only when its separate legacy source CSV is available.

```sh
node webapp/test_metrics.js
node webapp/test_ui.js
python3 webapp/test_python_parity.py
```

The first check includes exhaustive whole-label partitions; the second checks
UI rendering and normalization using a small DOM/canvas harness. The third
requires NumPy and compares JavaScript endpoints against the Python figure
implementation. These are numerical and rendering-logic checks, not a visual
browser test. `metrics.js` exports both `window.Metrics` and a Node module.
The internal `highDrain` / `smallDrain` names implement the paper's LevelCap /
TailTrim residuals.

The internal status key and CSS class `safe` are retained for compatibility; the displayed term is **conservative**.
