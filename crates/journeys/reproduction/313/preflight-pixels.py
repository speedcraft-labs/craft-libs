"""Untimed app-output check, not a benchmark. Run under shared GPU test lock."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
k=Path(__file__).parent;root=Path('/jobs/work/speedcraft-labs');sys.path.insert(0,str(root/'wt/313-session-latency/crates/journeys/scripts'))
import lightcraft_real_app as driver
out=k/'pixel-preflight-v2';out.mkdir(exist_ok=False)
display=':128';lock=Path('/tmp/.X128-lock');sock=Path('/tmp/.X11-unix/X128')
if lock.exists() or sock.exists():raise RuntimeError('private test display already owned; refuse to reuse')
def interrupted(sig,frame):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,interrupted)
conf=k/'xorg.conf';xorg=None;checks=[];records=[]
try:
 with (out/'xorg.stdout').open('wb') as log:
  xorg=subprocess.Popen(['sudo','-n','/usr/lib/xorg/Xorg',display,'-config',str(conf),'-noreset','-nolisten','tcp','-ac','-novtswitch','-sharevts','-logfile',str(out/'xorg.log')],stdout=log,stderr=log)
 deadline=time.monotonic()+20
 while not sock.exists():
  if xorg.poll() is not None:raise RuntimeError('test X server failed')
  if time.monotonic()>deadline:raise TimeoutError('test X server startup')
  time.sleep(.05)
 os.environ['DISPLAY']=display;os.environ['WGPU_BACKEND']='vulkan'
 config=json.load(open(k/'comparison-v6-template.json'))
 for tier in ['typical-50','import-1262']:
  sources=sorted((root/'hyper/corpus/lightcraft-session-tiers-2026'/tier).iterdir());photo=sources[0]
  for side in ['point','main','upstream']:
   directory=out/(tier+'-'+side);directory.mkdir();binary=Path(config['revisions'][side]['binary']);process=None;control=None
   try:
    process,control=driver.spawn(binary,directory/'library',directory/'profile',photo,log_path=directory/'app.log')
    control.call('ui.set',{'settings':{'previewLimit':0,'lensDatabase':'declined'}});control.call('ui.dialog.cancel');item=driver.wait_for_photo(control,process)
    driver.session_execute(control,'library.select',{'ids':[item['id']]});driver.session_execute(control,'view.detail');driver.session_detail(control,item['id'])
    driver.session_execute(control,'develop.set',{'values':{'light.exposure':.7}})
    driver.session_detail(control,item['id']);driver.render_preview(control,directory/'oracle.png',item['id'])
    for fmt in ['jpeg','png']:
     destination=directory/('export.jpg' if fmt=='jpeg' else 'export.png')
     driver.session_execute(control,'app.export',{'path':str(destination),'ids':[item['id']],'format':fmt,'longEdge':2048,'quality':90,'colorSpace':'srgb','bitDepth':8,'background':True})
     driver.session_wait(control,lambda s:not (s.get('export') or {}).get('running'))
     if not destination.is_file():raise RuntimeError('missing export')
    records.append(dict(tier=tier,side=side,input=str(photo),input_sha256=driver.file_digest(photo),binary_sha256=driver.file_digest(binary),directory=str(directory),files={p.name:driver.file_digest(p) for p in directory.iterdir() if p.suffix in ('.png','.jpg')}))
   finally:
    if process is not None:driver.stop(process,control)
    if control is not None:control.stream.close()
  for side in ['main','upstream']:
   for file in ['oracle.png','export.jpg','export.png']:
    old,new=(Image.open(out/(tier+'-'+s)/file).convert('RGBA') for s in ['point',side])
    assert old.size==new.size
    diff=ImageChops.difference(old,new);checks.append(dict(tier=tier,side=side,file=file,maximum=[hi for lo,hi in diff.getextrema()],mean=ImageStat.Stat(diff).mean))
 result=dict(correctness_only=True,records=records,checks=checks,exact=all(max(x['maximum'])==0 for x in checks))
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
 if result['exact']:
  for record in records:
   for name in record['files']:(Path(record['directory'])/name).unlink()
finally:
 if lock.exists():
  pid=int(lock.read_text().strip());args=subprocess.check_output(['ps','-p',str(pid),'-o','args='],text=True)
  if 'Xorg '+display+' ' in args and str(conf) in args:subprocess.run(['sudo','-n','kill','-TERM',str(pid)],check=True)
 if xorg is not None:xorg.wait(timeout=10)
