import json,os,signal,subprocess,sys,time
from pathlib import Path
from gpu_condition import mode,set_mode,restore_display
k=Path(__file__).parent;out=Path(sys.argv[2]);config=json.load(open(sys.argv[1]));display=':129';lock=Path('/tmp/.X129-lock');conf=k/'xorg.conf'
if lock.exists() or Path('/tmp/.X11-unix/X129').exists():raise RuntimeError('private display already in use; never reuse or kill another server')
log=out.with_suffix('.xorg.log');stdout=out.with_suffix('.xorg.stdout')
def interrupted(sig,frame):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,interrupted)
with stdout.open('wb') as stream:
 process=subprocess.Popen(['sudo','-n','/usr/lib/xorg/Xorg',display,'-config',str(conf),'-noreset','-nolisten','tcp','-ac','-novtswitch','-sharevts','-logfile',str(log)],stdout=stream,stderr=stream)
try:
 deadline=time.monotonic()+20
 while not Path('/tmp/.X11-unix/X129').exists():
  if process.poll() is not None:raise RuntimeError('Xorg exited; see '+str(log))
  if time.monotonic()>deadline:raise TimeoutError('Xorg startup')
  time.sleep(.05)
 pid=int(lock.read_text().strip())
 info=dict(display=display,xorg_pid=pid,cpus=sorted(os.sched_getaffinity(pid)),configuration=conf.read_text())
 out.with_suffix('.display.json').write_text(json.dumps(info,indent=2))
 if set(info['cpus'])!=set(range(22,28)):raise RuntimeError('Xorg not on reserved benchmark CPUs')
 if config.get('gpu_state'):
  info['power_mizer_original']=mode(display)
  info['power_mizer_requested']=1
  out.with_suffix('.display.json').write_text(json.dumps(info,indent=2))
  set_mode(display,1)
  info['power_mizer_active']=mode(display)
  out.with_suffix('.display.json').write_text(json.dumps(info,indent=2))
 env=dict(os.environ,DISPLAY=display)
 if config.get('_lease_selftest_display'):status=subprocess.run(['sleep','300']).returncode
 else:status=subprocess.run(['/jobs/work/speedcraft-labs/targets/313-session-latency/debug/craft-journeys','session','--config',sys.argv[1],'--out',str(out)],env=env).returncode
finally:
 try:
  metadata=out.with_suffix('.display.json')
  if metadata.exists():restore_display(metadata)
 finally:
  if lock.exists():
   pid=int(lock.read_text().strip())
   command=subprocess.check_output(['ps','-p',str(pid),'-o','args='],text=True)
   if f'Xorg {display} ' in command and str(conf) in command:
    subprocess.run(['sudo','-n','kill','-TERM',str(pid)],check=True)
  process.wait(timeout=5)
sys.exit(status)
