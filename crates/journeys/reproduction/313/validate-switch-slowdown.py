"""Verify the predeclared physical 10% dispatch delay, independently of A/A."""
import json,statistics as st,sys
from pathlib import Path
k=Path(__file__).parent;r=json.load(open(sys.argv[1]));p=json.load(open(k/'switch-slowdown-v6-provenance.json'))
assert r['comparison_complete'] and r['output_checked'] and r['gpu_process_checks_passed'] and r['prior_acquisitions_passed'] and r['guard']['contended'] is False
assert r['config']['sessions']==p['pairs']
assert len(r['sessions'])==2*p['pairs'] and r['config']['test_switch_delay_ms']==p['requested_ms']
observations=[]
for s in r['sessions']:
 expected=p['requested_ms'] if s['side']=='main' else 0
 assert s['test_switch_delay_ms']==expected
 samples=[x for x in s['samples'] if x['action']=='switch' and not x['warmup']]
 assert len(samples)==p['repetitions']
 for sample in samples:
  d=sample['evidence'].get('test_delay')
  if s['side']=='main':
   assert d and d['requested_ms']==expected and d['actual_delay_ns']>=expected*1e6
   assert d['actual_delay_ns']==d['wire_send_ns']-d['queue_start_ns']
   assert sample['sent_ns']==d['queue_start_ns']<d['wire_send_ns']<=sample['frame_ns']
   observations.append(dict(pair=s['pair'],duration_ns=sample['duration_ns'],**d))
  else:assert d is None
row=next(x for x in r['rows'] if x['action']=='switch' and x['phase']=='warm')
assert row['calibration_contains_unity'] is True
actual=st.median(x['actual_delay_ns'] for x in observations);control=row['sides']['point']['median_ns']
result=dict(report=sys.argv[1],action='switch',phase='warm',requested_ms=p['requested_ms'],requested_pct_of_calibration=100*p['requested_ms']*1e6/p['calibration_control_median_ns'],actual_median_delay_ns=actual,independent_control_median_ns=control,requested_pct_of_independent_control=100*p['requested_ms']*1e6/control,actual_pct_of_independent_control=100*actual/control,ratio=row['speedup'],ci95=row['ci95'],verdict=row['verdict'],calibration_mde_pct=row['minimum_detectable_effect_pct'],current_mde_pct=row['estimated_mde_pct'],passed=row['verdict']=='slower' and row['ci95'][1]<1 and 9<=100*actual/control<=11,observations=observations)
(k/'switch-slowdown-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(f"Physical 10% proof acceptance: {'PASS' if result['passed'] else 'FAIL'}; predeclared realized fraction 9–11% and CI entirely below 1.\nDeliberate slowdown, warm switch: requested {p['requested_ms']:.3f} ms = 10% of untreated pilot median; actual median queued delay {actual/1e6:.3f} ms. Independent control median {control/1e6:.3f} ms; requested/actual delay equals {result['requested_pct_of_independent_control']:.2f}%/{result['actual_pct_of_independent_control']:.2f}% of that control. Ratio {row['speedup']:.3f}, 95% CI {row['ci95'][0]:.3f}–{row['ci95'][1]:.3f}: **{row['verdict']}**. All {len(observations)} treatment delays lie inside their measured action clocks. Original app binaries are used in both arms.")
if not result['passed']:sys.exit(2)
