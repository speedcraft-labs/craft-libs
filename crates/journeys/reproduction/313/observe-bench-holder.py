"""Read-only lock observation. Elapsed process lifetime is NOT lease duration."""
import json,subprocess,time
from pathlib import Path
k=Path(__file__).parent;p=k/'bench-holder-observation.json';now=time.time()
locks=json.loads(subprocess.check_output(['sudo','-n','lslocks','--json','--output','PID,PATH,BLOCKER'],text=True))['locks']
xs=[x for x in locks if x.get('path')=='/jobs/work/speedcraft-labs/bench.lock']
ids=sorted({x['pid'] for x in xs if not x.get('blocker')})
old=json.load(open(p)) if p.exists() else {};holders={str(pid):old.get('holders',{}).get(str(pid),now) for pid in ids}
observations=[]
for pid in ids:
 try:args=subprocess.check_output(['ps','-p',str(pid),'-o','args='],text=True).strip()
 except subprocess.CalledProcessError:args='exited during snapshot'
 elapsed=now-holders[str(pid)];observations.append(dict(pid=pid,observed_continuous_seconds=elapsed,args=args))
 print('Bench holder',pid,'observed',round(elapsed),'s;',sum(bool(x.get('blocker')) for x in xs),'waiters')
 if elapsed>1800:print('OVER-30-MINUTE HOLDER:',pid,args)
with (k/'bench-holder-observations.jsonl').open('a') as f:f.write(json.dumps(dict(wall=now,holders=observations,waiters=sum(bool(x.get('blocker')) for x in xs)))+'\n')
p.write_text(json.dumps(dict(wall=now,holders=holders),indent=2)+'\n')
