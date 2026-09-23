#!/usr/bin/env python3
"""Reconstruct the pinned-state Ethereum histogram and partition offline.

Accept the checksummed raw Beacon response or its compact validator projection.
Compare reconstructed CSV bytes with the artifact. Explicit write flags create
new derived inputs from the checksummed raw response.
This verifies an observable grouping, not a chain state or controller mapping.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STEM = "eth_active_validator_projection_2026-09-22.csv.gz"
RAW_SHA256 = "273c82e554242c8305b20de991bfb3839445a80ddc2ea3a9547c3b62c5a0426b"
HISTOGRAM = "eth_active_effective_balance_histogram_2026-09-22.csv"
GROUPS = "eth_execution_withdrawal_address_groups_2026-09-22.csv"
REQUEST = DATA / "eth_validators_effective_2026-09-22.request.json"
HEADER = DATA / "eth_validators_effective_2026-09-22.header.json"
COLUMNS = ["index", "status", "effective_balance", "withdrawal_credentials"]
ACTIVE_STATUSES = {"active_ongoing", "active_exiting", "active_slashed"}
GROUP_COLUMNS = [
    "group_key", "validator_count", "effective_balance_gwei",
    "credential_00_count", "credential_01_count", "credential_02_count",
]


def pinned_request():
    request = json.loads(REQUEST.read_text())
    header = json.loads(HEADER.read_text())
    message = header["data"]["header"]["message"]
    root = request["state_root"]
    if request["slot"] != message["slot"] or root != message["state_root"]:
        raise ValueError("header and validator request identify different states")
    if request["validator_raw_sha256"] != RAW_SHA256:
        raise ValueError("request manifest identifies a different raw response")
    expected_url = f"https://ethereum-beacon-api.publicnode.com/eth/v1/beacon/states/{root}/validators?status=active"
    if request["validator_request"] != expected_url:
        raise ValueError("validator request is not the pinned active-state query")
    return request


def open_bytes(path: Path, *, decompress: bool = True):
    return gzip.open(path, "rb") if decompress and path.suffix == ".gz" else path.open("rb")


def sha256(path: Path, *, decompress: bool = False) -> str:
    result = hashlib.sha256()
    with open_bytes(path, decompress=decompress) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


class JSONStream:
    """Incremental decoder: the large response need not be loaded at once."""

    def __init__(self, stream):
        self.stream = stream
        self.buffer = ""
        self.position = 0
        self.eof = False
        self.decoder = json.JSONDecoder()

    def fill(self):
        chunk = self.stream.read(1024 * 1024)
        self.buffer = self.buffer[self.position:] + chunk
        self.position = 0
        self.eof = not chunk

    def peek(self):
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position].isspace():
                self.position += 1
            if self.position < len(self.buffer):
                return self.buffer[self.position]
            if self.eof:
                return ""
            self.fill()

    def take(self, expected):
        if self.peek() != expected:
            raise ValueError(f"expected JSON delimiter {expected!r}")
        self.position += 1

    def value(self):
        self.peek()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
                self.position = end
                return value
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self.fill()


def raw_rows(path: Path):
    pinned_request()
    if sha256(path, decompress=True) != RAW_SHA256:
        raise ValueError("raw response SHA-256 differs from the FC27 input")
    metadata = {}
    with open_bytes(path) as binary, io.TextIOWrapper(binary, encoding="utf-8") as stream:
        source = JSONStream(stream)
        source.take("{")
        found_data = False
        while source.peek() != "}":
            key = source.value()
            source.take(":")
            if key == "data":
                if found_data:
                    raise ValueError("duplicate data array")
                found_data = True
                source.take("[")
                while source.peek() != "]":
                    row = source.value()
                    status = row["status"]
                    if status not in ACTIVE_STATUSES:
                        raise ValueError(f"raw response includes non-active status {status!r}")
                    validator = row["validator"]
                    yield int(row["index"]), status, int(validator["effective_balance"]), validator["withdrawal_credentials"].lower()
                    if source.peek() != ",":
                        break
                    source.take(",")
                source.take("]")
            else:
                metadata[key] = source.value()
            if source.peek() != ",":
                break
            source.take(",")
        source.take("}")
        if source.peek():
            raise ValueError("unexpected data after raw response")
    if not found_data or metadata.get("finalized") is not True or metadata.get("execution_optimistic") is not False:
        raise ValueError("unexpected raw response envelope")


def projection_rows(path: Path):
    manifest = json.loads(Path(str(path) + ".metadata.json").read_text())
    if manifest["raw_response_sha256"] != RAW_SHA256:
        raise ValueError("projection manifest identifies a different raw source")
    request = pinned_request()
    if manifest["state_root"] != request["state_root"] or manifest["slot"] != request["slot"]:
        raise ValueError("projection manifest identifies a different chain state")
    if sha256(path) != manifest["compressed_sha256"]:
        raise ValueError("compressed projection checksum mismatch")
    if sha256(path, decompress=True) != manifest["uncompressed_csv_sha256"]:
        raise ValueError("projection CSV checksum mismatch")
    with open_bytes(path) as binary, io.TextIOWrapper(binary, encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError("unexpected projection columns")
        for row in reader:
            if row["status"] not in ACTIVE_STATUSES:
                raise ValueError("projection includes a non-active validator")
            yield int(row["index"]), row["status"], int(row["effective_balance"]), row["withdrawal_credentials"]


def csv_bytes(columns, rows) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def reconstruct(rows):
    histogram = Counter()
    groups = defaultdict(lambda: [0, 0, 0, 0, 0])
    group_maxima = defaultdict(int)
    indices = set()
    statuses = Counter()
    prefix_counts = Counter()
    prefix_effective_gwei = Counter()
    for index, status, effective, credential in rows:
        if index < 0 or index in indices or effective <= 0:
            raise ValueError("invalid/duplicate index or nonpositive effective balance")
        if status not in ACTIVE_STATUSES:
            raise ValueError("non-active validator status")
        indices.add(index)
        statuses[status] += 1
        if len(credential) != 66 or not credential.startswith("0x"):
            raise ValueError("invalid withdrawal credential")
        bytes.fromhex(credential[2:])
        prefix = credential[2:4]
        if prefix not in {"00", "01", "02"}:
            raise ValueError("unknown withdrawal-credential prefix")
        prefix_counts[prefix] += 1
        prefix_effective_gwei[prefix] += effective
        key = f"validator_index:{index}" if prefix == "00" else f"execution_address:0x{credential[-40:]}"
        group = groups[key]
        group[0] += 1
        group[1] += effective
        group[2 + int(prefix)] += 1
        group_maxima[key] = max(group_maxima[key], effective)
        histogram[effective] += 1
    histogram_bytes = csv_bytes(["effective_balance_gwei", "validator_count"], sorted(histogram.items()))
    group_bytes = csv_bytes(GROUP_COLUMNS, [(key, *groups[key]) for key in sorted(groups)])
    summary = {
        "validator_count": len(indices),
        "group_count": len(groups),
        "status_counts": dict(sorted(statuses.items())),
        "credential_prefix_counts": dict(sorted(prefix_counts.items())),
        "credential_prefix_effective_gwei": dict(sorted(prefix_effective_gwei.items())),
        "effective_balance_gwei": sum(balance * count for balance, count in histogram.items()),
        "merge_moved_effective_gwei": sum(group[1] - group_maxima[key] for key, group in groups.items()),
    }
    summary["merge_moved_mass"] = summary["merge_moved_effective_gwei"] / summary["effective_balance_gwei"]
    return histogram_bytes, group_bytes, summary


def write_projection(path: Path, rows, summary):
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with path.open("wb") as file, gzip.GzipFile(filename="", mode="wb", fileobj=file, mtime=0, compresslevel=9) as compressed:
        class HashingWriter:
            def write(self, text):
                encoded = text.encode("utf-8")
                digest.update(encoded)
                compressed.write(encoded)
                return len(text)
        writer = csv.writer(HashingWriter(), lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(sorted(rows))
    request = pinned_request()
    manifest = {
        "file": path.name,
        "columns": COLUMNS,
        "effective_balance_unit": "gwei",
        "row_order": "ascending integer validator index",
        "encoding": "UTF-8 CSV, LF line endings; gzip level 9, mtime 0, no filename header",
        "compressed_bytes": path.stat().st_size,
        "compressed_sha256": sha256(path),
        "uncompressed_csv_sha256": digest.hexdigest(),
        "raw_response_sha256": RAW_SHA256,
        "state_root": request["state_root"],
        "slot": request["slot"],
        "source_request": request["validator_request"],
        "source_download_completed_utc": request["validator_download_completed_utc"],
        "included_statuses": sorted(summary["status_counts"]),
        "limitations": [
            "Projection of a response requested by immutable state root from a public Beacon node.",
            "The request and header share a state root; the node's response is not independently authenticated to consensus.",
            "Withdrawal-address equality is not validated as common controller identity.",
        ],
        **summary,
    }
    Path(str(path) + ".metadata.json").write_text(json.dumps(manifest, indent=2) + "\n")
    Path(str(path) + ".sha256").write_text(f"{manifest['compressed_sha256']}  {path.name}\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--raw", type=Path, help="local raw Beacon JSON response, optionally gzip-compressed")
    source.add_argument("--projection", type=Path, help="compact CSV.gz and accompanying metadata JSON")
    parser.add_argument("--write-projection", type=Path, help="requires --raw; writes projection and checksum/metadata sidecars")
    parser.add_argument("--write-derived", action="store_true", help="requires --raw; writes histogram and group CSVs")
    parser.add_argument("--verify-dir", type=Path, default=DATA, help="directory containing the existing histogram and group CSVs")
    args = parser.parse_args()
    if args.write_projection and not args.raw:
        parser.error("--write-projection requires --raw")
    if args.write_derived and not args.raw:
        parser.error("--write-derived requires --raw")
    rows = list(raw_rows(args.raw)) if args.raw else projection_rows(args.projection or DATA / STEM)
    histogram, groups, summary = reconstruct(rows)
    for name, actual in [(HISTOGRAM, histogram), (GROUPS, groups)]:
        path = args.verify_dir / name
        if args.write_derived:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(actual)
        elif actual != path.read_bytes():
            raise ValueError(f"reconstructed {name} differs from supplied CSV")
    summary["histogram_and_groups"] = "both match the supplied CSVs byte for byte"
    if args.write_projection:
        summary["projection"] = write_projection(args.write_projection, rows, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
