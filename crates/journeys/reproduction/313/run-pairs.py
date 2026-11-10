import json,os,subprocess,sys
from pathlib import Path
k=Path(__file__).parent;config=json.load(open(sys.argv[1]));label=sys.argv[2];base=Path('/jobs/work/speedcraft-labs')
env=dict(os.environ,WGPU_BACKEND='vulkan',__GL_SHADER_DISK_CACHE_PATH=str(base/'targets/313-session-latency/gpu-cache'))
prior=config.get('resume_report')
for pair in range(config['sessions']):
 expected={config['side']} if config.get('side') else set(config.get('acquisition_sides',config['sides']))
 if prior:
  existing=json.load(open(prior))['sessions']
  if all(any(s['pair']==pair and s['side']==side for s in existing) for side in expected):continue
 c=dict(config,pair=pair)
 if prior:c['resume_report']=prior
 cfg=k/f'{label}-{pair}.json';cfg.write_text(json.dumps(c,indent=2));out=k/f'{label}-{pair}'
 if out.exists():raise RuntimeError('will not overwrite '+str(out))
 os.utime(base/'targets/313-session-latency',None)
 print('queued',label,pair,flush=True)
 with (k/f'{label}-{pair}.log').open('wb') as log:
  command=(['python3',str(k/'idle-acquisition.py'),str(cfg),str(out)] if config.get('stress_only_when_queue_empty') else ['flock',str(base/'bench.lock'),'flock','-x','-w','5',str(base/'gpu.lock'),'timeout','--signal=TERM','--kill-after=5s','895s','python3',str(k/'lease.py'),str(cfg),str(out)])
  code=subprocess.run(command,env=env,stdout=log,stderr=log).returncode
 if not (out/'report.json').exists():
  print('acquisition has no completed report; retained config/log, exit',code,flush=True)
  sys.exit(75 if code in (1,124,143) else code or 1)
 report=json.load(open(out/'report.json'))
 if report.get('failure') or report.get('guard',{}).get('contended') is not False:
  raise RuntimeError(f'{label} {pair} failed: '+str(report.get('failure',code)))
 if not all(any(s['pair']==pair and s['side']==side for s in report['sessions']) for side in expected):raise RuntimeError('missing completed session')
 prior=str(out/'report.json');(k/f'{label}-latest.txt').write_text(prior)
 print('finished',label,pair,'sessions',len(report['sessions']),flush=True)
print('COMPLETE',label,prior,flush=True)
