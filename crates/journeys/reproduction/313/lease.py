# Outside bench.slice, inside both locks. Restore settings and reap the owned unit.
import json,os,re,signal,subprocess,sys,time
from pathlib import Path
from gpu_condition import graphics_clock,restore_owned_displays
k=Path(__file__).parent;cfg=Path(sys.argv[1]);out=Path(sys.argv[2]);config=json.load(open(cfg))
def run_lease():
 started=time.monotonic();limit=840
 command=['/jobs/work/speedcraft-labs/scripts/bench-run','python3',str(k/'acquire-pair.py'),str(cfg),str(out)]
 probe=json.load(open(cfg)).get('clock_probe',False)
 if probe:
  limit=180
  command=['/jobs/work/speedcraft-labs/scripts/bench-run','python3',str(k/'clock-probe.py')]
 if os.environ.get('SESSION_LEASE_SELF_TEST')=='1' and config.get('gpu_state'):
  limit=10
 elif os.environ.get('SESSION_LEASE_SELF_TEST')=='1':
  limit=2
  command=['sudo','-n','systemd-run','--quiet','--wait','--pipe','--collect','--unit=run-313-lease-selftest.service','--uid=agent','--gid=agent','--property=AllowedCPUs=0-21','python3',str(k/'lease-selftest-worker.py'),str(cfg),str(out)]
 child_env=dict(os.environ,SESSION_LEASE_DEADLINE_NS=str(time.monotonic_ns()+int(limit*1e9)))
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
   info=json.load(open(metadata));pid=info['xorg_pid'];lock=Path('/tmp/.X129-lock')
   if lock.exists() and int(lock.read_text().strip())==pid and not Path('/proc',str(pid)).exists():
    subprocess.run(['sudo','-n','rm','-f','--','/tmp/.X129-lock','/tmp/.X11-unix/X129'],check=True)
  out.with_suffix('.lease-expired.json').write_text(json.dumps(dict(unit=unit,limit_seconds=limit,elapsed_seconds=time.monotonic()-started,status='lease expired; completed guarded sides retained, incomplete sides rejected'),indent=2))
 return code

def early_cancel(sig,frame):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,early_cancel)
with graphics_clock(config,out):code=run_lease()
sys.exit(code)
