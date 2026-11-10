"""Guarded heavy A/A, then primary and descriptive upstream with identical cadence."""
import json,os,subprocess,time
from pathlib import Path
k=Path(__file__).parent
env=dict(os.environ);env.pop('CRAFT_JOURNEYS_TEST_SWITCH_DELAY_MS',None)
subprocess.run(['python3',str(k/'campaign.py'),str(k/'heavy-aa-1259-config.json'),'heavy-aa-1259'],env=env,check=True)
aa=json.load(open(k/'heavy-aa-1259-complete.json'))['report'];control=json.load(open(aa))
assert control['comparison_complete'] and control['output_checked'] and control['gpu_process_checks_passed'] and control['guard']['contended'] is False
print('Heavy A/A complete; gates',sum(r['aa_pass'] for r in control['rows']),'/',len(control['rows']),flush=True)
# Never hold a benchmark lock while waiting for independent validation.
p=k/'switch-slowdown-validation.json'
while not p.exists():time.sleep(5)
proof=json.load(open(p));assert proof['passed'] and 'switch-slowdown-v6-calibrated' in proof['report']
real=json.load(open(k/'heavy-comparison-1259-template.json'));real['aa_report']=aa;real['acquisition_sides']=['point','main']
(k/'heavy-comparison-1259-config.json').write_text(json.dumps(real,indent=2)+'\n')
subprocess.run(['python3',str(k/'campaign.py'),str(k/'heavy-comparison-1259-config.json'),'heavy-comparison-1259-primary'],env=env,check=True)
real['resume_report']=json.load(open(k/'heavy-comparison-1259-primary-complete.json'))['report'];real['acquisition_sides']=['upstream']
(k/'heavy-comparison-1259-upstream-config.json').write_text(json.dumps(real,indent=2)+'\n')
subprocess.run(['python3',str(k/'campaign.py'),str(k/'heavy-comparison-1259-upstream-config.json'),'heavy-comparison-1259-upstream'],env=env,check=True)
print('ALL HEAVY MATRICES COMPLETE',flush=True)
