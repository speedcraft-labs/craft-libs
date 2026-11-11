"""Audit native command/read ordering from retained traces, with no timing changes."""
import json,sys
from pathlib import Path
path=Path(sys.argv[1]);report=json.loads(path.read_text());rows=[]
for s in report['sessions']:
 command_by_sent={call['sent_ns']:(trace['calls'],i) for trace in s['control_traces'] for i,call in enumerate(trace['calls'])}
 for sample in s['samples']:
  calls,i=command_by_sent[sample['sent_ns']]
  assert calls[i+1]['method']=='ui.latency.wait',(s['pair'],s['side'],sample['action'],'not immediately followed by native record read')
  assert calls[i+1]['reply_ns']<=sample['frame_ns']
  assert sample['in_app']['control_wait_ns']==0
 lifecycle=[]
 for trace in s['control_traces'][1:]:
  assert trace['calls'][0]['method']=='ui.latency.wait'
  lifecycle.append(trace['pid'])
 rows.append(dict(pair=s['pair'],side=s['side'],tier=s['tier'],actions=len(s['samples']),startup_read_first_pids=lifecycle))
result=dict(report=str(path),sessions=len(rows),action_intervals=sum(x['actions'] for x in rows),startup_read_first=sum(len(x['startup_read_first_pids']) for x in rows),all_commands_immediately_followed_by_single_native_read=True,all_app_control_wait_ns_zero=True,rows=rows)
if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
