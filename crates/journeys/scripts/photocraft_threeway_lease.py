# Outside bench.slice, under bench.lock. Reuse a caller-owned GPU lock or acquire it once.
import fcntl,json,os,re,signal,subprocess,sys,time
from contextlib import contextmanager
from pathlib import Path
OPERATORS=Path('/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway/operators')
sys.path.insert(0,str(OPERATORS))
from gpu_condition import ForeignGpuBusy,graphics_clock,restore_owned_displays
k=OPERATORS;cfg=Path(sys.argv[1]);out=Path(sys.argv[2]);config=json.load(open(cfg))
GPU_LOCK='/jobs/work/speedcraft-labs/gpu.lock'
BENCH_GUARD='/jobs/work/speedcraft-labs/bench.lock.guard.flock'
BENCH_HELD='CRAFT_JOURNEYS_BENCH_LOCK_HELD'
GPU_HELD='CRAFT_JOURNEYS_GPU_LOCK_HELD'

@contextmanager
def gpu_lock_scope():
 if os.environ.get(BENCH_HELD)!='1':
  raise RuntimeError('lease.py must run under bench.lock')
 if os.environ.get(GPU_HELD)=='1':
  print('GPU lock inherited from caller; not reacquiring',flush=True)
  yield
  return
 fd=os.open(GPU_LOCK,os.O_CREAT|os.O_RDWR,0o666)
 try:
  fcntl.flock(fd,fcntl.LOCK_EX)
  os.environ[GPU_HELD]='1'
  print('GPU lock acquired by lease.py',flush=True)
  yield
 finally:
  os.environ.pop(GPU_HELD,None)
  fcntl.flock(fd,fcntl.LOCK_UN)
  os.close(fd)
if (k.parent/'RETIRE-LEGACY-CONFIRMATION').exists() and out.name.startswith('real-import-1259-cont2-'):
 out.with_suffix('.retired-before-launch.json').write_text(json.dumps(dict(reason='legacy confirmation protocol retired at an acquisition boundary; all data preserved',config=str(cfg),ns=time.monotonic_ns())))
 print('Legacy confirmation collector retired at acquisition boundary; no app or clocks started',flush=True)
 sys.exit(78)
if config.get('stress_only_when_queue_empty'):
 locks=json.loads(subprocess.check_output(['sudo','-n','lslocks','--json','--output','PID,COMMAND,MODE,PATH'],text=True))['locks']
 waiters=[row for row in locks if row.get('path')=='/jobs/work/speedcraft-labs/bench.lock' and row.get('mode','').endswith('*')]
 if waiters:
  event=dict(reason='stress tier deferred: benchmark queue nonempty',waiters=waiters,ns=time.monotonic_ns())
  with out.with_suffix('.queue-admissions.jsonl').open('a') as log:log.write(json.dumps(event)+'\n')
  sys.exit(77)
def run_lease():
 started=time.monotonic();limit=840
 runner = 'acquire-pair.py' if len(config.get('sides', [])) == 2 else 'acquire-threeway.py'
 command=['/jobs/work/speedcraft-labs/scripts/bench-run','python3',str(k/runner),str(cfg),str(out)]
 probe=json.load(open(cfg)).get('clock_probe',False)
 if probe:
  limit=180
  command=['/jobs/work/speedcraft-labs/scripts/bench-run','python3',str(k/'clock-probe.py')]
 if os.environ.get('SESSION_LEASE_SELF_TEST')=='1' and config.get('gpu_state'):
  limit=10
 elif os.environ.get('SESSION_LEASE_SELF_TEST')=='1':
  limit=2
  command=['sudo','-n','systemd-run','--quiet','--wait','--pipe','--collect','--unit=run-313b-lease-selftest.service','--uid=agent','--gid=agent','--property=AllowedCPUs=0-21','python3',str(k/'lease-selftest-worker.py'),str(cfg),str(out)]
 child_env=dict(os.environ,SESSION_LEASE_DEADLINE_NS=str(time.monotonic_ns()+int(limit*1e9)),BENCH_LOCK_FILE=BENCH_GUARD)
 child_env[BENCH_HELD]='1'
 child_env[GPU_HELD]='1'
 if probe:child_env.update(SESSION_PROBE_CONFIG=str(cfg),SESSION_PROBE_OUTPUT=str(out))
 process=subprocess.Popen(command,start_new_session=True,env=child_env)
 class Cancelled(Exception):pass
 def cancelled(signum,frame):raise Cancelled()
 signal.signal(signal.SIGTERM,cancelled)
 expired=False
 try:
  code=process.wait(timeout=limit)
 except (subprocess.TimeoutExpired,KeyboardInterrupt,Cancelled):
  signal.signal(signal.SIGTERM,signal.SIG_IGN)
  signal.signal(signal.SIGINT,signal.SIG_IGN)
  expired=True;code=124
  unitfile=out.with_suffix('.unit.json');unit=None
  if unitfile.exists():
   info=json.load(open(unitfile));unit=info['unit']
   if info['config']!=str(cfg) or info['out']!=str(out) or not re.fullmatch(r'run-[A-Za-z0-9_-]+\.service',unit):
    raise RuntimeError('refuse to stop an unrecognized unit')
   restore_owned_displays(out)
   subprocess.run(['sudo','-n','systemctl','kill','--signal=TERM',unit],check=False,timeout=5)
   time.sleep(45 if probe else 2)
   subprocess.run(['sudo','-n','systemctl','kill','--signal=KILL',unit],check=False,timeout=5)
  try:os.killpg(process.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:process.wait(timeout=5)
  except subprocess.TimeoutExpired:
   try:os.killpg(process.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   process.wait(timeout=5)
  # A SIGKILLed owned Xorg may leave its socket. Verify identity and death first.
  for metadata in out.glob('*.display.json') if out.exists() else []:
   info=json.load(open(metadata));pid=info['xorg_pid'];lock=Path('/tmp/.X130-lock')
   if lock.exists() and int(lock.read_text().strip())==pid and not Path('/proc',str(pid)).exists():
    subprocess.run(['sudo','-n','rm','-f','--','/tmp/.X130-lock','/tmp/.X11-unix/X130'],check=True)
  out.with_suffix('.lease-expired.json').write_text(json.dumps(dict(unit=unit,limit_seconds=limit,elapsed_seconds=time.monotonic()-started,status='lease expired; completed guarded sides retained, incomplete sides rejected'),indent=2))
 return code

def early_cancel(sig,frame):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,early_cancel)
try:
 with gpu_lock_scope():
  with graphics_clock(config,out):code=run_lease()
except ForeignGpuBusy:
 print("Foreign GPU user before admission; no app/clocks started; release both locks and retry",flush=True)
 code=77
sys.exit(code)
