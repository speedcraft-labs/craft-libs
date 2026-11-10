"""Fixed 20-pair physical switch check, then the independently measured real tier."""
import json,os,subprocess
from pathlib import Path
k=Path(__file__).parent;c=json.load(open(k/'switch-slowdown-v6-config.json'))
env=dict(os.environ,CRAFT_JOURNEYS_TEST_SWITCH_DELAY_MS=str(c['test_switch_delay_ms']))
subprocess.run(['python3',str(k/'campaign.py'),str(k/'switch-slowdown-v6-config.json'),'switch-slowdown-v6'],env=env,check=True)
proof=json.load(open(k/'switch-slowdown-v6-complete.json'))['report']
subprocess.run(['python3',str(k/'validate-switch-slowdown.py'),proof],check=True)
subprocess.run(['python3',str(k/'campaign.py'),str(k/'comparison-v6-config.json'),'comparison-v6-primary'],check=True)
real=json.load(open(k/'comparison-v6-config.json'));real['resume_report']=json.load(open(k/'comparison-v6-primary-complete.json'))['report'];real['acquisition_sides']=['upstream']
(k/'comparison-v6-upstream-config.json').write_text(json.dumps(real,indent=2)+'\n')
subprocess.run(['python3',str(k/'campaign.py'),str(k/'comparison-v6-upstream-config.json'),'comparison-v6-upstream'],check=True)
print('ALL TYPICAL MATRICES COMPLETE',flush=True)
