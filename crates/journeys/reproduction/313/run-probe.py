import json,subprocess,time,os,sys
from pathlib import Path
k=Path(__file__).parent;root=Path('/jobs/work/speedcraft-labs')
label=sys.argv[1] if len(sys.argv)>1 else 'clock-capability'
for attempt in range(10000):
 cfg=k/f'{label}-{attempt}.json';cfg.write_text(json.dumps({'clock_probe':True}))
 out=k/f'{label}-{attempt}'
 status={'attempt':attempt,'state':'queued','wall_ns':time.time_ns()}
 (k/'clock-probe-status.json').write_text(json.dumps(status))
 print(status,flush=True)
 with (k/f'{label}-{attempt}.log').open('wb') as log:
  code=subprocess.run(['flock',str(root/'bench.lock'),'flock','-x','-w','5',str(root/'gpu.lock'),'timeout','--signal=TERM','--kill-after=5s','895s','python3',str(k/'lease.py'),str(cfg),str(out)],stdout=log,stderr=log).returncode
 status.update(exit_code=code,state='complete' if code==0 and (k/'clock-probe.json').exists() else 'probe failed' if (k/'clock-probe.json').exists() else 'admission rejected',wall_ns=time.time_ns())
 (k/'clock-probe-status.json').write_text(json.dumps(status));print(status,flush=True)
 if (k/'clock-probe.json').exists():break
 time.sleep(5)
