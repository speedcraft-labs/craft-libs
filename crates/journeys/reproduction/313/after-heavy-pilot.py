"""Advance the heavy tier only after an actually completed, guarded pilot.
All stress acquisitions remain nonblocking and wait for an empty bench queue.
"""
import json,subprocess,time
from pathlib import Path
k=Path(__file__).parent;pilot=k/'heavy-aa-pilot-v5/point/report.json'
# The Rust guard is attached only after the app driver finishes. Never consume a
# partially written driver report, even if its image checks have completed.
while True:
 try:r=json.load(open(pilot))
 except (FileNotFoundError,json.JSONDecodeError):r={}
 if r.get('guard',{}).get('contended') is False and r.get('output_checked') and r.get('gpu_process_checks_passed') and len(r.get('sessions',[]))==1 and not r.get('failure'):break
 if (k/'heavy-aa-pilot-v5.lease-expired.json').exists() or r.get('failure'):
  raise RuntimeError('heavy pilot failed or exceeded the lease; inspect retained raw data before choosing the next approach')
 time.sleep(5)
c=json.load(open(k/'heavy-aa-v5-config.json'));c['resume_report']=str(pilot)
(k/'heavy-aa-v5-seeded-config.json').write_text(json.dumps(c,indent=2)+'\n')
print('guarded heavy pilot complete',pilot,flush=True)
subprocess.run(['python3',str(k/'campaign.py'),str(k/'heavy-aa-v5-seeded-config.json'),'heavy-aa-v5-fixed'],check=True)
aa=Path(json.load(open(k/'heavy-aa-v5-fixed-complete.json'))['report'])
real=json.load(open(k/'heavy-comparison-v5-template.json'));real['aa_report']=str(aa)
(k/'heavy-comparison-v5-config.json').write_text(json.dumps(real,indent=2)+'\n')
subprocess.run(['python3',str(k/'campaign.py'),str(k/'heavy-comparison-v5-config.json'),'heavy-comparison-v5-primary'],check=True)
real['resume_report']=json.load(open(k/'heavy-comparison-v5-primary-complete.json'))['report'];real['acquisition_sides']=['upstream']
(k/'heavy-comparison-v5-upstream-config.json').write_text(json.dumps(real,indent=2)+'\n')
subprocess.run(['python3',str(k/'campaign.py'),str(k/'heavy-comparison-v5-upstream-config.json'),'heavy-comparison-v5-upstream'],check=True)
print('ALL HEAVY MATRICES COMPLETE',flush=True)
