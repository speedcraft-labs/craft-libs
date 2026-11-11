"""After collection and the reporting-only patch, prove A/A statistics unchanged."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
paths = json.loads((root / 'ALL-PHASES.json').read_text())
scripts = Path('/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts')
sys.path.insert(0, str(scripts))
import lightcraft_session_report as current

spec = importlib.util.spec_from_file_location('frozen_report_65838523', root / 'report-frozen-65838523.py')
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)
assert hasattr(current, 'calibrated_mde'), 'Apply the final report-only correction first'
proof = dict(frozen_timing_driver=paths['driver_sha256'], aa={}, comparisons={})
for name in ('aa', 'heavy_aa'):
    report = json.loads(Path(paths[name]).read_text())
    assert report['comparison_complete'] and len(report['sessions']) == 40
    old = frozen.summarize(report['sessions'], aa=True)
    new = current.summarize(report['sessions'], aa=True)
    assert old == new == report['rows'], (name, 'A/A statistics changed')
    proof['aa'][name] = dict(rows=len(new), all_fields_bit_identical=True,
                            sha256=hashlib.sha256(json.dumps(new, sort_keys=True).encode()).hexdigest())
for name, calibration in (('slowdown', 'aa'), ('real50', 'aa'), ('heavy_real', 'heavy_aa')):
    report = json.loads(Path(paths[name]).read_text())
    reference = json.loads(Path(paths[calibration]).read_text())
    old = frozen.summarize(report['sessions'], calibration=reference)
    new = current.summarize(report['sessions'], calibration=reference)
    assert len(old) == len(new)
    for a, b in zip(old, new):
        assert {k: v for k, v in a.items() if k != 'minimum_detectable_effect_pct'} == {
            k: v for k, v in b.items() if k != 'minimum_detectable_effect_pct'}, (name, 'clock/bootstrap/verdict changed')
    proof['comparisons'][name] = dict(rows=len(new), only_mde_can_change=True,
                                    default_pixel_qualification_preserved=(name != 'real50' or
                                    report['publishable'] is False and report['primary_output_equivalent'] is False))
(root / 'final-analysis-identity-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(proof, indent=2))
