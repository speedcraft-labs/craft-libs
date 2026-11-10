"""Finish the original run, retain its floor, then test the predeclared tighter pairing."""
import json,subprocess,time
from pathlib import Path
k=Path(__file__).parent
while not (k/'aa-v5-fixed-complete.json').exists():time.sleep(5)
path=json.load(open(k/'aa-v5-fixed-complete.json'))['report']
print('Original v5 complete; diagnostic retained:',path,flush=True)
subprocess.run(['python3',str(k/'campaign.py'),str(k/'aa-v6-config.json'),'aa-v6-paired'],check=True)
