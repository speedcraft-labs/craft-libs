import json,os,subprocess,time
from pathlib import Path
k=Path(__file__).parent;root=Path('/jobs/work/speedcraft-labs');out=k/'gpu-lease-selftest-v5';cfg=k/'gpu-lease-selftest-config.json'
for attempt in range(10000):
 print('queued cleanup selftest',attempt,flush=True)
 with (k/f'gpu-lease-selftest-acquisition-{attempt}.log').open('wb') as log:
  env=dict(os.environ,SESSION_LEASE_SELF_TEST='1')
  code=subprocess.run(['flock',str(root/'bench.lock'),'flock','-x','-w','5',str(root/'gpu.lock'),'python3',str(k/'lease.py'),str(cfg),str(out)],env=env,stdout=log,stderr=log).returncode
 if not out.exists():
  print('admission rejected',code,flush=True);time.sleep(5);continue
 metadata=json.load(open(out/'point.display.json'))
 audit=json.load(open(out.with_suffix('.gpu-condition.json')))
 unit=json.load(open(out.with_suffix('.unit.json')))['unit']
 active=subprocess.run(['sudo','-n','systemctl','is-active',unit],capture_output=True,text=True)
 passed=(code==124 and metadata.get('power_mizer_active')==1 and metadata.get('power_mizer_restored') is True
         and active.stdout.strip() in ('inactive','failed','unknown','') and 'reset_output' in audit
         and not Path('/proc',str(metadata['xorg_pid'])).exists())
 result=dict(passed=passed,exit_code=code,unit=unit,unit_state=active.stdout.strip(),display=metadata,clock_audit=audit)
 (k/'gpu-lease-selftest-result.json').write_text(json.dumps(result,indent=2))
 print('cleanup selftest',passed,flush=True)
 if not passed:raise RuntimeError('cleanup proof failed; inspect retained output before more GPU work')
 break
