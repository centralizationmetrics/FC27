#!/usr/bin/env python3
"""Ethereum withdrawal-address grouping and conditional Merge figure.

The source is a pinned-state Beacon API response for all active validators.
Validators with 0x01 or 0x02 withdrawal credentials are grouped when the
embedded 20-byte execution address is equal; every 0x00 validator remains a
singleton.  This is an observable withdrawal-address partition, not a
controller partition.  Conditional on two 0x01/0x02 validators having the
same controller if and only if their embedded execution withdrawal addresses
are equal, each validator has one controller and only whole 0x00 holdings may be
merged into the fixed groups or with one another. Their total share bounds
the additional Merge cost.  The generated metadata records that
condition explicitly.

The API request names the state root recorded in the saved finalized header.
The response is from a public provider, not independently authenticated to
Ethereum consensus.
"""

import csv
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
from certify import unresolved_merge_intervals


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VALIDATORS_JSON = DATA / "eth_validators_effective_2026-09-22.json"
HEADER_JSON = DATA / "eth_validators_effective_2026-09-22.header.json"
REQUEST_JSON = DATA / "eth_validators_effective_2026-09-22.request.json"
PROJECTION_CSV = DATA / "eth_active_validator_projection_2026-09-22.csv.gz"
HISTOGRAM_CSV = DATA / "eth_active_effective_balance_histogram_2026-09-22.csv"
GROUPS_CSV = DATA / "eth_execution_withdrawal_address_groups_2026-09-22.csv"
SUMMARY_CSV = DATA / "eth_merge_shift_calibration_summary.csv"
METADATA_JSON = DATA / "eth_merge_shift_calibration_metadata.json"
OUT_STEM = ROOT / "figure_eth_merge_shift_calibration"

CR_K = 10_000
NC_TAU = 0.5
STRESS_ALPHA = 0.10
BEACON_API_PROVIDER = "ethereum-beacon-api.publicnode.com"

LINE_TRUTH = "#111111"
COLOR_PARTITION = "#56b4e9"
COLOR_MERGE = "#d55e00"


def existing_path(path: Path) -> Path:
    if path.exists():
        return path
    gz_path = path.with_suffix(path.suffix + ".gz")
    if gz_path.exists():
        return gz_path
    return path


def open_text(path: Path):
    if path.exists():
        return path.open()
    gz_path = path.with_suffix(path.suffix + ".gz")
    if gz_path.exists():
        return gzip.open(gz_path, "rt")
    return path.open()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    target = existing_path(path)
    opener = gzip.open if target.suffix == ".gz" else open
    with opener(target, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sorted_shares(amounts: np.ndarray) -> np.ndarray:
    out = np.asarray(amounts, dtype=np.float64)
    out.sort()
    out = out[::-1]
    return out / out.sum()


def execution_withdrawal_group(row: dict) -> tuple[str, str]:
    credential = row["validator"]["withdrawal_credentials"].lower()
    if not credential.startswith("0x") or len(credential) != 66:
        raise ValueError(f"unexpected withdrawal credential: {credential!r}")
    prefix = credential[2:4]
    if prefix in {"01", "02"}:
        return f"execution_address:0x{credential[-40:]}", prefix
    if prefix == "00":
        return f"validator_index:{row['index']}", prefix
    raise ValueError(f"unsupported withdrawal-credential prefix: {prefix}")


def build_compact_inputs() -> tuple[np.ndarray, np.ndarray, dict]:
    with open_text(VALIDATORS_JSON) as stream:
        obj = json.load(stream)

    validator_balances: list[int] = []
    grouped_balance: defaultdict[str, int] = defaultdict(int)
    grouped_maximum: defaultdict[str, int] = defaultdict(int)
    grouped_count: defaultdict[str, int] = defaultdict(int)
    grouped_prefix_count: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {"00": 0, "01": 0, "02": 0}
    )
    prefix_counts = {"00": 0, "01": 0, "02": 0}
    prefix_effective_gwei = {"00": 0, "01": 0, "02": 0}
    status_counts: defaultdict[str, int] = defaultdict(int)
    indices: set[str] = set()

    for row in obj["data"]:
        status = row.get("status", "")
        if status not in {"active_ongoing", "active_exiting", "active_slashed"}:
            raise ValueError(f"stored response contains unexpected status {status!r}")
        index = str(row["index"])
        if index in indices:
            raise ValueError(f"duplicate validator index {index}")
        indices.add(index)
        effective_balance = int(row["validator"]["effective_balance"])
        if effective_balance <= 0:
            raise ValueError(f"nonpositive effective balance at validator {index}")
        group_key, prefix = execution_withdrawal_group(row)
        validator_balances.append(effective_balance)
        grouped_balance[group_key] += effective_balance
        grouped_maximum[group_key] = max(grouped_maximum[group_key], effective_balance)
        grouped_count[group_key] += 1
        grouped_prefix_count[group_key][prefix] += 1
        prefix_counts[prefix] += 1
        prefix_effective_gwei[prefix] += effective_balance
        status_counts[status] += 1

    with HISTOGRAM_CSV.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["effective_balance_gwei", "validator_count"])
        values, counts = np.unique(np.asarray(validator_balances, dtype=np.int64), return_counts=True)
        writer.writerows(zip(values.tolist(), counts.tolist()))

    with GROUPS_CSV.open("w", newline="") as stream:
        fieldnames = [
            "group_key",
            "validator_count",
            "effective_balance_gwei",
            "credential_00_count",
            "credential_01_count",
            "credential_02_count",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for key in sorted(grouped_balance):
            prefix_count = grouped_prefix_count[key]
            writer.writerow(
                {
                    "group_key": key,
                    "validator_count": grouped_count[key],
                    "effective_balance_gwei": grouped_balance[key],
                    "credential_00_count": prefix_count["00"],
                    "credential_01_count": prefix_count["01"],
                    "credential_02_count": prefix_count["02"],
                }
            )

    header = json.loads(HEADER_JSON.read_text())
    header_data = header.get("data", {})
    header_message = ((header_data.get("header") or {}).get("message") or {})
    request = json.loads(REQUEST_JSON.read_text())
    if header_message.get("state_root") != request["state_root"] or header_message.get("slot") != request["slot"]:
        raise ValueError("saved header does not match the pinned validator request")
    if request["state_root"] not in request["validator_request"] or "status=active" not in request["validator_request"]:
        raise ValueError("validator request is not pinned to the expected active state")
    nonsingleton_keys = [key for key, count in grouped_count.items() if count > 1]
    nonsingleton_balance = sum(grouped_balance[key] for key in nonsingleton_keys)
    moved_balance = sum(grouped_balance[key] - grouped_maximum[key] for key in grouped_balance)
    metadata = {
        "execution_optimistic": obj.get("execution_optimistic"),
        "finalized": obj.get("finalized"),
        "validator_count": len(validator_balances),
        "group_count": len(grouped_balance),
        "nonsingleton_group_count": len(nonsingleton_keys),
        "affected_validator_count": sum(grouped_count[key] for key in nonsingleton_keys),
        "nonsingleton_group_mass": nonsingleton_balance / sum(validator_balances),
        "merge_moved_effective_gwei": moved_balance,
        "merge_moved_mass": moved_balance / sum(validator_balances),
        "denominator_effective_gwei": sum(validator_balances),
        "included_statuses": sorted(status_counts),
        "status_counts": dict(sorted(status_counts.items())),
        "credential_prefix_counts": prefix_counts,
        "credential_prefix_effective_gwei": prefix_effective_gwei,
        "raw_response_sha256": sha256_file(VALIDATORS_JSON),
        "requested_by_state_root": True,
        "paired_header": {
            "block_root": header_data.get("root"),
            "slot": header_message.get("slot"),
            "state_root": header_message.get("state_root"),
        },
        "state_binding": "validator request uses the state root in the saved finalized header; provider response is not independently authenticated",
    }
    return (
        sorted_shares(np.asarray(validator_balances, dtype=np.float64)),
        sorted_shares(np.asarray(list(grouped_balance.values()), dtype=np.float64)),
        metadata,
    )


def load_histogram_vector() -> np.ndarray:
    balances: list[float] = []
    with HISTOGRAM_CSV.open() as stream:
        for row in csv.DictReader(stream):
            balances.extend(
                [float(row["effective_balance_gwei"])] * int(row["validator_count"])
            )
    return sorted_shares(np.asarray(balances, dtype=np.float64))


def load_group_vector() -> np.ndarray:
    with GROUPS_CSV.open() as stream:
        balances = [float(row["effective_balance_gwei"]) for row in csv.DictReader(stream)]
    return sorted_shares(np.asarray(balances, dtype=np.float64))


def load_conditional_shares() -> tuple[list[float], list[float]]:
    """Separate fixed withdrawal groups from unresolved whole validator holdings."""
    with GROUPS_CSV.open() as stream:
        rows = list(csv.DictReader(stream))
    total = sum(int(row['effective_balance_gwei']) for row in rows)
    fixed = [int(row['effective_balance_gwei'])/total for row in rows
             if not int(row['credential_00_count'])]
    unresolved = [int(row['effective_balance_gwei'])/total for row in rows
                  if int(row['credential_00_count'])]
    return sorted(fixed, reverse=True), sorted(unresolved, reverse=True)


def unresolved_00_mass() -> tuple[int, int, int, float]:
    total_gwei = 0
    unresolved_gwei = 0
    unresolved_validators = 0
    with GROUPS_CSV.open() as stream:
        for row in csv.DictReader(stream):
            balance = int(row["effective_balance_gwei"])
            total_gwei += balance
            count_00 = int(row["credential_00_count"])
            if count_00:
                if (
                    count_00 != 1
                    or int(row["validator_count"]) != 1
                    or int(row["credential_01_count"])
                    or int(row["credential_02_count"])
                ):
                    raise ValueError("0x00 group is not a pure singleton group")
                unresolved_validators += count_00
                unresolved_gwei += balance
    if total_gwei <= 0:
        raise ValueError("empty withdrawal-address grouping")
    return (
        unresolved_validators,
        unresolved_gwei,
        total_gwei,
        unresolved_gwei / total_gwei,
    )


def load_vectors() -> tuple[np.ndarray, np.ndarray, dict]:
    if existing_path(VALIDATORS_JSON).exists():
        return build_compact_inputs()
    metadata_file = json.loads(METADATA_JSON.read_text())
    for path, key in ((HISTOGRAM_CSV, "histogram_sha256"), (GROUPS_CSV, "groups_sha256")):
        actual = sha256_file(path)
        if actual != metadata_file[key]:
            raise ValueError(f"checksum mismatch for {path}: {actual} != {metadata_file[key]}")
    metadata = metadata_file["validator_snapshot"]
    # Compact group totals alone cannot identify the largest validator in
    # each group. Reconstruct the moved-mass cost from the validator projection.
    from verify_eth_projection import projection_rows, reconstruct
    _, _, reconstructed = reconstruct(projection_rows(PROJECTION_CSV))
    metadata["merge_moved_effective_gwei"] = reconstructed["merge_moved_effective_gwei"]
    metadata["merge_moved_mass"] = reconstructed["merge_moved_mass"]
    return load_histogram_vector(), load_group_vector(), metadata


def level_cap(x: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return x.copy()
    if amount >= float(x.sum()):
        return np.zeros_like(x)
    lo, hi = 0.0, float(x[0])
    for _ in range(80):
        mid = (lo + hi) / 2
        removed = float(np.maximum(x - mid, 0.0).sum())
        if removed > amount:
            lo = mid
        else:
            hi = mid
    return np.minimum(x, (lo + hi) / 2)


def tail_trim(x: np.ndarray, amount: float) -> np.ndarray:
    out = x.copy()
    remaining = float(amount)
    for index in range(out.size - 1, -1, -1):
        if remaining <= 0:
            break
        removed = min(float(out[index]), remaining)
        out[index] -= removed
        remaining -= removed
    return out


def cr(x: np.ndarray) -> float:
    return float(x[: min(CR_K, x.size)].sum())


def nc(x: np.ndarray) -> float:
    index = int(np.searchsorted(np.cumsum(x), NC_TAU, side="left"))
    return float(index + 1) if index < x.size else float("nan")


def hhi(x: np.ndarray) -> float:
    return float(np.dot(x, x))


def metric_value(x: np.ndarray, metric: str) -> float:
    return {"cr": cr, "nc": nc, "hhi": hhi}[metric](x)


def shift_interval(x: np.ndarray, metric: str, alpha: float) -> tuple[float, float]:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("Shift alpha must lie in [0,1]")
    if metric == "cr":
        return cr(level_cap(x, alpha)), min(1.0, cr(x) + alpha)
    if metric == "nc":
        lower = float(np.searchsorted(np.cumsum(x), NC_TAU - alpha, side="left") + 1)
        return lower, nc(level_cap(x, alpha))
    if metric == "hhi":
        amount = min(alpha, 1.0 - float(x[0]))
        lower = hhi(level_cap(x, alpha))
        upper = (float(x[0]) + amount) ** 2 + hhi(tail_trim(x[1:], amount))
        return lower, upper
    raise ValueError(metric)


def compute_rows(
    validator: np.ndarray, grouped: np.ndarray, conditional_rho: float, merge_budget: float,
    fixed: list[float], unresolved: list[float],
) -> list[dict[str, object]]:
    specs = [("cr", f"CR_{CR_K}"), ("nc", f"NC_{NC_TAU:g}"), ("hhi", "HHI")]
    rows = []
    conditional = unresolved_merge_intervals(fixed, unresolved, CR_K, NC_TAU)
    for metric, label in specs:
        conditional_lower, conditional_upper = conditional[metric]
        stress_lower, stress_upper = shift_interval(grouped, metric, STRESS_ALPHA)
        validator_value = metric_value(validator, metric)
        if metric == "cr":
            merge_lower, merge_upper = validator_value, min(1.0, validator_value + merge_budget)
        elif metric == "nc":
            merge_lower = float(np.searchsorted(np.cumsum(validator), NC_TAU - merge_budget, side="left") + 1)
            merge_upper = validator_value
        else:
            amount = min(merge_budget, 1.0 - float(validator[0]))
            merge_lower = validator_value
            merge_upper = (float(validator[0]) + amount)**2 + hhi(tail_trim(validator[1:], amount))
        rows.append(
            {
                "metric": metric,
                "label": label,
                "validator_label_value": validator_value,
                "withdrawal_address_value": metric_value(grouped, metric),
                "withdrawal_partition_moved_mass": merge_budget,
                "validator_merge_safe_lower": merge_lower,
                "validator_merge_safe_upper": merge_upper,
                "unresolved_00_rho": conditional_rho,
                "conditional_merge_lower": conditional_lower,
                "conditional_merge_upper": conditional_upper,
                "stress_alpha": STRESS_ALPHA,
                "stress_shift_lower": stress_lower,
                "stress_shift_upper": stress_upper,
            }
        )
    return rows


def write_rows(rows: list[dict[str, object]]) -> None:
    with SUMMARY_CSV.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def metric_label(metric: str) -> str:
    return {
        "cr": r"$\mathrm{CR}_{10^4}$",
        "nc": r"$\mathrm{NC}_{1/2}$",
        "hhi": r"$\mathrm{HHI}$",
    }[metric]


def plot(rows: list[dict[str, object]]) -> None:
    width_in = 12.2 / 2.54
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 8.5,
            "axes.titlesize": 9.0,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.0,
            "legend.fontsize": 8.0,
            "axes.grid": True,
            "grid.color": "#b8b8b8",
            "grid.alpha": 0.42,
            "grid.linewidth": 0.45,
            "pdf.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(width_in, 2.45), constrained_layout=False)
    band_half_width = 0.12
    merge_fill = matplotlib.colors.to_rgba(COLOR_MERGE, 0.16)

    for axis, row in zip(axes, rows):
        validator_value = float(row["validator_label_value"])
        grouped_value = float(row["withdrawal_address_value"])
        lower = float(row["conditional_merge_lower"])
        upper = float(row["conditional_merge_upper"])
        axis.scatter(0, validator_value, marker="o", color=LINE_TRUTH, s=24, zorder=4)
        axis.scatter(
            1,
            grouped_value,
            marker="D",
            facecolor=COLOR_PARTITION,
            edgecolor=LINE_TRUTH,
            linewidth=0.7,
            s=25,
            zorder=4,
        )
        axis.plot([1, 2 - band_half_width], [grouped_value, lower], color=COLOR_MERGE, linewidth=1)
        axis.plot([1, 2 - band_half_width], [grouped_value, upper], color=COLOR_MERGE, linewidth=1)
        axis.fill_between(
            [2 - band_half_width, 2 + band_half_width],
            [lower, lower],
            [upper, upper],
            facecolor=merge_fill,
            hatch="////",
            edgecolor=COLOR_MERGE,
            linewidth=0.8,
            zorder=3,
        )
        for endpoint in (lower, upper):
            axis.plot(
                [2 - band_half_width, 2 + band_half_width],
                [endpoint, endpoint],
                color=COLOR_MERGE,
                linewidth=1.25,
                linestyle=(0, (1, 1.4)),
                zorder=4,
            )
        axis.set_title(metric_label(str(row["metric"])))
        axis.set_xlim(-0.3, 2.3)
        axis.set_xticks([0, 1, 2], ["V", "W", "M"])
        if row["metric"] in {"nc", "hhi"}:
            axis.set_yscale("log")
        axis.tick_params(axis="x", length=0, pad=2)
        axis.tick_params(axis="y", width=0.55, length=2.5, pad=1.5)
        for spine in axis.spines.values():
            spine.set_linewidth(0.65)

    axes[0].set_ylabel("Value", labelpad=2)
    fig.subplots_adjust(left=0.085, right=0.995, top=0.90, bottom=0.34, wspace=0.48)
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=LINE_TRUTH,
            markeredgecolor=LINE_TRUTH,
            markersize=4.5,
            label="V: validator labels",
        ),
        Line2D(
            [0],
            [0],
            marker="D",
            color="none",
            markerfacecolor=COLOR_PARTITION,
            markeredgecolor=LINE_TRUTH,
            markeredgewidth=0.7,
            markersize=4.5,
            label="W: withdrawal-address partition",
        ),
        Patch(
            facecolor=merge_fill,
            hatch="////",
            edgecolor=COLOR_MERGE,
            label=r"M: conditional Merge",
        ),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=2,
        frameon=False,
        handlelength=1.5,
        handletextpad=0.55,
        columnspacing=1.2,
        labelspacing=0.45,
    )
    for extension in ("pdf", "png"):
        fig.savefig(f"{OUT_STEM}.{extension}", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def main() -> None:
    request = json.loads(REQUEST_JSON.read_text())
    validator, grouped, validator_metadata = load_vectors()
    unresolved_count, unresolved_gwei, total_gwei, rho_00 = unresolved_00_mass()
    if unresolved_count != validator_metadata["credential_prefix_counts"]["00"]:
        raise ValueError("0x00 validator count disagrees with snapshot metadata")
    if total_gwei != validator_metadata["denominator_effective_gwei"]:
        raise ValueError("grouped denominator disagrees with snapshot metadata")
    prefix_effective_gwei = validator_metadata.get("credential_prefix_effective_gwei")
    if prefix_effective_gwei and unresolved_gwei != prefix_effective_gwei["00"]:
        raise ValueError("0x00 effective balance disagrees with snapshot metadata")
    merge_budget = validator_metadata["merge_moved_mass"]
    rows = compute_rows(validator, grouped, rho_00, merge_budget, *load_conditional_shares())
    write_rows(rows)
    metadata = {
        "claim_label": "execution_withdrawal_address_partition_with_whole_validator_merge",
        "validator_source": str(PROJECTION_CSV.relative_to(ROOT)),
        "raw_response_source": str(VALIDATORS_JSON.with_suffix(".json.gz").relative_to(ROOT)),
        "header_source": str(HEADER_JSON.relative_to(ROOT)),
        "histogram_source": str(HISTOGRAM_CSV.relative_to(ROOT)),
        "group_source": str(GROUPS_CSV.relative_to(ROOT)),
        "beacon_api_provider": BEACON_API_PROVIDER,
        "beacon_api_endpoint": request["validator_request"],
        "download_completed_utc": request["validator_download_completed_utc"],
        "state_root": request["state_root"],
        "slot": request["slot"],
        "header_sha256": sha256_file(HEADER_JSON),
        "validator_snapshot": validator_metadata,
        "partition_rule": (
            "merge 0x01 and 0x02 validators iff their embedded 20-byte execution "
            "withdrawal address is equal; retain every 0x00 validator as a singleton"
        ),
        "partition_interpretation": (
            "exact for the stated withdrawal-address rule; each validator has one controller. The Merge certificate is "
            "controller-level only if two 0x01/0x02 validators have the same controller "
            "if and only if their embedded execution withdrawal addresses are equal, so "
            "only whole 0x00 holdings may merge into these groups or with one another"
        ),
        "merge_budget_convention": (
            "total moved mass: each group retains its largest validator holding "
            "and absorbs the other whole holdings; receiving holdings are not charged"
        ),
        "known_limitations": [
            "one controller may use several withdrawal addresses",
            "one pooled or contract withdrawal address may serve several controllers or beneficiaries",
            "withdrawal authority is distinct from the validator signing key",
            "the response was supplied by a public Beacon node and was not independently authenticated to consensus",
        ],
        "conditional_merge": {
            "unresolved_set": "0x00 credential singleton groups",
            "unresolved_validator_count": unresolved_count,
            "unresolved_effective_gwei": unresolved_gwei,
            "denominator_effective_gwei": total_gwei,
            "rho_00": rho_00,
            "grouping_restriction": "each validator has one controller; distinct withdrawal-address groups cannot merge; unresolved whole holdings may join them or one another",
            "endpoint_status": "sharp; every endpoint is attained by a finite whole-holding grouping",
            "status": (
                "total unresolved share bounds additional moved mass, conditional on each validator having one controller and two 0x01/0x02 validators having "
                "the same controller if and only if their embedded execution withdrawal "
                "addresses are equal, so only mass carried by 0x00 validators may be reassigned"
            ),
        },
        "stress_shift": {
            "alpha": STRESS_ALPHA,
            "status": "uncalibrated sensitivity value, not an estimated error rate",
        },
        "histogram_sha256": sha256_file(HISTOGRAM_CSV),
        "groups_sha256": sha256_file(GROUPS_CSV),
        "summary_sha256": sha256_file(SUMMARY_CSV),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    METADATA_JSON.write_text(json.dumps(metadata, indent=2) + "\n")
    plot(rows)
    print(f"summary {SUMMARY_CSV.relative_to(ROOT)}")
    print(f"metadata {METADATA_JSON.relative_to(ROOT)}")
    print(f"histogram {HISTOGRAM_CSV.relative_to(ROOT)}")
    print(f"groups {GROUPS_CSV.relative_to(ROOT)}")
    print(f"conditional rho_00 {rho_00:.12f}")
    print(f"partition moved-mass budget {merge_budget:.12f}")
    print(f"partition-budget safe HHI upper {rows[2]['validator_merge_safe_upper']:.12f}")
    print(f"figure {OUT_STEM.relative_to(ROOT)}.pdf")


if __name__ == "__main__":
    main()
