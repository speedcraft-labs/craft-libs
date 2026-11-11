"""Read-only status for the two independent collectors and final heavy comparison."""
import json,os,re,subprocess,time
from pathlib import Path
r=Path(__file__).parent.parent;state=json.loads((r/'CURRENT-STATE.json').read_text());names=state.get('status_campaign_names',('aa-import-1259-fixed','real-50-descriptive','real-import-1259'));errors=[];phases=[]
try:locks=json.loads(subprocess.check_output(['sudo','-n','lslocks','--json','--output','PID,MODE,PATH'],text=True))['locks']
except (OSError,subprocess.SubprocessError):locks=[]
for name in names:
 cfg=r/(name+'-config.json')
 if not cfg.exists():continue
 log=r/(name+'-campaign.log');text=log.read_text() if log.exists() else ''
 if 'Traceback' in text:errors.append(str(log))
 config=json.loads(cfg.read_text());seed_pairs=0
 if config.get('resume_report'):
  prior=json.loads(Path(config['resume_report']).read_text());seed_pairs=sum(all(any(s['pair']==pair and s['side']==side for s in prior['sessions']) for side in config['sides']) for pair in range(config['sessions']))
 count=seed_pairs+len(re.findall(r'"status": "(?:accepted|descriptive complete)"',text));target=json.loads(cfg.read_text())['sessions'];controller=None
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   args=(proc/'cmdline').read_bytes().split(b'\0')
   if len(args)>3 and args[1] in [str(r/'operators/campaign-v2.py').encode(),str(r/'operators/campaign-descriptive.py').encode()] and args[3].decode()==name:controller=int(proc.name);break
  except OSError:pass
 descendants=set();todo=[controller] if controller else []
 while todo:
  pid=todo.pop()
  try:children=list(map(int,Path(f'/proc/{pid}/task/{pid}/children').read_text().split()))
  except OSError:children=[]
  for child in children:
   if child not in descendants:descendants.add(child);todo.append(child)
 own=[x for x in locks if x['pid'] in descendants];admission='complete' if count==target else 'between acquisitions'
 if any(x.get('path','').endswith('/bench.lock') and x['mode'].endswith('*') for x in own):admission='bench queue'
 elif any(x.get('path','').endswith('/gpu.lock') and x['mode'].endswith('*') for x in own):admission='GPU tests queue'
 elif any(x.get('path','').endswith('/gpu.lock') and x['mode']=='WRITE' for x in own):admission='measuring'
 if admission=='measuring':
  for pid in descendants:
   try:
    args=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    if len(args)>3 and args[1]==str(r/'operators/lease.py').encode():
     acquisition=json.loads(Path(args[2].decode()).read_text())
     admission+=' '+('upstream sample' if (acquisition.get('side')=='upstream' or acquisition.get('acquisition_sides')==['upstream']) else 'primary pair')+' '+str(acquisition['pair']+1)
     attempt=re.search(r'-attempt(\d+)\.json$',args[2].decode())
     if attempt and int(attempt.group(1))>0:admission+=' attempt '+str(int(attempt.group(1))+1)
     break
   except (OSError,ValueError):pass
 phases.append(dict(name=name,complete=count,target=target,admission=admission))
state=json.loads((r/'CURRENT-STATE.json').read_text());p=r/state.get('pipeline_log','post-recovery-v2.log')
if p.exists() and 'Traceback' in p.read_text():errors.append(str(p))
fs=os.statvfs('/jobs');print(json.dumps(dict(utc=time.strftime('%H:%M:%SZ',time.gmtime()),phases=phases,errors=errors,disk_free_gib=round(fs.f_bavail*fs.f_frsize/1024**3,1),all_phases_complete=(r/'ALL-PHASES.json').exists())))
