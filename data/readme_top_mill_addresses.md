# Bitcoin top-1,000,000 balance records

## Artifact used by the paper

- File: `data/top_mill_adresses.json` (the historical filename is retained).
- Rows: 1,000,000 JSON Lines records.
- SHA-256: `d9392e4a598a4471cfef60ac5559aee2abf93036479b49b91986be5ce4904149`.
- Exact sum of `balance_btc`, parsed in satoshis: `18,557,628.31566030 BTC`.

The file matches version 1 of RPhilipp's *Bitcoin Address Balances -- Top
1,000,000* Kaggle dataset:

<https://www.kaggle.com/datasets/rphilipp/bitcoin-address-balances-top-1000000/versions/1>

The depositor describes it as a 23 September 2025 snapshot derived from the
community-maintained Google BigQuery `crypto_bitcoin` dataset and releases it
under CC0.

## Representation

The paper treats each row as one observed label and does not perform
label-to-controller attribution. Most `address` fields contain a one-element
array. Four rows contain arrays of two or three decoded addresses, and one
decoded address occurs in two rows. Those four multi-address rows contain
5.98014231 BTC in total. The released documentation does not specify how
multi-address scripts were assigned, so the paper calls these *balance
records*, not one million distinct addresses.

## Denominator and coverage

The capping case study uses `19,925,284 BTC`, the circulating supply reported
in CoinMarketCap's 23 September 2025 historical snapshot:

<https://coinmarketcap.com/historical/20250923/>

This gives coverage `0.9313607934351299585` and omitted mass
`1,367,655.68433970 BTC`. The supply value is an external dated convention;
the released balance file does not identify a synchronized Bitcoin block.

## Reproducibility limitation

The dataset release supplies no SQL, BigQuery job ID, block height or hash,
UTC cutoff, schema version, or multi-address-script rule. The repository can
therefore reproduce every figure from the released file and checksum, but it
cannot independently reproduce the underlying chain-state extraction. A new
snapshot should pin a block height and hash, publish the SQL and job metadata,
and derive both balances and denominator from that same chain state.
