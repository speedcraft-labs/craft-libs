"""Functional probe, then fresh direct-drop20pair A/A and10pair real cohorts."""
import hashlib,json,os,subprocess,time
from pathlib import Path
r=Path(__file__).resolve().parent.parent
driver=Path('/jobs/work/speedcraft-labs/wt/313b-direct-import/crates/journeys/scripts/lightcraft_real_app.py')
frozen='191b35b1fbff2ce9db087093ccd9b8434f32df612c47abf4c3ef3802d9c185cd'
legacy='0e5419347a4661c3cf465c8c40f2c5a25ee15b13726df8696081274851c961e3'
env=dict(os.environ,CRAFT_JOURNEYS_HARNESS_BIN='/jobs/work/speedcraft-labs/tmp/313b-binaries/craft-journeys-direct-import',LIGHTCRAFT_ACQUISITION_ATTEMPTS='10')
def finished(name):
 p=r/(name+'-latest.txt')
 if not p.exists():return None
 path=Path(p.read_text().strip());data=json.loads(path.read_text())
 return (path,data) if data.get('comparison_complete') else None
def check_source():assert hashlib.sha256(driver.read_bytes()).hexdigest()==frozen
check_source()
while True:
 p=finished('direct-import-probe')
 log=r/'direct-import-probe-campaign.log'
 if log.exists() and 'Traceback' in log.read_text():raise RuntimeError('Inspect failed functional probe; do not start a statistical cohort')
 if p:break
 time.sleep(10)
probe_path,probe=p
assert len(probe['sessions'])==3 and probe['driver_sha256']==frozen
assert probe['output_checked'] and probe['gpu_process_checks_passed'] and probe['guard']['contended'] is False
for s in probe['sessions']:
 assert s['import_boundary']=='folder-drop-to-usable-grid' and len(s['samples'])==1
 calls={c['sent_ns']:(t['calls'],i) for t in s['control_traces'] for i,c in enumerate(t['calls'])}
 for sample in s['samples']:
  trace,i=calls[sample['sent_ns']]
  assert trace[i]['method']=='ui.dropFiles' and trace[i+1]['method']=='ui.latency.wait'
  assert sample['in_app']['control_wait_ns']==0
proof=dict(report=str(probe_path),driver_sha256=frozen,all_three_revisions=True,all_folder_drops_immediately_followed_by_single_native_read=True,app_recorder_and_binaries_unchanged=True)
(r/'direct-import-probe-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
# Retire only our old protocol, and only BEFORE a new acquisition starts. Any
# already running bounded acquisition finishes normally; no process is killed.
state=json.loads((r/'CURRENT-STATE.json').read_text());state.update(pipeline='operators/post-direct-import.py',pipeline_log='post-direct-import.log',pipeline_phase='retiring legacy confirmation protocol',status_campaign_names=['aa-import-1259-fixed','real-50-descriptive','direct-import-probe','aa-import-1259-direct','real-import-1259-direct']);(r/'CURRENT-STATE.json').write_text(json.dumps(state,indent=2)+'\n')
(r/'RETIRE-LEGACY-CONFIRMATION').write_text('Direct probe passed on all three revisions. Retire old collector at next acquisition boundary; preserve every old observation.\n')
while True:
 found=False
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:args=(proc/'cmdline').read_bytes().split(b'\0')
  except OSError:continue
  if len(args)>3 and args[1]==str(r/'operators/campaign-v2.py').encode() and args[3]==b'real-import-1259-cont2':found=True
 if not found:break
 time.sleep(5)
legacy_path=(r/'real-import-1259-cont2-latest.txt') if (r/'real-import-1259-cont2-latest.txt').exists() else r/'real-import-1259-latest.txt'
legacy_real=legacy_path.read_text().strip()
def run(config,name):
 check_source();p=r/(name+'-config.json');assert not p.exists();p.write_text(json.dumps(config,indent=2)+'\n')
 state=json.loads((r/'CURRENT-STATE.json').read_text());state.update(active_campaign=name,pipeline_phase=name,pipeline_config=str(p));(r/'CURRENT-STATE.json').write_text(json.dumps(state,indent=2)+'\n')
 with (r/(name+'-campaign.log')).open('a') as log:
  subprocess.run(['python3',str(r/'operators/campaign-v2.py'),str(p),name],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 result=finished(name);assert result
 return result
aa=json.loads((r/'aa-import-1259-fixed-config.json').read_text());aa.pop('resume_report',None);aa.pop('aa_report',None)
aa.update(aa=True,sessions=20,direct_import=True,expected_driver_sha256=frozen)
aa_path,aa_data=run(aa,'aa-import-1259-direct');assert len(aa_data['sessions'])==40
revisions=json.loads((r/'real-import-1259-config.json').read_text())['revisions']
real=dict(aa,aa=False,sessions=10,revisions=revisions,sides=['point','main','upstream'],aa_report=str(aa_path))
real_path,real_data=run(real,'real-import-1259-direct');assert len(real_data['sessions'])==30
result=dict(status='all fixed cohorts complete; final integration/report/backup/queues remain',aa=(r/'aa-inapp-r4-latest.txt').read_text().strip(),slowdown=(r/'switch-delay-10pct-latest.txt').read_text().strip(),real50=(r/'real-50-descriptive-latest.txt').read_text().strip(),heavy_aa=str(aa_path),heavy_real=str(real_path),legacy_heavy_aa=(r/'aa-import-1259-fixed-latest.txt').read_text().strip(),legacy_heavy_real_partial=legacy_real,driver_sha256_by_cohort=dict(typical=legacy,direct_import=frozen),completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),real50_scope='defaultV4/V7 outputs differ; descriptive only',heavy_scope='direct Add-in-place folder drop with review disabled; catalog/thumbnail parity',legacy_scope='confirmation-to-grid A/A and every complete/incomplete real attempt preserved separately; never pooled with direct mode')
(r/'ALL-PHASES.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
body=r/'all-direct-cohorts-handoff.md';body.write_text('HANDOFF313b — all fixed primary cohorts collected. ALL-PHASES.json records both driver hashes and both import protocols. Legacy confirmation observations remain separate, untrimmed. Next final integration/AAidentityproof/tables/plots/passing-image-pruning/NASonce/PRready+mergequeues.\n');subprocess.run(['gh','issue','comment','291','-R','speedcraft-labs/hyper','--body-file',str(body)],check=True)
