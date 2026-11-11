"""Passive CPU/run-queue/page-fault diagnostics; no latency value filters."""
import json,os,time
from pathlib import Path
root=Path(__file__).parent.parent
os.sched_setaffinity(0,set(range(22)))
(root/'process-observer.pid').write_text(str(os.getpid())+'\n')
end=time.monotonic()+86400
with (root/'process-scheduling-observations.jsonl').open('a',buffering=1) as log:
 while time.monotonic()<end and not (root/'process-observer.stop').exists():
  for proc in Path('/proc').iterdir():
   if not proc.name.isdigit():continue
   try:
    if not (proc/'comm').read_text().startswith('lightcraft-r3-'):continue
    executable=(proc/'exe').resolve()
    if executable.parent!=Path('/jobs/work/speedcraft-labs/tmp/313b-binaries'):continue
    threads=[]
    for task in (proc/'task').iterdir():
     try:
      sched=list(map(int,(task/'schedstat').read_text().split()));stat=(task/'stat').read_text().rsplit(')',1)[1].split()
      threads.append(dict(tid=int(task.name),name=(task/'comm').read_text().strip(),cpu_ns=sched[0],runqueue_wait_ns=sched[1],timeslices=sched[2],state=stat[0],minor_faults=int(stat[7]),major_faults=int(stat[9])))
     except (OSError,ValueError,IndexError):pass
    record=dict(monotonic_ns=time.perf_counter_ns(),utc_ns=time.time_ns(),pid=int(proc.name),binary=executable.name,threads=threads)
    log.write(json.dumps(record)+'\n')
   except (OSError,ValueError):pass
  time.sleep(2)
