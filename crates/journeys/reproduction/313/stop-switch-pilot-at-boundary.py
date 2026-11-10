"""Correct injection magnitude from untreated pilot, without examining treatment CIs."""
from pathlib import Path
import json,os,statistics as st,subprocess,time
k=Path(__file__).parent;out=k/'switch-slowdown-v6-attempt-0-0';r=json.load(open(out/'point/report.json'));s=next(s for s in r['sessions'] if s['pair']==0 and s['side']=='point')
values=[x['duration_ns'] for x in s['samples'] if x['action']=='switch' and not x['warmup']];assert len(values)==4
baseline=st.median(values);prior=json.load(open(k/'switch-slowdown-v6-provenance.json'));old_pct=prior['requested_ms']*1e8/baseline
assert old_pct>11 or old_pct<9
policy=dict(wall_ns=time.time_ns(),untreated_pilot=str(out/'point/report.json'),untreated_pilot_median_ns=baseline,old_requested_ms=prior['requested_ms'],old_pct_of_current_control=old_pct,reason='Correct known injection magnitude from untreated pilot only; no treatment CI or verdict examined. Keep this whole pair as diagnostic; start fresh 20-pair proof. Require actual injected fraction of independent control median within 9-11% as well as slower CI.',original_data_retained=True)
(k/'switch-delay-reference-correction.json').write_text(json.dumps(policy,indent=2)+'\n')
# Wait for this independently bounded lease to finish restoring settings. The
# original run-pairs parent is busy parsing the final JSON before it can requeue.
expected=['python3',str(k/'lease.py'),str(k/'switch-slowdown-v6-attempt-0-0.json'),str(out)]
pids=[]
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:args=p.joinpath('cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
 except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 if args==expected:pids.append(int(p.name))
assert len(pids)<=1
print('Retain oversized-injection pilot; wait only for owned lease',pids,flush=True)
deadline=time.monotonic()+900
while pids and Path('/proc',str(pids[0])).exists():
 if time.monotonic()>deadline:raise RuntimeError('owned lease exceeded bounded cleanup; review')
 time.sleep(.05)
subprocess.run(['systemctl','--user','stop','313-switch-proof-and-typical'],check=True)
r=json.load(open(out/'report.json'))
assert r['guard']['contended'] is False and r['prior_acquisitions_passed'] and r['gpu_process_checks_passed'] and r['output_checked'] and len(r['sessions'])==2
for name in ['switch-slowdown-v6-config.json','switch-slowdown-v6-provenance.json','after-aa-switch.py']:(k/('initial-'+name)).write_bytes((k/name).read_bytes())
p=k/'switch-slowdown-v6-config.json';c=json.load(open(p));c['test_switch_delay_ms']=baseline*.1/1e6;p.write_text(json.dumps(c,indent=2)+'\n')
p=k/'switch-slowdown-v6-provenance.json';v=json.load(open(p));v.update(requested_ms=c['test_switch_delay_ms'],calibration_control_median_ns=baseline,calibration_control_kind='independent untreated pilot',calibration_control_report=str(out/'point/report.json'),calibration_selected_pairs=[0],calibration_selected_samples=4,requested_fraction_acceptance_pct=[9,11],prior_all_session_requested_ms=prior['requested_ms']);p.write_text(json.dumps(v,indent=2)+'\n')
p=k/'after-aa-switch.py';text=p.read_text().replace("'switch-slowdown-v6'","'switch-slowdown-v6-calibrated'").replace("'switch-slowdown-v6-complete.json'","'switch-slowdown-v6-calibrated-complete.json'");compile(text,str(p),'exec');p.write_text(text)
p=k/'validate-switch-slowdown.py';text=p.read_text().replace("passed=row['verdict']=='slower' and row['ci95'][1]<1", "passed=row['verdict']=='slower' and row['ci95'][1]<1 and 9<=100*actual/control<=11").replace('10% of A/A control median','10% of untreated pilot median');compile(text,str(p),'exec');p.write_text(text)
policy.update(completed_pilot_report=str(out/'report.json'),new_requested_ms=c['test_switch_delay_ms']);(k/'switch-delay-reference-correction.json').write_text(json.dumps(policy,indent=2)+'\n')
subprocess.run(['systemd-run','--user','--unit=313-switch-proof-calibrated','--property=CPUAffinity=0-21','--property=Nice=19','--property=StandardOutput=append:'+str(k/'switch-proof-and-typical.log'),'--property=StandardError=append:'+str(k/'switch-proof-and-typical.log'),'/usr/bin/python3',str(k/'after-aa-switch.py')],check=True)
print('Fresh fixed 20-pair proof queued, requested ms',c['test_switch_delay_ms'],flush=True)
