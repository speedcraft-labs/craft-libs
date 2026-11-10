"""Read-only lease observation. Process age is not acquisition duration."""
import json,subprocess,time
from pathlib import Path
k=Path(__file__).parent;p=k/'bench-holder-observation.json';now=time.time()
locks=json.loads(subprocess.check_output(['sudo','-n','lslocks','--json','--output','PID,PATH,BLOCKER,MODE'],text=True))['locks']
old=json.load(open(p)) if p.exists() else {};previous=old.get('resources',{'bench.lock':old.get('holders',{})});current={};observations=[]
for resource in ['bench.lock','gpu.lock']:
 xs=[x for x in locks if x.get('path')=='/jobs/work/speedcraft-labs/'+resource]
 ids=sorted({x['pid'] for x in xs if not x.get('blocker')});holders={str(pid):previous.get(resource,{}).get(str(pid),now) for pid in ids};current[resource]=holders
 for pid in ids:
  try:
   argv=Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0');argv=[x.decode(errors='replace') for x in argv if x]
   paths=[x for x in argv if x.endswith(('.py','.sh')) or '/targets/' in x]
   command=' '.join(paths) if paths else Path('/proc',str(pid),'comm').read_text().strip()
  except FileNotFoundError:command='exited during snapshot'
  elapsed=now-holders[str(pid)];observations.append(dict(resource=resource,pid=pid,observed_continuous_seconds=elapsed,command=command))
  print(resource,'holder',pid,'observed',round(elapsed),'s;',sum(bool(x.get('blocker')) for x in xs),'waiters;',command)
  if elapsed>1800:print('OVER-30-MINUTE HOLDER:',resource,pid,command)
with (k/'bench-holder-observations.jsonl').open('a') as f:f.write(json.dumps(dict(wall=now,holders=observations))+'\n')
p.write_text(json.dumps(dict(wall=now,resources=current),indent=2)+'\n')
