#!/usr/bin/env python3
"""Build the anonymous FC27 release from an explicit canonical-file allowlist.

No TeX compilation, figure regeneration, network requests, or author-file copies.
Run only after canonical figures, tables, and the anonymous PDF are current.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FIGURES = (
    'figure_attribution_two_models', 'figure_eth_merge_shift_calibration',
    'figure_bitcoin_top1m_capping_convergence', 'figure_family_parameter_sensitivity',
)
ANALYSIS = (
    'certify.py', 'test_certify.py', 'joint_capping.py', 'test_joint_capping.py',
    'requirements-fc27.txt', 'plot_all_figures.py', 'plot_eth_merge_shift_calibration.py',
    'summarize_bitcoin_top1m_capping_convergence.py', 'summarize_bitcoin_joint_certificates.py',
    'verify_bitcoin_joint_certificates.py', 'verify_eth_projection.py',
    'verify_eth_conditional.py',
    'summarize_bitcoin_top1m_alpha_variation.py', 'summarize_attribution_hhi_two_models.py',
)
DATA = (
    'readme_top_mill_addresses.md', 'bitcoin_top1m_capping_convergence_summary.csv',
    'bitcoin_joint_certificates_summary.csv',
    'bitcoin_merge_upper_gaps.json', 'eth_conditional_exact_check.json',
    'eth_active_validator_projection_2026-09-22.csv.gz',
    'eth_active_validator_projection_2026-09-22.csv.gz.metadata.json',
    'eth_active_validator_projection_2026-09-22.csv.gz.sha256',
    'eth_active_effective_balance_histogram_2026-09-22.csv',
    'eth_execution_withdrawal_address_groups_2026-09-22.csv',
    'eth_merge_shift_calibration_summary.csv', 'eth_merge_shift_calibration_metadata.json',
    'eth_validators_effective_2026-09-22.header.json',
    'eth_validators_effective_2026-09-22.request.json',
)
WEB = ('README.md', 'index.html', 'style.css', 'metrics.js', 'app.js', 'prepare_data.py',
       'test_metrics.js', 'test_ui.js', 'test_python_parity.py',
       'data/bitcoin_top10k.json', 'data/bitcoin_top1m.json', 'data/eth_top10k.json')
PUBLISHED = (
    'README.md', '14122023_binance.csv', '14122023_osmosis.csv',
    '25102024_aptos.csv', '25102024_axelar.csv', '25102024_celestia.csv',
    '25102024_celo.csv', '25102024_cosmos.csv', '25102024_injective.csv',
    '25102024_polygon.csv', '25102024_sui.csv',
    'empiricial-analysis-tnsm.csv', 'certificate_results.json',
    'ten_system_certificates.json',
    'breakdown_budgets.json',
    'aptos_shift_015_witness.csv', 'polygon_shift_015_witness.csv',
)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def sources(code_only=False):
    direct = ['FC27_REPRODUCIBILITY.md',
              'review/fc27_prior_claims_consensus_check.py',
              'review/fc27_prior_claims_ten_systems_check.py',
              'review/fc27_breakdown_budgets.py',
              'review/fc27_attribution_exact_checks.py', 'review/fc27_capping_checks.py',
              'tools/build_fc27_artifact.py', 'tools/verify_fc27_artifact.py']
    if not code_only:
        direct += ['fc27_submission.tex', 'fc27_submission.pdf',
                   'fc27_references.bib', 'llncs.cls', 'splncs04.bst']
    direct += [f'{figure}.{suffix}' for figure in FIGURES for suffix in ('pdf', 'png')]
    direct += [f'analysis-code/{name}' for name in ANALYSIS]
    direct += [f'data/{name}' for name in DATA]
    direct += [f'webapp/{name}' for name in WEB]
    direct += [f'review/data/motepalli2025/{name}' for name in PUBLISHED]
    result = {name: name for name in direct}
    for name in ('README.md', 'LICENSE', 'DATA_LICENSE.md', 'PUBLISHING.md',
                 '.gitignore', '.nojekyll', 'index.html'):
        result[name] = f'tools/fc27_artifact/{name}'
        result[f'tools/fc27_artifact/{name}'] = f'tools/fc27_artifact/{name}'
    for name in ('README.md', 'PUBLISHING.md'):
        template = f'tools/fc27_artifact/repository/{name}'
        result[template] = template
        if code_only:
            result[name] = template
            result[f'tools/fc27_artifact/{name}'] = template
    return result


def build(output, replace, code_only=False):
    if output == ROOT or ROOT in output.parents and output.name in ('webapp', 'data', 'analysis-code', 'review', 'tools'):
        raise SystemExit('Refusing to replace a canonical source directory')
    if output.exists():
        if not replace:
            raise SystemExit(f'{output} exists; use --replace to rebuild a generated artifact')
        marker = output / 'manifest.json'
        if not marker.exists() or json.loads(marker.read_text()).get('artifact') != 'fc27-moved-mass-merge':
            raise SystemExit('Refusing to replace a directory without an FC27 release manifest')
    mapping = sources(code_only)
    missing = [source for source in mapping.values() if not (ROOT / source).is_file()]
    raw = ROOT / 'data/top_mill_adresses.json'
    compressed = raw.with_suffix('.json.gz')
    if not raw.exists() and not compressed.exists():
        missing.append(str(raw.relative_to(ROOT)))
    if missing:
        raise SystemExit('Missing canonical inputs: ' + ', '.join(missing))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fc27-build-', dir=output.parent) as temp:
        bundle_name = 'fc27_repository' if code_only else 'fc27_supplementary_artifact'
        stage = Path(temp) / bundle_name
        stage.mkdir()
        for target, source in sorted(mapping.items()):
            destination = stage / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, destination)
        if code_only:
            guide = stage / 'FC27_REPRODUCIBILITY.md'
            content = guide.read_text()
            # The standalone code release has no paper build inputs.
            start = content.find('## Build the paper\n')
            if start != -1:
                end = content.index('## Provenance limits', start)
                content = content[:start] + content[end:]
            start = content.find('## Assemble the current anonymous artifact\n')
            if start != -1:
                content = content[:start] + (
                    '## Rebuild the code artifact\n\n'
                    'See `README.md` for the code-only build command and '
                    '`PUBLISHING.md` for GitHub Pages setup.\n'
                )
            guide.write_text(content)
        # Always canonicalize gzip headers, even when rebuilding from a bundle.
        opener = raw.open if raw.exists() else lambda mode: gzip.open(compressed, mode)
        with opener('rb') as source, (stage / 'data/top_mill_adresses.json.gz').open('wb') as sink:
            with gzip.GzipFile(fileobj=sink, mode='wb', filename='', mtime=0, compresslevel=9) as target:
                shutil.copyfileobj(source, target)
        files = {}
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                files[path.relative_to(stage).as_posix()] = {'sha256': digest(path), 'bytes': path.stat().st_size}
        manifest = {'artifact': 'fc27-moved-mass-merge',
                    'contents': 'code-data-figures' if code_only else 'paper-code-data-figures',
                    'merge_cost': 'sum over groups of (group total minus largest member)',
                    'merge_upper_status': 'sharp for unknown-count capping when rho <= omitted mass; otherwise a conservative Shift relaxation',
                    'files': files}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        lines = [f"{v['sha256']}  {name}\n" for name, v in files.items()]
        lines.append(f"{digest(stage / 'manifest.json')}  manifest.json\n")
        (stage / 'checksums.sha256').write_text(''.join(lines))
        archive = Path(temp) / 'release.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    info = zipfile.ZipInfo(bundle_name + '/' + path.relative_to(stage).as_posix(), (1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(stage), output)
        zip_path = output.with_suffix('.zip')
        shutil.move(str(archive), zip_path)
    print(f'Built {output}: {len(files)} files plus manifest/checksums')
    print(f'ZIP: {zip_path} ({zip_path.stat().st_size / 1048576:.2f} MiB)')
    print(f'SHA-256: {digest(zip_path)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'fc27_supplementary_artifact')
    parser.add_argument('--replace', action='store_true', help='replace an existing generated FC27 artifact')
    parser.add_argument('--code-only', action='store_true',
                        help='omit the paper, bibliography, and TeX build files for a code repository')
    args = parser.parse_args()
    build(args.output.resolve(), args.replace, args.code_only)


if __name__ == '__main__':
    main()
