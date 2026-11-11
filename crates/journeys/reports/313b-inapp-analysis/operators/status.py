import json,os,time,subprocess
from pathlib import Path
root=Path(__file__).parent.parent
state=json.loads((root/'CURRENT-STATE.json').read_text());phase=state.get('pipeline_phase',state.get('active_campaign','aa-inapp-r4'))
errors=[]
for path in [root/(phase+'-campaign.log'),root/state.get('pipeline_log','post-r4-controller.log')]:
 if path.exists() and 'Traceback' in path.read_text():errors.append(str(path))
logs=list(root.glob(phase+'-*-attempt*.log'))
last=''
if logs:
 p=max(logs,key=lambda p:p.stat().st_mtime);lines=p.read_text().splitlines();last=next((x for x in reversed(lines) if x.strip()),'')
if last.lstrip().startswith('|'):last='side completed; serializing output checks and cumulative report'
if last.startswith('Stress tier:') and p.with_suffix('.gpu-state-admission.json').exists():last='Foreign GPU user before admission; both locks released, no app or clocks started'
# Distinguish the current OS lock queue from a stale admission log line.
admission='between acquisitions'
try:
 controller=None
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   args=(proc/'cmdline').read_bytes().split(b'\0')
   if len(args)>3 and args[1]==str(root/'operators/campaign-v2.py').encode() and args[3].decode()==phase:controller=int(proc.name);break
  except OSError:pass
 descendants=set();todo=[controller] if controller else []
 while todo:
  parent=todo.pop()
  try:children=list(map(int,Path(f'/proc/{parent}/task/{parent}/children').read_text().split()))
  except OSError:children=[]
  for pid in children:
   if pid not in descendants:descendants.add(pid);todo.append(pid)
 locks=json.loads(subprocess.check_output(['sudo','-n','lslocks','--json','--output','PID,MODE,PATH'],text=True))['locks']
 own=[row for row in locks if row['pid'] in descendants]
 if any(row.get('path','').endswith('/bench.lock') and row['mode'].endswith('*') for row in own):admission='waiting for bench.lock'
 elif any(row.get('path','').endswith('/gpu.lock') and row['mode'].endswith('*') for row in own):admission='waiting for shared GPU tests to release gpu.lock'
 elif any(row.get('path','').endswith('/gpu.lock') and row['mode']=='WRITE' for row in own):admission='bounded acquisition running'
except (OSError,ValueError,subprocess.SubprocessError):admission='lock snapshot unavailable'
free=os.statvfs('/jobs');print(json.dumps(dict(utc=time.strftime('%H:%M:%SZ',time.gmtime()),phase=phase,status=state.get('status'),admission=admission,latest=last[-250:],errors=errors,all_phases_complete=(root/'ALL-PHASES.json').exists(),disk_free_gib=round(free.f_bavail*free.f_frsize/1024**3,1))))
