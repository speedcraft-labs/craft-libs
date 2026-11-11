"""Wait independent unchanged cohorts, then strict heavy real comparison; no CI waiting."""
import hashlib,json,os,subprocess,time
from pathlib import Path
r=Path(__file__).parent.parent;source=Path('/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts/lightcraft_real_app.py');frozen='0e5419347a4661c3cf465c8c40f2c5a25ee15b13726df8696081274851c961e3'
def finished(name):
 pointer=r/(name+'-latest.txt')
 if not pointer.exists():return None
 path=Path(pointer.read_text().strip());d=json.loads(path.read_text());return (path,d) if d.get('comparison_complete') else None
while True:
 for name in ('aa-import-1259-fixed','real-50-descriptive'):
  log=r/(name+'-campaign.log')
  if log.exists() and 'Traceback' in log.read_text():raise RuntimeError('inspect failed collector '+name)
 aa=finished('aa-import-1259-fixed');real=finished('real-50-descriptive')
 if aa and real:break
 time.sleep(30)
assert hashlib.sha256(source.read_bytes()).hexdigest()==frozen
heavy=json.loads((r/'aa-import-1259-fixed-config.json').read_text());revisions=json.loads((r/'real-50-r4-config.json').read_text())['revisions']
heavy.pop('resume_report',None)
config=dict(heavy,aa=False,sessions=10,aa_report=str(aa[0]),revisions=revisions,sides=['point','main','upstream'])
p=r/'real-import-1259-config.json';assert not p.exists();p.write_text(json.dumps(config,indent=2)+'\n')
s=json.loads((r/'CURRENT-STATE.json').read_text());s.update(pipeline_phase='real-import-1259',pipeline_config=str(p));(r/'CURRENT-STATE.json').write_text(json.dumps(s,indent=2)+'\n')
with (r/'real-import-1259-campaign.log').open('a') as log:
 subprocess.run(['python3',str(r/'operators/campaign-v2.py'),str(p),'real-import-1259'],stdout=log,stderr=subprocess.STDOUT,check=True)
hr=finished('real-import-1259');assert hr
result=dict(status='all cohorts complete; final report-only correction/review/NAS/merge queues remain',aa=(r/'aa-inapp-r4-latest.txt').read_text().strip(),slowdown=(r/'switch-delay-10pct-latest.txt').read_text().strip(),real50=str(real[0]),heavy_aa=str(aa[0]),heavy_real=str(hr[0]),driver_sha256=frozen,completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),real50_scope='descriptive default V4/V7 workloads; strict pixel gate remains failed, no speed verdict')
(r/'ALL-PHASES.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
body=r/'all-recovered-phases-handoff.md';body.write_text('HANDOFF 313b — all required cohorts collected; exact paths in ALL-PHASES.json. Real50 defaults remain NON-EQUIVALENT and descriptive only, no pixel gate relaxed. Next: final report-only correction49tests+AA identity proof, conservative MDE/precision tables, image hashes/pruning, one NAS snapshot, PR ready/merge queues.\n');subprocess.run(['gh','issue','comment','291','-R','speedcraft-labs/hyper','--body-file',str(body)],check=True)
