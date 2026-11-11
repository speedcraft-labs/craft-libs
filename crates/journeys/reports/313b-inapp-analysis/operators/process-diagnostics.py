"""Descriptive thread run-queue measurements; never filter or adjust app timings."""
import collections,json,statistics,sys
from pathlib import Path
root=Path(__file__).parent.parent
report=json.loads(Path(sys.argv[1]).read_text())
by_pid=collections.defaultdict(list)
with (root/'process-scheduling-observations.jsonl').open() as f:
 for line in f:
  r=json.loads(line);by_pid[r['pid']].append(r)
rows=[]
for s in report['sessions']:
 totals=collections.defaultdict(lambda:dict(cpu_ns=0,runqueue_wait_ns=0,minor_faults=0,major_faults=0,threads=0))
 observations=0
 for pid in s['process_ids']:
  snapshots=[r for r in by_pid.get(pid,[]) if s['launch_ns']<=r['monotonic_ns']<=s['quit_request_ns']]
  observations+=len(snapshots)
  threads=collections.defaultdict(list)
  for r in snapshots:
   for t in r['threads']:threads[t['tid']].append(t)
  for tid,ts in threads.items():
   if len(ts)<2:continue
   first,last=ts[0],ts[-1];label=('ui' if tid==pid else 'latency-fence' if last['name']=='latency-fence' else 'workers')
   delta={k:last[k]-first[k] for k in ('cpu_ns','runqueue_wait_ns','minor_faults','major_faults')}
   if any(v<0 for v in delta.values()):continue
   for k,v in delta.items():totals[label][k]+=v
   totals[label]['threads']+=1
 for value in totals.values():
  demand=value['cpu_ns']+value['runqueue_wait_ns']
  value['runnable_wait_share_pct']=value['runqueue_wait_ns']/demand*100 if demand else None
 rows.append(dict(pair=s['pair'],side=s['side'],tier=s['tier'],observations=observations,threads=dict(totals)))
result=dict(note='Partial observer coverage,2-second snapshots; only observed same-thread counter deltas, no extrapolation. Run-queue wait is runnable CPU scheduling delay, not sleeping/GPU wait. Includes untimed verification and startup, so this is session context, not decomposition of measured action intervals. No causal attribution or sample exclusion.',sessions=rows)
if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
