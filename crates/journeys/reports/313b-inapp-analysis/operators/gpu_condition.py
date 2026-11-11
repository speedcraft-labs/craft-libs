"""Scoped NVIDIA settings; caller already holds bench then exclusive GPU lock."""
import contextlib,json,signal,subprocess,time
from pathlib import Path
class ForeignGpuBusy(RuntimeError):
 pass

def command(args):
 p=subprocess.run(args,text=True,capture_output=True,timeout=5)
 if p.returncode or 'not supported' in (p.stdout+p.stderr).lower():
  raise RuntimeError(f'{args}: {p.returncode}: {p.stdout} {p.stderr}')
 return p.stdout
def snapshot():
 return command(['nvidia-smi','--id=0','--query-gpu=pstate,clocks.gr,clocks.mem,power.draw','--format=csv,noheader,nounits']).strip()
def mode(display):
 return int(command(['nvidia-settings','--ctrl-display='+display,'--query','[gpu:0]/GPUPowerMizerMode','--terse']).strip())
def set_mode(display,value):
 command(['nvidia-settings','--ctrl-display='+display,'--assign',f'[gpu:0]/GPUPowerMizerMode={value}'])
 if mode(display)!=value:raise RuntimeError('PowerMizer assignment did not take effect')
def restore_display(metadata):
 info=json.loads(metadata.read_text())
 if 'power_mizer_original' not in info:return
 lock=Path('/tmp/.X130-lock');pid=info['xorg_pid']
 if not lock.exists() or int(lock.read_text().strip())!=pid:return
 cmd=Path('/proc',str(pid),'cmdline').read_bytes().replace(b'\0',b' ').decode()
 if 'Xorg :130 ' not in cmd or str(Path(__file__).parent/'xorg.conf') not in cmd:
  raise RuntimeError('refuse to change another display')
 set_mode(info['display'],info['power_mizer_original'])
 info.update(power_mizer_restored=True,power_mizer_restored_ns=time.monotonic_ns())
 metadata.write_text(json.dumps(info,indent=2))
def restore_owned_displays(out):
 for metadata in out.glob('*.display.json') if out.exists() else []:
  try:restore_display(metadata)
  except Exception as error:
   metadata.with_suffix('.restore-failure.json').write_text(json.dumps({'error':str(error)}))
@contextlib.contextmanager
def graphics_clock(config,out):
 state=config.get('gpu_state')
 if not state:
  yield;return
 foreign=command(['nvidia-smi','--query-compute-apps=pid,name','--format=csv,noheader']).strip()
 if foreign:
  event={'rejected_foreign_processes':foreign,'monotonic_ns':time.monotonic_ns()}
  out.with_suffix('.gpu-state-admission.json').write_text(json.dumps(event))
  with out.with_suffix('.gpu-state-admissions.jsonl').open('a') as admission_log:admission_log.write(json.dumps(event)+'\n')
  raise ForeignGpuBusy('foreign GPU process before applying clock condition')
 audit={'before':snapshot(),'requested':state,'start_ns':time.monotonic_ns()}
 try:
  mhz=int(state['graphics_mhz'])
  audit['set_output']=command(['sudo','-n','nvidia-smi','--id=0',f'--lock-gpu-clocks={mhz},{mhz}'])
  audit['after_set']=snapshot()
  if abs(int(audit['after_set'].split(',')[1])-mhz)>15:raise RuntimeError('graphics clock lock did not take effect')
  yield
 finally:
  signal.signal(signal.SIGTERM,signal.SIG_IGN)
  signal.signal(signal.SIGINT,signal.SIG_IGN)
  restore_owned_displays(out)
  audit['reset_output']=command(['sudo','-n','nvidia-smi','--id=0','--reset-gpu-clocks'])
  audit.update(after_reset=snapshot(),end_ns=time.monotonic_ns())
  out.with_suffix('.gpu-condition.json').write_text(json.dumps(audit,indent=2))
