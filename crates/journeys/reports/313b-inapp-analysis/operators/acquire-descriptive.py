"""Collect unchanged driver clocks; preserve failed cross-version quality gates."""
import copy,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
k=Path(__file__).parent;cfg=Path(sys.argv[1]);out=Path(sys.argv[2]);c=json.loads(cfg.read_text())
source=Path('/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts/lightcraft_real_app.py')
assert hashlib.sha256(source.read_bytes()).hexdigest()=='0e5419347a4661c3cf465c8c40f2c5a25ee15b13726df8696081274851c961e3'
assert os.environ.get('CRAFT_JOURNEYS_INAPP_SWITCH_DELAY_NS','0')=='0' and os.environ.get('CRAFT_JOURNEYS_TEST_SWITCH_DELAY_MS','0')=='0'
sys.path.insert(0,str(source.parent));from lightcraft_session_report import check_photo_frames,check_export_pixels,validate_session
unit=Path('/proc/self/cgroup').read_text().strip().split('/')[-1]
out.with_suffix('.unit.json').write_text(json.dumps(dict(unit=unit,config=str(cfg),out=str(out))))
out.mkdir(parents=True,exist_ok=False);records=[];last=None
order=('point','main','upstream') if c['pair']%2==0 else ('upstream','main','point')
for actual in order:
 if actual not in c['acquisition_sides']:continue
 remaining=(int(os.environ['SESSION_LEASE_DEADLINE_NS'])-time.monotonic_ns())/1e9
 if last is not None and remaining<last*1.5+30:
  out.with_suffix('.deferred.json').write_text(json.dumps(dict(actual_side=actual,remaining_seconds=remaining,preceding_side_seconds=last)));sys.exit(75)
 child=copy.deepcopy(c);child.pop('resume_report',None);child.update(side='point',acquisition_sides=['point'],collection_alias={'point':actual})
 child['revisions']['point']=copy.deepcopy(c['revisions'][actual])
 path=out/(actual+'.json');path.write_text(json.dumps(child,indent=2)+'\n');dest=out/actual
 code=subprocess.run(['python3',str(k/'acquire-display.py'),str(path),str(dest)]).returncode
 raw=dest/'report.json';report=json.loads(raw.read_text())
 if report.get('failure') or report.get('guard',{}).get('contended') is not False or report.get('gpu_process_checks_passed') is not True:raise RuntimeError(str(report.get('failure',report.get('guard'))))
 assert len(report['sessions'])==1 and report['sessions'][0]['side']=='point'
 s=copy.deepcopy(report['sessions'][0]);assert s['pair']==c['pair'] and s['test_switch_delay_ms']==0
 assert not any(x['in_app'].get('test_delay_requested_ns',0) for x in s['samples'])
 # Native photo change and JPEG checks remain strict, outside every clock.
 s['photo_output_checks']=check_photo_frames(s);s['export_output_check']=check_export_pixels(s)
 s.update(side=actual,collection_alias='point',collection_report=str(raw),collection_binary_sha256=report['binary_sha256']['point'])
 validate_session(s);assert s['samples']==report['sessions'][0]['samples']
 records.append(dict(session=s,guard=report['guard'],fingerprint=report['fingerprint'],raw_report=str(raw),binary_sha256=report['binary_sha256']['point']))
 protected={s[key] for key in ('oracle','export_sample','export_oracle')}
 for image in Path(s['directory']).rglob('*.png'):
  if str(image) not in protected and 'headless-attempt' not in image.name and '.rejected.' not in image.name:image.unlink()
 (out/(actual+'.accepted.json')).write_text(json.dumps(records[-1],indent=2)+'\n')
 last=(time.perf_counter_ns()-s['launch_ns'])/1e9
(out/'group.json').write_text(json.dumps(dict(pair=c['pair'],selected=c['acquisition_sides'],records=records,clock_source_unchanged=True),indent=2)+'\n')
