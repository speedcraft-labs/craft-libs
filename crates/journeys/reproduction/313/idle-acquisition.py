"""Stress work never joins the bench queue; admit only an empty queue."""
import fcntl,json,os,signal,subprocess,sys,time
from pathlib import Path
k=Path(__file__).parent;root=Path('/jobs/work/speedcraft-labs')
cfg,out=map(Path,sys.argv[1:3]);cancelled=False
def cancel(sig,frame):
 global cancelled
 cancelled=True
signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
attempts=0
while not cancelled:
 attempts+=1
 bench=(root/'bench.lock').open('a');gpu=(root/'gpu.lock').open('a')
 try:
  try:fcntl.flock(bench,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:continue
  locks=json.loads(subprocess.check_output(['sudo','-n','lslocks','--json','--output','PID,PATH,BLOCKER'],text=True))['locks']
  waiters=[x for x in locks if x.get('path')==str(root/'bench.lock') and x.get('blocker')]
  if waiters:continue
  try:fcntl.flock(gpu,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:continue
  foreign=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,name','--format=csv,noheader'],text=True).strip()
  if foreign:continue
  out.with_suffix('.stress-admission.json').write_text(json.dumps(dict(wall_ns=time.time_ns(),pid=os.getpid(),bench_waiters=waiters,gpu_processes=foreign,attempts=attempts),indent=2))
  print('stress admitted with empty queue',out,flush=True)
  process=subprocess.Popen(['python3',str(k/'lease.py'),str(cfg),str(out)])
  while process.poll() is None:
   if cancelled:process.terminate()
   try:process.wait(timeout=1)
   except subprocess.TimeoutExpired:pass
  sys.exit(process.returncode)
 finally:
  gpu.close();bench.close()
  if not cancelled:time.sleep(5)
sys.exit(143)
