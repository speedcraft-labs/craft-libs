"""Complete a fixed acquisition selection, retaining all resource failures."""
import hashlib,json,os,subprocess,sys,threading,time
from pathlib import Path
k=Path(__file__).parent
root=Path('/jobs/work/speedcraft-labs')
config=json.load(open(sys.argv[1]));label=sys.argv[2]
driver=root/'wt/313-session-latency/crates/journeys/scripts/lightcraft_real_app.py'
frozen=hashlib.sha256(driver.read_bytes()).hexdigest()
def workload(c):
 return {key:value for key,value in c.items() if key not in ('pair','side','acquisition_sides','resume_report')}
def heartbeat():
 while True:
  os.utime(root/'targets/313-session-latency',None)
  time.sleep(30)
threading.Thread(target=heartbeat,daemon=True).start()
for generation in range(10000):
 if hashlib.sha256(driver.read_bytes()).hexdigest()!=frozen:
  raise RuntimeError('driver changed; review before resuming')
 paths=[Path(config['resume_report'])] if config.get('resume_report') else []
 for folder in k.glob(label+'-attempt-*'):
  if folder.is_dir():paths+=list(folder.glob('report.json'))+list(folder.glob('*/report.json'))
 candidates=[]
 for path in paths:
  try:report=json.load(open(path))
  except (OSError,json.JSONDecodeError):continue
  if (report.get('driver_sha256')==frozen and workload(report['config'])==workload(config)
      and report.get('guard',{}).get('contended') is False
      and report.get('prior_acquisitions_passed') and report.get('gpu_process_checks_passed')
      and report.get('output_checked') and not report.get('failure')):
   info=dict(actual={(s['tier'],s['pair'],s['side']) for s in report['sessions']},publishable=report.get('publishable'),comparison_complete=report.get('comparison_complete'))
   candidates.append((len(report['sessions']),path.stat().st_mtime,path,info))
 report=None  # Do not retain megabytes of every cumulative report while benchmarking.
 current=dict(config)
 if candidates:
  _,_,path,info=max(candidates,key=lambda x:x[:2])
  current['resume_report']=str(path)
  (k/(label+'-latest.txt')).write_text(str(path))
  selected={config['side']} if config.get('side') else set(config.get('acquisition_sides',config['sides']))
  expected={(tier,pair,side) for tier in config['payloads'] for pair in range(config['sessions']) for side in selected}
  actual=info['actual']
  print('checkpoint',path,'sessions',len(actual),flush=True)
  if expected<=actual:
   (k/(label+'-complete.json')).write_text(json.dumps(dict(report=str(path),publishable=info['publishable'],comparison_complete=info['comparison_complete']),indent=2))
   print('COMPLETE',path,flush=True)
   break
 cfg=k/f'{label}-generation-{generation}.json';cfg.write_text(json.dumps(current,indent=2))
 prefix=f'{label}-attempt-{generation}'
 env=dict(os.environ)
 if config.get('test_switch_delay_ms') is not None:
  env['CRAFT_JOURNEYS_TEST_SWITCH_DELAY_MS']=str(config['test_switch_delay_ms'])
 code=subprocess.run(['python3',str(k/'run-pairs.py'),str(cfg),prefix],env=env).returncode
 fatal=[]
 for path in k.glob(prefix+'-*/*/report.json'):
  try:report=json.load(open(path))
  except (OSError,json.JSONDecodeError):continue
  if report.get('failure') and not path.parent.parent.with_suffix('.lease-expired.json').exists():
   fatal.append((str(path),report['failure']))
 if fatal:raise RuntimeError('non-resource failure requires review: '+str(fatal))
 if config.get('require_contiguous_pair'):
  splits=list(k.glob(prefix+'-*.deferred.json'))+list(k.glob(prefix+'-*.lease-expired.json'))
  if splits:raise RuntimeError('contiguous-pair protocol interrupted; preserve whole acquisition for review: '+str(splits))
 print('attempt ended',code,'completed sides retained',flush=True)
else:raise RuntimeError('campaign retry limit reached')
