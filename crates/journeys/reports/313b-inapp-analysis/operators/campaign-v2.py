"""Whole-pair campaign; retries only incomplete lease/admission failures, never values."""
import json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).parent.parent
config_path=Path(sys.argv[1]);name=sys.argv[2];base=json.loads(config_path.read_text())
prior=base.get('resume_report');env=dict(os.environ,CRAFT_JOURNEYS_INAPP_TIMING='1')
attempts=int(os.environ.get('LIGHTCRAFT_ACQUISITION_ATTEMPTS','3'))
assert 1<=attempts<=10
def post(body,path):
 path.write_text(body+'\n')
 done=subprocess.run(['gh','issue','comment','291','-R','speedcraft-labs/hyper','--body-file',str(path)],capture_output=True,text=True)
 path.with_suffix('.post.json').write_text(json.dumps(dict(status=done.returncode,stdout=done.stdout,stderr=done.stderr),indent=2))
def acquire(pair,selected,seed,label):
 for attempt in range(attempts):
  out=root/f'{name}-{pair}-{label}-attempt{attempt}'
  if out.exists():raise RuntimeError('Existing evidence must never be overwritten: '+str(out))
  c=dict(base,pair=pair,acquisition_sides=selected)
  if seed:c['resume_report']=seed
  cfg=out.with_suffix('.json');cfg.write_text(json.dumps(c,indent=2)+'\n')
  with out.with_suffix('.log').open('a') as log:
   while True:
    code=subprocess.run(['flock','/jobs/work/speedcraft-labs/bench.lock','flock','-x','-w','5','-E','76','/jobs/work/speedcraft-labs/gpu.lock','python3',str(root/'operators/lease.py'),str(cfg),str(out)],env=env,stdout=log,stderr=subprocess.STDOUT).returncode
    if code not in (76,77):break
    log.write(('Shared GPU occupied' if code==76 else 'Stress tier: benchmark queue nonempty')+'; both locks released before retry\n');log.flush();time.sleep(10 if code==76 else 60)
  if code in (75,124):
   # This is a completion/budget predicate, not a latency threshold or outlier test.
   proof=dict(status='excluded incomplete acquisition; whole selected group retried',code=code,config=str(cfg),seed=seed,selected=selected,attempt=attempt)
   out.with_suffix('.incomplete.json').write_text(json.dumps(proof,indent=2)+'\n')
   post(f'HANDOFF 313b — {name} pair{pair} acquisition {label} attempt{attempt} could not complete inside the840s lease ({code}); retained at `{out}`, excluded as an incomplete group. Retry uses the unchanged workload and seed `{seed}`; no successful whole pair is removed and no timing value triggers retries. After{attempts} incomplete attempts the campaign stops for inspection.',out.with_suffix('.incomplete-handoff.md'))
   continue
  if code:raise RuntimeError(f'Failed acquisition {out}, status{code}; inspect retained evidence')
  report=json.loads((out/'report.json').read_text())
  if report.get('failure') or report.get('guard',{}).get('contended') is not False:raise RuntimeError(f'Guard/failure {out}')
  if not all(any(s['pair']==pair and s['side']==side for s in report['sessions']) for side in selected):raise RuntimeError(f'Incomplete selected group {out}')
  return str(out/'report.json')
 raise RuntimeError(f'{pair}/{label}: {attempts} incomplete bounded acquisitions; do not extend lock time')
for pair in range(base['sessions']):
 if prior:
  previous=json.loads(Path(prior).read_text())
  if all(any(s['pair']==pair and s['side']==side for s in previous['sessions']) for side in base['sides']):continue
 prior=acquire(pair,['point','main'],prior,'primary')
 if 'upstream' in base['sides']:
  # Secondary column only; primary point/main stays adjacent in ONE acquisition.
  prior=acquire(pair,['upstream'],prior,'descriptive')
 report=json.loads(Path(prior).read_text())
 (root/f'{name}-latest.txt').write_text(prior+'\n')
 state=json.loads((root/'CURRENT-STATE.json').read_text());state.update(status=f'{name}: {pair+1}/{base["sessions"]} complete pairs',latest_report=prior,active_campaign=name,controller_parent=os.getpid());(root/'CURRENT-STATE.json').write_text(json.dumps(state,indent=2)+'\n')
 print(json.dumps(dict(pair=pair,status='accepted',report=prior)),flush=True)
 post(f'HANDOFF 313b — {name}: {pair+1}/{base["sessions"]} complete pairs. Latest cumulative `{prior}`, base config `{config_path}`; frozen app patch/driver, repetitions={base["repetitions"]}, warmups={base["warmups"]}. Primary builds contiguous AB/BA in one<=840s lease; upstream, when present, is a separately acquired descriptive column. No successful whole pair trimmed. Raw GPU guards, output checks, cold/warm rows and driver/app medians retained. Precision verdict is provisional until this fixed cohort finishes. Collected harness `{report["harness_revision"]}`; timing driver SHA256 `{report["driver_sha256"]}`; import boundary `{report["sessions"][-1].get("import_boundary", "confirmation-to-usable-grid (legacy)")}`. Recorder patch44fe9373 unchanged; production PR branches `algo/313b-inapp-timing`; PRs https://github.com/speedcraft-labs/lightcraft/pull/8 and https://github.com/speedcraft-labs/craft-libs/pull/37. Resume from this cumulative report with identical config, never an incomplete attempt.',root/f'{name}-{pair}-handoff.md')
print(prior,flush=True)
