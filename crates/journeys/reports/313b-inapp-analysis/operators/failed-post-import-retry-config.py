"""Resume the same fixed import cohort; each acquisition remains hard840s."""
import hashlib,json,os,subprocess,time
from pathlib import Path
r=Path(__file__).resolve().parent.parent
frozen='0e5419347a4661c3cf465c8c40f2c5a25ee15b13726df8696081274851c961e3'
driver=Path('/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts/lightcraft_real_app.py')
assert hashlib.sha256(driver.read_bytes()).hexdigest()==frozen
name='real-import-1259-cont'
config=json.loads((r/'real-import-1259-config.json').read_text())
prior=Path((r/'real-import-1259-latest.txt').read_text().strip())
old=json.loads(prior.read_text());assert len(old['sessions'])==12
assert old['guard']['contended'] is False and old['output_checked']
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:args=(proc/'cmdline').read_bytes().split(b'\0')
 except OSError:continue
 assert not (len(args)>3 and args[1]==str(r/'operators/campaign-v2.py').encode()),'Existing collector must finish; never launch a duplicate'
config.update(resume_report=str(prior),max_acquisition_attempts=10)
p=r/(name+'-config.json');assert not p.exists();p.write_text(json.dumps(config,indent=2)+'\n')
state=json.loads((r/'CURRENT-STATE.json').read_text());state.update(active_campaign=name,pipeline='operators/post-import-continue.py',pipeline_phase=name,pipeline_config=str(p),pipeline_log='post-import-continue.log',status_campaign_names=['aa-import-1259-fixed','real-50-descriptive',name]);(r/'CURRENT-STATE.json').write_text(json.dumps(state,indent=2)+'\n')
with (r/(name+'-campaign.log')).open('a') as log:
 subprocess.run(['python3',str(r/'operators/campaign-v2.py'),str(p),name],stdout=log,stderr=subprocess.STDOUT,check=True)
latest=(r/(name+'-latest.txt')).read_text().strip();report=json.loads(Path(latest).read_text());assert report['comparison_complete'] and len(report['sessions'])==30
result=dict(status='all cohorts complete; report-only patch/tests/backup/PR queues remain',aa=(r/'aa-inapp-r4-latest.txt').read_text().strip(),slowdown=(r/'switch-delay-10pct-latest.txt').read_text().strip(),real50=(r/'real-50-descriptive-latest.txt').read_text().strip(),heavy_aa=(r/'aa-import-1259-fixed-latest.txt').read_text().strip(),heavy_real=latest,driver_sha256=frozen,completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),real50_scope='V4/V7 default developed pixels differ; descriptive only, strict gate retained')
(r/'ALL-PHASES.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
body=r/'all-import-continued-handoff.md';body.write_text('HANDOFF 313b — all fixed cohorts complete, including resumed10pair import comparison. Exact immutable paths in ALL-PHASES.json. Next staged report-only patch, cargo test-pcraft-journeys,52Python/AAidentityproof, finaltables/plots/pruning/NASonce and PRready/mergequeues. Closed failed precision gates and V4/V7 descriptive-only scope remain unchanged.\n');subprocess.run(['gh','issue','comment','291','-R','speedcraft-labs/hyper','--body-file',str(body)],check=True)
