import json,statistics as st,math,sys
from pathlib import Path
k=Path(__file__).parent
paths=sys.argv[1:] or [str(k.parent/'paired-typical-50-resilient-v2/report.json')]
lines=['Variance diagnostics; log SD ×100 is approximate relative SD (%). First use is excluded. No trimming. Only measured repetitions are used. Original import/preview/switch/export and lifecycle rows have one measured value per session: within-session variance is not identifiable, and their across-session SD includes within-session noise. The separate frozen-driver pilot estimates within-session SD from three repeats but has only one session, so its between-session component is not identifiable. New repeated rows subtract within/n from the variance of session means. Old switching uses varying scenes; old/new app commits also differ, so this is not a causal harness-only comparison.','']
for path in paths:
 lines+=['', 'Dataset: '+Path(path).parent.name, '', '| Dataset / action | Sessions | Repeats/session | Across-session log SD % (corrected if identifiable) | Within-session log SD % |','|---|---:|---:|---:|---:|']
 r=json.load(open(path));sessions=[s for s in r['sessions'] if s['side']=='main'];new=any('phase' in x for s in sessions for x in s['samples'])
 for a in ['import','preview','exposure','switch','export','startup','quit']:
  clusters=[]
  for s in sessions:
   if a in ['startup','quit']:
    vals=[x['duration_ns'] for x in s.get(a+'_samples',[]) if x['phase']=='warm'] if new else [s['startup_library_ns'] if a=='startup' else s['exit_ns']-s['quit_request_ns']]
   else:
    xs=[x for x in s['samples'] if x['action']==a]; vals=[x['duration_ns'] for x in xs if not x['warmup']]
   clusters.append([math.log(x) for x in vals])
  within=st.mean(st.variance(xs) for xs in clusters) if all(len(xs)>1 for xs in clusters) else None
  between=st.variance(st.mean(xs) for xs in clusters) if len(clusters)>1 else None
  if between is not None and within is not None:between=max(0,between-st.mean(within/len(xs) for xs in clusters))
  fmt=lambda v:f'{math.sqrt(v)*100:.2f}' if v is not None else 'not identifiable'
  lines.append(f'| {Path(path).parent.name} / {a} | {len(clusters)} | {min(map(len,clusters))} | {fmt(between)} | {fmt(within)} |')
 if any(s.get('control_traces') for s in sessions):
  lines+=['','| Action | Control wait % of timed interval (median) | Inspect calls (median) | X11 candidate interval p95 ms |','|---|---:|---:|---:|']
  for action in ['import','preview','exposure','switch','export']:
   waits=[];counts=[];gaps=[]
   for session in sessions:
    calls=[c for trace in session.get('control_traces',[]) for c in trace['calls']]
    for sample in session['samples']:
     if sample['action']!=action or sample['warmup']:continue
     start,end=sample['sent_ns'],sample['frame_ns']
     overlaps=[c for c in calls if c['sent_ns']<end and c['reply_ns']>start]
     waits.append(sum(max(0,min(end,c['reply_ns'])-max(start,c['sent_ns'])) for c in overlaps)/(end-start)*100)
     counts.append(sum(c['method']=='ui.inspect' for c in overlaps))
     candidates=sorted({c['ns'] for c in sample['evidence']['capture']['candidates'] if start<c['ns']<=sample['evidence']['capture']['verified_ns']})
     gaps.extend((b-a)/1e6 for a,b in zip(candidates,candidates[1:]))
   gaps.sort()
   lines.append(f'| {action} | {st.median(waits):.2f} | {st.median(counts):.1f} | {gaps[min(len(gaps)-1,int(len(gaps)*.95))]:.2f} |' if gaps else f'| {action} | {st.median(waits):.2f} | {st.median(counts):.1f} | unrecorded |')
 if not new:
  lines+=['','Fast/slow retained measured action, fork main. lastRenderMs is the last render only, not the entire action.','', '| Action | Fast ms / lastRenderMs | Slow ms / lastRenderMs |','|---|---:|---:|']
  for a in ['preview','exposure','switch','export']:
   xs=sorted([x for s in sessions for x in s['samples'] if x['action']==a and not x['warmup']],key=lambda x:x['duration_ns'])
   def cell(x):return f"{x['duration_ns']/1e6:.2f} / {x.get('evidence',{}).get('perf',{}).get('lastRenderMs','unrecorded')}"
   lines.append(f'| {a} | {cell(xs[0])} | {cell(xs[-1])} |')
print('\n'.join(lines))
