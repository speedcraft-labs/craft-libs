"""Print actual between-build separation; never assume a config label proves adjacency."""
import json,statistics as st,sys
from pathlib import Path
out=[]
for name in sys.argv[1:]:
 r=json.load(open(name));pairs=[]
 for tier in sorted({s['tier'] for s in r['sessions']}):
  for pair in sorted({s['pair'] for s in r['sessions'] if s['tier']==tier}):
   groups={s['side']:s for s in r['sessions'] if s['tier']==tier and s['pair']==pair}
   if not {'point','main'}<=groups.keys():continue
   def bounds(s):return min(x['sent_ns'] for x in s['samples']),max(x['exit_ns'] for x in s['quit_samples'])
   a,b=sorted([bounds(groups['point']),bounds(groups['main'])]);d=dict(tier=tier,pair=pair,gap_s=(b[0]-a[1])/1e9,first_duration_s=(a[1]-a[0])/1e9,second_duration_s=(b[1]-b[0])/1e9)
   pairs.append(d)
 print(Path(name).parent.name,':',len(pairs),'complete primary pairs; between-side gap median/max',round(st.median(x['gap_s'] for x in pairs),2),round(max(x['gap_s'] for x in pairs),2),'s')
 print('| Pair | Between-side gap s | First/second timed-session span s |');print('|---|---:|---:|')
 for x in pairs:print(f"| {x['pair']} | {x['gap_s']:.2f} | {x['first_duration_s']:.2f}/{x['second_duration_s']:.2f} |")
 out.append(dict(report=name,pairs=pairs))
Path(__file__).with_name('pair-gap-diagnostic.json').write_text(json.dumps(out,indent=2)+'\n')
