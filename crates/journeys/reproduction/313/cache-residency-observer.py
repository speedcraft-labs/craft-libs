"""Read-only fincore observations. Never fault, warm, or evict file pages."""
import json,os,subprocess,time
from pathlib import Path
k=Path(__file__).parent;corpus=Path('/jobs/work/speedcraft-labs/hyper/corpus/lightcraft-session-tiers-2026');page_size=os.sysconf('SC_PAGE_SIZE')
while not (k/'gpu-clock-observer.stop').exists():
 started=time.monotonic_ns();rows=[]
 for tier in ['typical-50','import-1262']:
  files=sorted(str(p) for p in (corpus/tier).iterdir() if p.is_file() and not p.name.startswith('.'))
  result=subprocess.run(['fincore','--json','--bytes','--output','PAGES,SIZE,FILE',*files],text=True,capture_output=True)
  if result.returncode:
   rows.append(dict(tier=tier,error=result.stderr,exit_code=result.returncode));continue
  data=json.loads(result.stdout)['fincore'];total=sum((int(x['size'])+page_size-1)//page_size for x in data);resident=sum(int(x['pages']) for x in data)
  rows.append(dict(tier=tier,files=len(files),size_bytes=sum(int(x['size']) for x in data),resident_pages=resident,total_pages=total,resident_pct=100*resident/total,files_not_fully_resident=sum(int(x['pages'])<(int(x['size'])+page_size-1)//page_size for x in data)))
 record=dict(monotonic_ns=started,end_ns=time.monotonic_ns(),wall_ns=time.time_ns(),read_only=True,tiers=rows)
 with (k/'cache-residency-observer.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
 print(json.dumps(record),flush=True)
 for _ in range(60):
  if (k/'gpu-clock-observer.stop').exists():break
  time.sleep(1)
