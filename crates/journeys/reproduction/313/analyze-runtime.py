import json,statistics as st,math,sys,collections
from pathlib import Path
r=json.load(open(sys.argv[1]));sessions=r['sessions']
print('Diagnostic only; accepted sessions:',len(sessions))
calls=[c for s in sessions for trace in s.get('control_traces',[]) for c in trace['calls']]
def pct(xs,p):
 xs=sorted(xs);return xs[min(len(xs)-1,int(len(xs)*p))]
print('| Method | Calls | Median RTT ms | p95 RTT ms |')
print('|---|---:|---:|---:|')
for method in ('ui.inspect','engine.execute','ui.pointer'):
 xs=[(c['reply_ns']-c['sent_ns'])/1e6 for c in calls if c['method']==method]
 print(f'| {method} | {len(xs)} | {st.median(xs):.2f} | {pct(xs,.95):.2f} |')
print('\n| Action | Samples | Verified earlier X11 | Timed capture gap p95 ms | Duration/render correlation |')
print('|---|---:|---:|---:|---:|')
for action in ('import','preview','exposure','switch','export'):
 xs=[x for s in sessions for x in s['samples'] if x['action']==action and not x['warmup']]
 gaps=[]
 for x in xs:
  times=sorted({c['ns'] for c in x['evidence']['capture']['candidates'] if x['sent_ns']<c['ns']<=x['frame_ns']})
  gaps.extend((b-a)/1e6 for a,b in zip(times,times[1:]))
 render=[x['evidence'].get('perf',{}).get('lastRenderMs') for x in xs]
 correlation='not attributable'
 if action in ('preview','exposure','switch') and all(v is not None for v in render):
  correlation=f"{st.correlation([x['duration_ns']/1e6 for x in xs],render):.3f}"
 verified=sum(x['evidence']['capture']['method']=='verified-x11' for x in xs)
 print(f"| {action} | {len(xs)} | {verified}/{len(xs)} | {pct(gaps,.95):.2f} | {correlation} |" if gaps else f'| {action} | {len(xs)} | {verified}/{len(xs)} | insufficient adjacent captures | {correlation} |')
print('\nLast render is one render, not the entire action. Export/import cannot be attributed with that field. Correlation is descriptive, not causal. Native verification runs after the selected frame and is outside action time.')
