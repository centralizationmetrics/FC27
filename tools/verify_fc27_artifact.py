#!/usr/bin/env python3
"""Verify every release-manifest checksum without downloading or changing files."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()

def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    failed = []
    for name, expected in manifest['files'].items():
        path = ROOT / name
        if not path.is_file() or digest(path) != expected['sha256'] or path.stat().st_size != expected['bytes']:
            failed.append(name)
    if failed:
        raise SystemExit('Integrity check failed: ' + ', '.join(failed))
    expected_lines = [f"{entry['sha256']}  {name}\n" for name, entry in manifest['files'].items()]
    expected_lines.append(f"{digest(ROOT / 'manifest.json')}  manifest.json\n")
    if (ROOT / 'checksums.sha256').read_text() != ''.join(expected_lines):
        raise SystemExit('Integrity check failed: checksums.sha256 does not match manifest')
    print(f"Artifact integrity verified: {len(manifest['files'])} files and manifest.")

if __name__ == '__main__':
    main()
