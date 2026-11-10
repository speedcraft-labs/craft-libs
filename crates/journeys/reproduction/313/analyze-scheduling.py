"""Coarse read-only VM scheduling observations; correlation is not causation."""
import bisect,json,statistics as st,sys
from pathlib import Path
k=Path(__file__).parent;r=json.load(open(sys.argv[1]))
raw=[json.loads(line) for line in (k/'cpu-steal-observer.jsonl').read_text().splitlines()]
intervals=[]
for a,b in zip(raw,raw[1:]):
 diffs=[[bv-av for av,bv in zip(a['cpus'][cpu],b['cpus'][cpu])] for cpu in a['cpus']]
 total=sum(sum(d[:8]) for d in diffs)
 if total<=0:continue
 intervals.append((a['monotonic_ns'],b['monotonic_ns'],sum(d[7] for d in diffs)/total*100))
ends=[x[1] for x in intervals]
observed=[]
for s in r['sessions']:
 for x in s['samples']:
  if x['warmup']:continue
  start,end=x['sent_ns'],x['frame_ns'];weighted=0;covered=0;i=bisect.bisect_right(ends,start)
  for left,right,steal in intervals[i:]:
   if left>=end:break
   overlap=max(0,min(end,right)-max(start,left));weighted+=overlap*steal;covered+=overlap
  observed.append(dict(pair=s['pair'],side=s['side'],action=x['action'],duration_ms=x['duration_ns']/1e6,steal_pct=weighted/covered if covered else None,last_render_ms=x['evidence'].get('perf',{}).get('lastRenderMs')))
print('Scheduling diagnostic: CPU22–27 steal, 2 s /proc/stat buckets weighted by overlap. Sub-second action estimates share buckets. No causal attribution.')
print('| Action | Samples | Steal median/range % | Duration/steal correlation | Fast duration/steal | Slow duration/steal |')
print('|---|---:|---:|---:|---:|---:|')
for action in ['import','preview','exposure','switch','export']:
 xs=[x for x in observed if x['action']==action and x['steal_pct'] is not None];xs.sort(key=lambda x:x['duration_ms']);v=[x['steal_pct'] for x in xs]
 try:corr=f"{st.correlation([x['duration_ms'] for x in xs],v):.3f}"
 except st.StatisticsError:corr='undefined'
 def cell(x):return f"{x['duration_ms']:.1f} ms / {x['steal_pct']:.2f}%"
 print(f'| {action} | {len(xs)} | {st.median(v):.2f} / {min(v):.2f}–{max(v):.2f} | {corr} | {cell(xs[0])} | {cell(xs[-1])} |')
(k/'scheduling-diagnostic.json').write_text(json.dumps(dict(source=sys.argv[1],bucket_seconds=2,observations=observed),indent=2)+'\n')
