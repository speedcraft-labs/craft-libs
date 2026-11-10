"""Validate the real shutdown delay inside each measured PID lifetime."""
import json,statistics as st,sys
from pathlib import Path
k=Path(__file__).parent;report=json.load(open(sys.argv[1]));p=json.load(open(k/('quit-slowdown-v6-provenance.json' if report['config'].get('require_contiguous_pair') else 'quit-slowdown-v5-provenance.json')))
assert report['comparison_complete'] and report['output_checked'] and report['gpu_process_checks_passed']
assert report['guard']['contended'] is False and report['prior_acquisitions_passed']
assert len(report['sessions'])==2*report['config']['sessions']
rows=[]
for s in report['sessions']:
 logs=[json.loads(x) for x in (Path(s['directory'])/'profile/test-quit-delay.jsonl').read_text().splitlines()]
 assert [x['pid'] for x in logs]==s['process_ids'], 'unexpected/missing injected child process'
 assert len(logs)==len(s['quit_samples'])
 for log,sample in zip(logs,s['quit_samples']):
  requested=p['requested_ns'] if s['side']=='main' else 0
  assert log['requested_ns']==requested and log['actual_delay_ns']>=requested
  assert sample['sent_ns']<=log['started_ns']<=log['ended_ns']<=sample['exit_ns']
  rows.append(dict(side=s['side'],pair=s['pair'],phase=sample['phase'],**log))
r=next(x for x in report['rows'] if x['action']=='quit' and x['phase']=='warm')
actual=st.median(x['actual_delay_ns'] for x in rows if x['side']=='main' and x['phase']=='warm')
control=r['sides']['point']['median_ns']
result=dict(report=sys.argv[1],action='quit',phase='warm',requested_ns=p['requested_ns'],actual_median_delay_ns=actual,calibration_control_median_ns=p['calibration_control_median_ns'],independent_control_median_ns=control,requested_pct_of_calibration=100*p['requested_ns']/p['calibration_control_median_ns'],requested_pct_of_independent_control=100*p['requested_ns']/control,actual_pct_of_independent_control=100*actual/control,ratio=r['speedup'],ci95=r['ci95'],verdict=r['verdict'],passed=r['verdict']=='slower' and r['ci95'][1]<1,pid_checks=len(rows),observations=rows)
(k/'quit-slowdown-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(f"Deliberate slowdown, warm quit: requested {p['requested_ns']/1e6:.3f} ms = 10% of A/A control median; realized median delay {actual/1e6:.3f} ms. Independent control median {control/1e6:.3f} ms; requested/realized delay is {result['requested_pct_of_independent_control']:.2f}%/{result['actual_pct_of_independent_control']:.2f}% of that control. Ratio {r['speedup']:.3f}, 95% CI {r['ci95'][0]:.3f}–{r['ci95'][1]:.3f}: **{r['verdict']}**. All {len(rows)} PID-specific delays fall within their measured quit clocks. Test-only shim used in both arms, zero delay for control; original binaries are used for the real comparison.")
if not result['passed']:sys.exit(2)
