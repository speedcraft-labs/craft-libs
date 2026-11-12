"""Locate observed import variation without filtering or claiming a causal partition."""
import collections,json,statistics,sys
from pathlib import Path
p=Path(sys.argv[1]);report=json.loads(p.read_text())
assert report['comparison_complete'] and report['config']['aa']
rows=[]
for side in ('point','main'):
 sessions=[s for s in report['sessions'] if s['side']==side]
 samples=[x for s in sessions for x in s['samples'] if x['action']=='import' and not x['warmup']]
 assert len(sessions)==20 and samples
 session_medians=[statistics.median(x['in_app']['duration_ns']/1e6 for x in s['samples'] if x['action']=='import' and not x['warmup']) for s in sessions]
 dist=lambda xs:dict(min=min(xs),median=statistics.median(xs),max=max(xs))
 stats=next(r for r in report['rows'] if r['action']=='import' and r['phase']=='warm')['sides'][side]
 rows.append(dict(side=side,sessions=len(sessions),warm_samples=len(samples),
  boundary=sessions[0]['import_boundary'],session_completion_medians_ms=dist(session_medians),
  first_photo_ms=dist([x['in_app']['first_response_ns']/1e6 for x in samples]),
  first_photo_to_complete_ms=dist([(x['in_app']['duration_ns']-x['in_app']['first_response_ns'])/1e6 for x in samples]),
  completion_frames=dist([x['in_app']['completion_frames'] for x in samples]),
  first_frames=dist([x['in_app']['first_frames'] for x in samples]),
  first_pending_labels=dict(collections.Counter(label for x in samples for label in x['in_app']['first_background_pending'])),
  completion_pending_labels=dict(collections.Counter(label for x in samples for label in x['in_app']['completion_background_pending'])),
  within_log_sd=stats['within_log_sd'],between_log_sd=stats['between_log_sd']))
result=dict(report=str(p),note='All fixed20 pairs retained. Direct folder-drop includes expansion/probing/preparation and frame-paced commits. First-photo stamps and completion stamps locate observed variation but do not partition CPU, disk, GPU, scheduler or recorder confirmation delay causally. Completion pending snapshot precedes GPU callback.',rows=rows)
Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
