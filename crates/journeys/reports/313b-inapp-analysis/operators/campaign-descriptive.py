"""Default-version timings are descriptive; unequal-output gates stay failed."""
import ast,copy,json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).parent.parent;config_path=Path(sys.argv[1]);name=sys.argv[2];base=json.loads(config_path.read_text())
sys.path.insert(0,'/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts')
from lightcraft_session_report import check_pixels,check_photo_frames,check_export_pixels,summarize,timing_comparison,validate_session
from lightcraft_real_app import session_calibration
os.environ['CRAFT_JOURNEYS_INAPP_TIMING']='1';assert os.environ.get('CRAFT_JOURNEYS_INAPP_SWITCH_DELAY_NS','0')=='0';assert os.environ.get('CRAFT_JOURNEYS_TEST_SWITCH_DELAY_MS','0')=='0'
calibration=session_calibration(base);records=[]
# Preserve the already-completed first primary pair, including its FAILED quality gate.
seed=Path(base['descriptive_seed_report']);old=json.loads(seed.read_text());assert old['failure'].startswith('primary output equivalence failed:')
for s in old['sessions']:
 actual=s['side'];raw=Path(base['descriptive_seed_acquisition'])/actual/'report.json';provenance=json.loads(raw.read_text());assert provenance['guard']['contended'] is False
 s=copy.deepcopy(s);s['photo_output_checks']=check_photo_frames(s) if not s.get('photo_output_checks') else s['photo_output_checks'];s['export_output_check']=check_export_pixels(s);validate_session(s)
 s.update(collection_alias=actual,collection_report=str(raw),collection_binary_sha256=provenance['binary_sha256'][actual])
 records.append(dict(session=s,guard=provenance['guard'],fingerprint=provenance['fingerprint'],raw_report=str(raw),binary_sha256=provenance['binary_sha256'][actual],original_quality_failure=old['failure']))
if base.get('descriptive_resume_report'):
 prior=json.loads(Path(base['descriptive_resume_report']).read_text());assert prior['clock_source_unchanged'] and prior['publishable'] is False
 records=[dict(provenance,session=session) for provenance,session in zip(prior['acquisition_provenance'],prior['sessions'],strict=True)]
 for record in records:validate_session(record['session']);assert record['guard']['contended'] is False
def post(body,path):
 path.write_text(body+'\n');done=subprocess.run(['gh','issue','comment','291','-R','speedcraft-labs/hyper','--body-file',str(path)],capture_output=True,text=True);path.with_suffix('.post.json').write_text(json.dumps(dict(code=done.returncode,stdout=done.stdout,stderr=done.stderr)))
def acquire(pair,selected,label):
 for attempt in range(3):
  out=root/f'{name}-{pair}-{label}-attempt{attempt}';assert not out.exists()
  c=dict(base,pair=pair,acquisition_sides=selected,descriptive_independent=True);cfg=out.with_suffix('.json');cfg.write_text(json.dumps(c,indent=2)+'\n')
  with out.with_suffix('.log').open('a') as log:
   while True:
    code=subprocess.run(['flock','/jobs/work/speedcraft-labs/bench.lock','flock','-x','-w','5','-E','76','/jobs/work/speedcraft-labs/gpu.lock','python3',str(root/'operators/lease.py'),str(cfg),str(out)],env=os.environ,stdout=log,stderr=subprocess.STDOUT).returncode
    if code not in (76,77):break
    time.sleep(10 if code==76 else 60)
  if code in (75,124):
   out.with_suffix('.incomplete.json').write_text(json.dumps(dict(code=code,selected=selected,status='incomplete whole group; retain/retry unchanged')))
   post(f'HANDOFF 313b — descriptive collection {out.name} incomplete under840s ({code}); retained and whole selected group retried. No numeric tails filtered.',out.with_suffix('.handoff.md'));continue
  if code:raise RuntimeError(f'{out}: code{code}')
  group=json.loads((out/'group.json').read_text());assert len(group['records'])==len(selected);return group['records']
 raise RuntimeError('three incomplete whole acquisitions: '+str(out))
def report(pair):
 sessions=[record['session'] for record in records];checks=[]
 for p in range(pair+1):
  group={s['side']:s for s in sessions if s['pair']==p};assert set(group)=={'point','main','upstream'}
  try:checks.extend(check_pixels([group['point'],group['main']]))
  except ValueError as e:
   if not str(e).startswith('primary output equivalence failed:'):raise
   case=ast.literal_eval(str(e).split(': ',1)[1]);case.update(strict_gate_error=str(e));checks.append(case)
  checks.extend(check_pixels([group['point'],group['upstream']]))
 rows=summarize(sessions,calibration=calibration,aa=False)
 for row in rows:
  row['statistical_verdict_before_quality_gate']=row['verdict'];row['verdict']='outputs differ; descriptive only';row['primary_equivalent']=False
  row['upstream_equivalent']=all(c['equivalent'] for c in checks if c['side']=='upstream')
 complete=len(sessions)==base['sessions']*3
 result=dict(schema='lightcraft-session-v1',config=base,sessions=sessions,rows=rows,pixel_checks=checks,timing_comparison=timing_comparison(sessions),comparison_complete=complete,output_checked=True,gpu_process_checks_passed=True,prior_acquisitions_passed=True,guard=dict(contended=False,reasons=[]),fingerprint=records[0]['fingerprint'],publishable=False,descriptive_publishable=complete,primary_output_equivalent=False,descriptive_reason='Default imported processV4 at forkpoint versusV7 at main/upstream; unchanged strict developed-pixel gate fails, so no speed verdict.',acquisition_provenance=[{k:v for k,v in record.items() if k!='session'} for record in records],driver_sha256=old['driver_sha256'],harness_revision=old['harness_revision'],clock_source_unchanged=True)
 dest=root/f'{name}-{pair}-derived-report.json';dest.write_text(json.dumps(result,indent=2)+'\n');(root/(name+'-latest.txt')).write_text(str(dest)+'\n')
 state=json.loads((root/'CURRENT-STATE.json').read_text());state.update(status=f'{name}: {pair+1}/{base["sessions"]} complete pairs',latest_report=str(dest),active_campaign=name);(root/'CURRENT-STATE.json').write_text(json.dumps(state,indent=2)+'\n')
 post(f'HANDOFF 313b — {name} {pair+1}/{base["sessions"]} complete actual point/main pairs+upstream; `{dest}`. Same frozen driver/recorder and action clocks. Exact raw collection alias/provenance retained. Strict developed-output gate stays FAILED; publishable=false and every row descriptive only. No speed claims or pixel tolerance changes.',root/f'{name}-{pair}-handoff.md')
 return dest
for pair in range(base['sessions']):
 existing={record['session']['side'] for record in records if record['session']['pair']==pair}
 if {'point','main','upstream'}<=existing:continue
 if not {'point','main'}<=existing:records.extend(acquire(pair,['point','main'],'primary'))
 if 'upstream' not in existing:records.extend(acquire(pair,['upstream'],'descriptive'))
 dest=report(pair);print(json.dumps(dict(pair=pair,status='descriptive complete',report=str(dest))),flush=True)
