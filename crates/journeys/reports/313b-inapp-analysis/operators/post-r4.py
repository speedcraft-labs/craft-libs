"""Durable, predeclared next phases. Stops on errors; never adjusts precision gates."""
import hashlib,json,os,statistics,subprocess,sys,time
from pathlib import Path
root=Path(__file__).parent.parent
source=Path('/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts/lightcraft_real_app.py')
frozen=hashlib.sha256(source.read_bytes()).hexdigest()
base=json.loads((root/'aa-r4-config.json').read_text())
def write(name,config):
 path=root/(name+'-config.json')
 if path.exists():raise RuntimeError('refuse overwrite: '+str(path))
 path.write_text(json.dumps(config,indent=2)+'\n');return path
def phase(name,c,env=None):
 if hashlib.sha256(source.read_bytes()).hexdigest()!=frozen:raise RuntimeError('driver changed; do not mix methods')
 cfg=write(name,c)
 state=json.loads((root/'CURRENT-STATE.json').read_text());state.update(pipeline_phase=name,pipeline_config=str(cfg));(root/'CURRENT-STATE.json').write_text(json.dumps(state,indent=2)+'\n')
 with (root/(name+'-campaign.log')).open('a') as log:
  subprocess.run(['python3',str(root/'operators/campaign-v2.py'),str(cfg),name],env=dict(os.environ,**(env or {})),stdout=log,stderr=subprocess.STDOUT,check=True)
 path=Path((root/(name+'-latest.txt')).read_text().strip());report=json.loads(path.read_text())
 if not report.get('comparison_complete'):raise RuntimeError('incomplete phase: '+name)
 return path,report
def notify(name,body):
 p=root/(name+'-handoff.md');p.write_text(body+'\n');subprocess.run(['gh','issue','comment','291','-R','speedcraft-labs/hyper','--body-file',str(p)],check=True)
while True:
 latest=root/'aa-inapp-r4-latest.txt'
 if latest.exists():
  aa_path=Path(latest.read_text().strip());aa=json.loads(aa_path.read_text())
  if aa.get('comparison_complete'):break
 if 'Traceback' in (root/'aa-inapp-r4-campaign.log').read_text():raise RuntimeError('A/A collector stopped; inspect before continuing')
 time.sleep(30)
assert len(aa['sessions'])==40 and aa['config']['repetitions']==6
notify('aa-r4-complete',f'HANDOFF 313b — fixed20pair R4 A/A COMPLETE, raw `{aa_path}`. Do not change thresholds or discard pairs. Full cold/warm ratio/CI/half-width/MDE rows there; precision failures, if any, stay failures. Next predeclared independent untreated2pair dose pilot,10pair physical switch-delay check, real10pair50RAW+upstream,20pair1259import A/A and10pair1259real+upstream. Both primary builds stay adjacent per<=840s lease; upstream is descriptive and acquired separately. Heavy admissions only with empty benchmark queue. app62b1627c/libs65838523, source remains frozen.')
# Pilot is separate evidence, never pooled into the slowdown inference.
pilot_config=dict(base,aa=False,sessions=2)
pilot_path,pilot=phase('switch-dose-pilot',pilot_config)
control=[x['in_app']['duration_ns'] for s in pilot['sessions'] for x in s['samples'] if x['action']=='switch' and not x['warmup']]
median=statistics.median(control);dose=round(median*.10)
dose_proof=dict(method='fixed physical UI-thread delay after acceptance, before dispatch',untreated_pilot=str(pilot_path),control_warm_median_ns=median,requested_delay_ns=dose,fraction=.10,independent_test_pairs=10,source_sha256=frozen)
(root/'switch-dose-predeclared.json').write_text(json.dumps(dose_proof,indent=2)+'\n')
notify('switch-dose',f'HANDOFF 313b — independent untreated dose pilot `{pilot_path}` complete. Frozen physical app-side switch delay={dose}ns,10% of contemporary warm untreated median={median}ns. The next10pairs are independent; pilot excluded. Both binaries contain identical delay code; only main requests opt in. Actual sleep and action clocks recorded inside app; no arithmetic duration modification. Final report must show actual dose as percent of contemporaneous test control and whether CI says slower.')
slow_path,slow=phase('switch-delay-10pct',dict(base,aa=False,sessions=10,aa_report=str(aa_path)),{'CRAFT_JOURNEYS_INAPP_SWITCH_DELAY_NS':str(dose)})
main_delay=[x['in_app']['test_delay_actual_ns'] for s in slow['sessions'] if s['side']=='main' for x in s['samples'] if x['action']=='switch' and not x['warmup']]
control=[x['in_app']['duration_ns'] for s in slow['sessions'] if s['side']=='point' for x in s['samples'] if x['action']=='switch' and not x['warmup']]
dose_proof.update(test_report=str(slow_path),actual_delay_median_ns=statistics.median(main_delay),contemporaneous_control_median_ns=statistics.median(control),actual_dose_control_pct=statistics.median(main_delay)/statistics.median(control)*100)
(root/'switch-dose-result.json').write_text(json.dumps(dose_proof,indent=2)+'\n')
# Real point/main pairs and upstream descriptive samples use the same conditions as A/A.
real=dict(base,aa=False,sessions=10,aa_report=str(aa_path),sides=['point','main','upstream'])
real['revisions']={**base['revisions'],'point':{'revision':'fc97c728644d399843d8201f83d25ccf81b89669','binary':'/jobs/work/speedcraft-labs/tmp/313b-binaries/lightcraft-r3-point'},'upstream':{'revision':'c2e9c456c9bfdcd4d56d8b88b8a5b546b69a3223','binary':'/jobs/work/speedcraft-labs/tmp/313b-binaries/lightcraft-r3-upstream'}}
real_path,real_report=phase('real-50-r4',real)
heavy=dict(base,payloads={'import-1259':'/jobs/work/speedcraft-labs/hyper/corpus/lightcraft-session-tiers-2026/import-1259'},repetitions=2,import_only=True,stress_only_when_queue_empty=True)
heavy_aa_path,heavy_aa=phase('aa-import-1259',heavy)
heavy_real=dict(heavy,aa=False,sessions=10,aa_report=str(heavy_aa_path),revisions=real['revisions'],sides=['point','main','upstream'])
heavy_real_path,heavy_real_report=phase('real-import-1259',heavy_real)
result=dict(status='all predeclared cohorts complete; final review/tables/pruning/NAS/merge queues remain',aa=str(aa_path),slowdown=str(slow_path),real50=str(real_path),heavy_aa=str(heavy_aa_path),heavy_real=str(heavy_real_path),driver_sha256=frozen,completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
(root/'ALL-PHASES.json').write_text(json.dumps(result,indent=2)+'\n')
notify('all-phases',f'HANDOFF 313b — all predeclared cohorts complete. Exact report paths in `{root}/ALL-PHASES.json`. No thresholds relaxed; every failed gate remains a failure. Next: final root review of tables and physical-dose magnitude, measured cause/floor for any imprecision, prune passing images to hashes, one final NAS snapshot, update PR descriptions, ready and merge_when_green. This controller deliberately does not merge or claim acceptance automatically.')
print(json.dumps(result,indent=2),flush=True)
