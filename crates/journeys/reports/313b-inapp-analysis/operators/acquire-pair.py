# One bounded pair, but an independently reset NVIDIA X server for each build.
import json,subprocess,sys,shutil,os,time,statistics,hashlib
from pathlib import Path
k=Path(__file__).parent;cfg=Path(sys.argv[1]);out=Path(sys.argv[2]);config=json.load(open(cfg))
unit=Path('/proc/self/cgroup').read_text().strip().split('/')[-1]
out.with_suffix('.unit.json').write_text(json.dumps(dict(unit=unit,config=str(cfg),out=str(out))))
out.mkdir(parents=True,exist_ok=False)
order=('point','main','upstream') if config['pair']%2==0 else ('upstream','main','point')
selected={config['side']} if config.get('side') else set(config.get('acquisition_sides',config['sides']))
prior=config.get('resume_report')
existing=json.load(open(prior))['sessions'] if prior else []
last_duration=None
# The hard840s lease is authoritative. Wall-time forecasts are diagnostic:
# two initial real acquisitions were falsely declined at381/373s remaining,
# while an identical main later finished in362s (forecast322s). Do not select
# complete pairs using that noisy external verification/control wall clock.
forecast_factor=1.25 if config.get('import_only') else 1.5
# File-cache preparation can make the first build much longer. Forecast the
# second from previous complete second-side wall times when available. The
# hard lease still rejects/retains every incomplete whole pair. Starting a new
# side requires only a fixed30s work/cleanup allowance, never an action value.
second_history={};calibration_history={}
if config.get('import_only'):
 for pair in sorted({s['pair'] for s in existing}):
  primary=[s for s in existing if s['pair']==pair and s['side'] in ('point','main')]
  if len(primary)==2:
   second=max(primary,key=lambda s:s['launch_ns'])
   second_history.setdefault(second['side'],[]).append((second['exit_ns']-second['launch_ns'])/1e9)
 # An initial real pair has no local history. Its main binary is identical to
 # the closed A/A B build; use its observed second-side lifecycle wall times
 # rather than multiplying the much slower fork-point first side. Never borrow
 # from a different binary, protocol, corpus tier, or unfinished control.
 if config.get('aa_report'):
  calibration=json.load(open(config['aa_report']))
  fields=('measurement_method','tiers','repetitions','warmups','import_only','gpu_state')
  assert calibration['comparison_complete'] and calibration['publishable']
  assert all(config.get(f)==calibration['config'].get(f) for f in fields)
  # k lives in keep/<ticket>/operators; derive the shared speedcraft-labs root.
  driver=k.parents[2]/'wt/313b-libs/crates/journeys/scripts/lightcraft_real_app.py'
  assert hashlib.sha256(driver.read_bytes()).hexdigest()==calibration['driver_sha256']
  for role,revision in config['revisions'].items():
   if second_history.get(role):continue
   with open(revision['binary'],'rb') as binary:actual=hashlib.file_digest(binary,'sha256').hexdigest()
   compatible={side for side,digest in calibration['binary_sha256'].items() if digest==actual}
   history=[]
   for pair in sorted({s['pair'] for s in calibration['sessions']}):
    primary=[s for s in calibration['sessions'] if s['pair']==pair and s['side'] in ('point','main')]
    if len(primary)!=2:continue
    second=max(primary,key=lambda s:s['launch_ns'])
    if second['side'] in compatible:history.append((second['exit_ns']-second['launch_ns'])/1e9)
   if history:second_history[role]=history;calibration_history[role]=str(config['aa_report'])

for side in order:
 if side not in selected:continue
 if any(s['pair']==config['pair'] and s['side']==side for s in existing):continue
 remaining=(int(os.environ.get('SESSION_LEASE_DEADLINE_NS','9999999999999999999'))-time.monotonic_ns())/1e9
 historical=second_history.get(side,[])[-6:]
 required=(statistics.median(historical)*1.5+30 if historical else last_duration*forecast_factor+30 if last_duration is not None else 0)
 prediction=dict(side=side,remaining_seconds=remaining,preceding_side_seconds=last_duration,forecast_headroom_seconds=required,historical_second_side_seconds=historical,calibration_history=calibration_history.get(side),method='matching-binary complete second-side median *1.5+30s' if historical else 'preceding side *factor+30s',forecast_factor=1.5 if historical else forecast_factor,admission_rule='fixed30s minimum; forecast advisory; hard840s deadline authoritative')
 if last_duration is not None:
  out.with_suffix('.admission-forecast.json').write_text(json.dumps(prediction))
  if remaining<30:
   out.with_suffix('.deferred.json').write_text(json.dumps(dict(prediction,reason='insufficient fixed30s allowance before the hard840s deadline')))
   sys.exit(75)
 c=dict(config,side=side)
 if prior:c['resume_report']=prior
 path=out/(side+'.json');path.write_text(json.dumps(c,indent=2));destination=out/side
 side_started=time.monotonic()
 code=subprocess.run(['python3',str(k/'acquire-display.py'),str(path),str(destination)]).returncode
 wall_duration=time.monotonic()-side_started
 report=json.load(open(destination/'report.json'))
 if report.get('failure') or report.get('guard',{}).get('contended') is not False:
  raise RuntimeError(f'pair {config["pair"]} side {side} failed: '+str(report.get('failure',code)))
 if not any(s['pair']==config['pair'] and s['side']==side for s in report['sessions']):raise RuntimeError('missing completed side')
 existing=report['sessions']
 accepted=next(s for s in existing if s['pair']==config['pair'] and s['side']==side)
 # Admission may have waited for a foreign GPU user to finish. Predict the next
 # side from accepted app work plus validation/cleanup, not that one-off wait.
 last_duration=(time.perf_counter_ns()-accepted['launch_ns'])/1e9
 (out/(side+'.forecast.json')).write_text(json.dumps(dict(full_side_seconds=wall_duration,accepted_work_seconds=last_duration,excluded_admission_seconds=max(0,wall_duration-last_duration),definition='accepted launch through validation/cleanup; actual action clocks untouched'),indent=2))
 prior=str(destination/'report.json')
 shutil.copy2(prior,out/'report.json')
# Byte-identical convenience copy; the original guarded report remains in side/.
shutil.copy2(prior,out/'report.json')
