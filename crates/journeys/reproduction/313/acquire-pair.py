# One bounded pair, but an independently reset NVIDIA X server for each build.
import json,subprocess,sys,shutil,os,time
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
for side in order:
 if side not in selected:continue
 if any(s['pair']==config['pair'] and s['side']==side for s in existing):continue
 remaining=(int(os.environ.get('SESSION_LEASE_DEADLINE_NS','9999999999999999999'))-time.monotonic_ns())/1e9
 if last_duration is not None and remaining<last_duration*1.5+30:
  out.with_suffix('.deferred.json').write_text(json.dumps(dict(side=side,remaining_seconds=remaining,preceding_side_seconds=last_duration,required_headroom_seconds=last_duration*1.5+30,reason='defer a new side rather than predictably overrun the lease')))
  sys.exit(75)
 c=dict(config,side=side)
 if prior:c['resume_report']=prior
 path=out/(side+'.json');path.write_text(json.dumps(c,indent=2));destination=out/side
 side_started=time.monotonic()
 code=subprocess.run(['python3',str(k/'acquire-display.py'),str(path),str(destination)]).returncode
 last_duration=time.monotonic()-side_started
 report=json.load(open(destination/'report.json'))
 if report.get('failure') or report.get('guard',{}).get('contended') is not False:
  raise RuntimeError(f'pair {config["pair"]} side {side} failed: '+str(report.get('failure',code)))
 if not any(s['pair']==config['pair'] and s['side']==side for s in report['sessions']):raise RuntimeError('missing completed side')
 existing=report['sessions']
 prior=str(destination/'report.json')
 shutil.copy2(prior,out/'report.json')
# Byte-identical convenience copy; the original guarded report remains in side/.
shutil.copy2(prior,out/'report.json')
