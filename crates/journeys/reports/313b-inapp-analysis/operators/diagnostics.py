"""Describe retained observations and measured VM scheduling; never filters data."""
import bisect,json,math,statistics,sys
from pathlib import Path
root=Path(__file__).parent.parent
sys.path.insert(0,'/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts')
from lightcraft_session_report import percentile,durations
report=json.loads(Path(sys.argv[1]).read_text())
observed=[json.loads(x) for x in (root/'scheduling-observations.jsonl').read_text().splitlines()]
times=[x['monotonic_ns'] for x in observed]
rows=[]
for s in report['sessions']:
 start=bisect.bisect_left(times,s['launch_ns']);end=bisect.bisect_right(times,s['quit_request_ns'])
 steals=[x['reserved_cpu_steal_pct'] for x in observed[start:end] if x.get('reserved_cpu_steal_pct') is not None]
 actions={a:statistics.median(durations(s,a))/1e6 for a in s.get('actions',('import','preview','exposure','switch','export','startup','quit'))}
 rows.append(dict(pair=s['pair'],side=s['side'],tier=s['tier'],actions_ms=actions,scheduler_observations=len(steals),steal_p50_pct=statistics.median(steals) if steals else None,steal_p95_pct=percentile(steals,.95) if steals else None,steal_max_pct=max(steals) if steals else None))
result=dict(note='Supplemental reserved-CPU /proc/stat steal observations every2s; coverage begins after pair0. Correlation is descriptive, not causal attribution. No samples excluded.',sessions=rows)
if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
for r in rows:print(r['pair'],r['side'],'steal p50/p95',r['steal_p50_pct'],r['steal_p95_pct'],'medians',r['actions_ms'])
