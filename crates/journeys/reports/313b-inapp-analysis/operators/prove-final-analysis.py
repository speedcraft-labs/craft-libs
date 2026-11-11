"""Prove every A/A field unchanged and comparisons change only MDE/qualification."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, '/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts')
import lightcraft_session_report as current

spec = importlib.util.spec_from_file_location('frozen_report_65838523', root / 'report-frozen-65838523.py')
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def collected_fields(row):
    # Producer appends this output qualifier after numerical summarization.
    return {key: value for key, value in row.items() if key not in ('upstream_equivalent', 'primary_equivalent', 'statistical_verdict_before_quality_gate')}


def prove(paths):
    assert hasattr(current, 'calibrated_mde'), 'Integrate the final sensitivity correction first'
    proof = dict(driver_sha256_by_cohort=paths['driver_sha256_by_cohort'], aa={}, comparisons={})
    for name in ('aa', 'heavy_aa', 'legacy_heavy_aa'):
        if name not in paths:
            continue
        path = Path(paths[name]); report = json.loads(path.read_text())
        assert report['comparison_complete'] and len(report['sessions']) == 40
        old = frozen.summarize(report['sessions'], aa=True)
        new = current.summarize(report['sessions'], aa=True)
        assert old == new == [collected_fields(row) for row in report['rows']], (name, 'A/A statistics changed')
        proof['aa'][name] = dict(rows=len(new), all_statistical_fields_bit_identical=True,
                                summary_sha256=digest(new), raw_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    for name, calibration in (('slowdown', 'aa'), ('real50', 'aa'),
                              ('heavy_real', 'heavy_aa'),
                              ('legacy_heavy_real_partial', 'legacy_heavy_aa')):
        if name not in paths:
            continue
        path = Path(paths[name]); report = json.loads(path.read_text())
        reference = json.loads(Path(paths[calibration]).read_text())
        old = frozen.summarize(report['sessions'], calibration=reference)
        new = current.summarize(report['sessions'], calibration=reference)
        assert len(old) == len(new) == len(report['rows'])
        for before, after, recorded in zip(old, new, report['rows']):
            strip_mde = lambda row: {key: value for key, value in row.items() if key != 'minimum_detectable_effect_pct'}
            assert strip_mde(before) == strip_mde(after), (name, 'clock/bootstrap/verdict changed')
            qualified = collected_fields(recorded)
            if name == 'real50':
                assert qualified['verdict'] == 'outputs differ; descriptive only'
                assert recorded['primary_equivalent'] is False
                assert recorded['statistical_verdict_before_quality_gate'] == after['verdict']
                qualified = dict(qualified, verdict=after['verdict'])
            assert strip_mde(after) == strip_mde(qualified), (name, 'collected statistics differ')
        if name == 'real50':
            assert not report['publishable'] and not report['primary_output_equivalent']
        if name == 'legacy_heavy_real_partial':
            assert not report['comparison_complete'] and len(report['sessions']) == 15
            assert all(row['verdict'] == 'insufficient paired sessions' for row in new)
        proof['comparisons'][name] = dict(rows=len(new), only_mde_can_change=True,
            observations_sha256=digest(report['sessions']),
            raw_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            output_qualification_preserved=True,
            no_protocol_pooling=True)
    return proof


if __name__ == '__main__':
    paths = json.loads((root / 'ALL-PHASES.json').read_text())
    assert all(name in paths for name in ('aa', 'heavy_aa', 'legacy_heavy_aa', 'slowdown', 'real50', 'heavy_real', 'legacy_heavy_real_partial'))
    result = prove(paths)
    (root / 'final-analysis-identity-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
