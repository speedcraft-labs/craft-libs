"""Describe app work/frame/scheduling variation; never changes or filters durations."""
import collections,json,math,statistics,sys
from pathlib import Path
root=Path(__file__).parent.parent
report=json.loads(Path(sys.argv[1]).read_text())
def med(xs):return statistics.median(xs) if xs else None
def corr(xs,ys):
 if len(xs)<3:return None
 a,b=statistics.mean(xs),statistics.mean(ys);den=math.sqrt(sum((x-a)**2 for x in xs)*sum((y-b)**2 for y in ys));return sum((x-a)*(y-b) for x,y in zip(xs,ys))/den if den else None
rows=[]
for tier in sorted({s['tier'] for s in report['sessions']}):
 for side in ('point','main','upstream'):
  group=[s for s in report['sessions'] if s['tier']==tier and s['side']==side]
  if not group:continue
  for action in ('import','preview','exposure','switch','export'):
   samples=[x for s in group for x in s['samples'] if x['action']==action and not x['warmup']]
   if not samples:continue
   perf=[x['evidence'].get('perf',{}) for x in samples]
   render=[p['lastRenderMs'] for p in perf if isinstance(p.get('lastRenderMs'),(int,float))]
   source=collections.Counter(str(x['evidence'].get('loupe',{}).get('source')) for x in samples)
   pending=collections.Counter(v for x in samples for v in x['in_app']['completion_background_pending'])
   session_points=[]
   if action in ('preview','exposure','switch'):
    for s in group:
     selected=[x for x in s['samples'] if x['action']==action and not x['warmup']]
     paired=[x for x in selected if isinstance(x['evidence'].get('perf',{}).get('lastRenderMs'),(int,float)) and x['evidence']['perf']['lastRenderMs']>0]
     if paired:session_points.append((math.log(statistics.median(x['duration_ns'] for x in paired)),math.log(statistics.median(x['evidence']['perf']['lastRenderMs'] for x in paired))))
   rows.append(dict(tier=tier,side=side,action=action,n=len(samples),app_median_ms=med([x['duration_ns']/1e6 for x in samples]),frames_median=med([x['in_app']['completion_frames'] for x in samples]),first_frames_median=med([x['in_app']['first_frames'] for x in samples]),last_render_median_ms=med(render) if action in ('preview','exposure','switch') else None,frame_cpu_median_ms=med([p['frameMs'] for p in perf if isinstance(p.get('frameMs'),(int,float))]),pending_at_completion_n=sum(bool(x['in_app']['completion_background_pending']) for x in samples),pending_labels=dict(pending),loupe_sources=dict(source) if action in ('preview','exposure','switch') else None,session_log_latency_render_correlation=corr([x[0] for x in session_points],[x[1] for x in session_points]),gpu_fallbacks=dict(collections.Counter(str(p.get('gpuFallback')) for p in perf))))
# LastRenderMs is an app diagnostic, not a partition of the frame interval. Cached
# slots can retain earlier work. Correlations describe observations, not causality.
result=dict(note='All accepted observations retained. Internal-render/frame diagnostics are descriptive; cached slots may retain earlier render costs. No causal decomposition or outlier removal.',rows=rows)
if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
