"""Supplemental read-only VM scheduling observations; never filters timing samples."""
import json,os,time
from pathlib import Path
root=Path(__file__).parent.parent
(root/'scheduling-observer.pid').write_text(str(os.getpid())+'\n')
previous=None;deadline=time.monotonic()+43200
with (root/'scheduling-observations.jsonl').open('a',buffering=1) as log:
 while time.monotonic()<deadline and not (root/'scheduling-observer.stop').exists():
  rows={}
  for line in Path('/proc/stat').read_text().splitlines():
   parts=line.split()
   if parts and parts[0] in {f'cpu{i}' for i in range(22,28)}:rows[parts[0]]=list(map(int,parts[1:9]))
  record={'monotonic_ns':time.perf_counter_ns(),'utc_ns':time.time_ns(),'cpu_ticks':rows}
  if previous:
   total=sum(sum(rows[c])-sum(previous[c]) for c in rows)
   steal=sum(rows[c][7]-previous[c][7] for c in rows)
   record['reserved_cpu_steal_pct']=steal/total*100 if total else None
  record['pressure']={name:Path('/proc/pressure',name).read_text().strip() for name in ('cpu','io','memory')}
  log.write(json.dumps(record)+'\n');previous=rows;time.sleep(2)
