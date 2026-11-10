import json,subprocess,time,os,signal
from pathlib import Path
k=Path(__file__).parent;result={'purpose':'configuration capability diagnostic only; no latency samples','phases':[]};graphics=False;memory=False;server=None;original_mode=None;server_pid=None
if os.environ.get('SESSION_PROBE_OUTPUT'):
 Path(os.environ['SESSION_PROBE_OUTPUT']).with_suffix('.unit.json').write_text(json.dumps(dict(unit=Path('/proc/self/cgroup').read_text().strip().split('/')[-1],config=os.environ['SESSION_PROBE_CONFIG'],out=os.environ['SESSION_PROBE_OUTPUT'])))
def cancel(sig,frame):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,cancel)
def run(args):
 try:
  p=subprocess.run(args,text=True,capture_output=True,timeout=5)
  r=dict(command=args,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,ns=time.monotonic_ns())
 except subprocess.TimeoutExpired:
  r=dict(command=args,exit_code=124,stdout='',stderr='command timed out after five seconds',ns=time.monotonic_ns())
 result['phases'].append(r);(k/'clock-probe-progress.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(r),flush=True);return r['exit_code']
try:
 run(['nvidia-smi','-q','-d','CLOCK,PERFORMANCE'])
 graphics=run(['sudo','-n','nvidia-smi','-i','0','--lock-gpu-clocks=1350,1350'])==0
 if graphics:
  memory=run(['sudo','-n','nvidia-smi','-i','0','--lock-memory-clocks=7000,7000'])==0
  memory=memory and 'not supported' not in result['phases'][-1]['stdout'].lower()
 time.sleep(2)
 run(['nvidia-smi','--query-gpu=pstate,clocks.gr,clocks.mem,power.draw','--format=csv'])
 result.update(graphics_lock_supported=graphics,memory_lock_supported=memory)
 if graphics and not memory:
  lock=Path('/tmp/.X129-lock');socket=Path('/tmp/.X11-unix/X129')
  if lock.exists() or socket.exists():raise RuntimeError('private display occupied; never reuse it')
  with (k/'clock-probe-xorg.stdout').open('wb') as stream:
   server=subprocess.Popen(['sudo','-n','/usr/lib/xorg/Xorg',':129','-config',str(k/'xorg.conf'),'-noreset','-nolisten','tcp','-ac','-novtswitch','-sharevts','-logfile',str(k/'clock-probe-xorg.log')],stdout=stream,stderr=stream)
  deadline=time.monotonic()+20
  while not socket.exists():
   if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError('probe Xorg did not start')
   time.sleep(.05)
  server_pid=int(lock.read_text().strip())
  result['probe_display']=dict(pid=server_pid,cpus=sorted(os.sched_getaffinity(server_pid)))
  query=['nvidia-settings','--ctrl-display=:129','--query','[gpu:0]/GPUPowerMizerMode','--terse']
  if run(query)==0:
   original_mode=int(result['phases'][-1]['stdout'].strip())
   result['original_power_mizer_mode']=original_mode
   run(['nvidia-settings','--ctrl-display=:129','--assign','[gpu:0]/GPUPowerMizerMode=1'])
   run(query);result['prefer_max_supported']=result['phases'][-1]['stdout'].strip()=='1'
   time.sleep(2)
   run(['nvidia-smi','--query-gpu=pstate,clocks.gr,clocks.mem,power.draw','--format=csv'])
finally:
 run(['sudo','-n','nvidia-smi','-i','0','--reset-gpu-clocks'])
 run(['sudo','-n','nvidia-smi','-i','0','--reset-memory-clocks'])
 if original_mode is not None:
  run(['nvidia-settings','--ctrl-display=:129','--assign',f'[gpu:0]/GPUPowerMizerMode={original_mode}'])
 if server is not None:
  if server_pid is None and Path('/tmp/.X129-lock').exists():server_pid=int(Path('/tmp/.X129-lock').read_text().strip())
  if server_pid is not None:
   command=subprocess.run(['ps','-p',str(server_pid),'-o','args='],capture_output=True,text=True,timeout=5).stdout
   if 'Xorg :129 ' in command and str(k/'xorg.conf') in command:run(['sudo','-n','kill','-TERM',str(server_pid)])
  try:server.wait(timeout=5)
  except subprocess.TimeoutExpired:
   if server_pid is not None:run(['sudo','-n','kill','-KILL',str(server_pid)])
 run(['nvidia-smi','-q','-d','CLOCK,PERFORMANCE'])
 (k/'clock-probe.json').write_text(json.dumps(result,indent=2)+'\n')
