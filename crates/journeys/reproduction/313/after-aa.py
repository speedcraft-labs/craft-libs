"""Run the predeclared validation/comparison matrices once the frozen A/A finishes.
No lock is held by this supervisor. Each campaign takes one bounded acquisition.
"""
import hashlib,json,os,shlex,subprocess,sys,time
from pathlib import Path
k=Path(__file__).parent;root=Path('/jobs/work/speedcraft-labs')
marker=k/'aa-v6-paired-complete.json'
while not marker.exists():time.sleep(5)
aa_path=Path(json.load(open(marker))['report']);aa=json.load(open(aa_path))
assert aa['comparison_complete'] and aa['output_checked'] and aa['gpu_process_checks_passed']
assert aa['guard']['contended'] is False and aa['prior_acquisitions_passed']
(k/'aa-v6-final-path.txt').write_text(str(aa_path)+'\n')
print('A/A finished:',aa_path,flush=True)
print('A/A gates:',sum(bool(r['aa_pass']) for r in aa['rows']),'/',len(aa['rows']),flush=True)
# Delay exactly 10% of the declared A/A control warm-quit median. The actual
# sleep and its proportion of the independent control are reported separately.
row=next(r for r in aa['rows'] if r['action']=='quit' and r['phase']=='warm')
delay=round(row['sides']['main']['median_ns']*.1)
lib=root/'targets/313-session-latency/quit-delay.so'
assert lib.is_file()
config=json.load(open(k/'aa-v6-config.json'));config.update(aa=False,aa_report=str(aa_path))
provenance={'action':'quit','phase':'warm','fraction_of_calibration_control':.1,'requested_ns':delay,'calibration':str(aa_path),'calibration_control_median_ns':row['sides']['main']['median_ns'],'library_sha256':hashlib.sha256(lib.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256((k/'quit-delay.c').read_bytes()).hexdigest(),'build_command':'cc -shared -fPIC -O2 -Wall -Wextra -Werror sensitivity/quit-delay.c -o targets/313-session-latency/quit-delay.so','note':'Test-only ELF destructor, loaded into app processes only. Both arms load the same shim; only main sleeps. Wrapper exec preserves PID. No production measurements use it.'}
for side in ('point','main'):
 app=Path(config['revisions'][side]['binary']);wrapper=root/'targets/313-session-latency'/('quit-delay-'+side)
 script='#!/bin/sh\nexport CRAFT_JOURNEYS_TEST_QUIT_DELAY_NS='+str(delay if side=='main' else 0)+'\nexport CRAFT_JOURNEYS_TEST_QUIT_DELAY_LOG="$PWD/test-quit-delay.jsonl"\nexport LD_PRELOAD='+shlex.quote(str(lib))+'\nexec '+shlex.quote(str(app))+' "$@"\n'
 wrapper.write_text(script);wrapper.chmod(0o755)
 config['revisions'][side]['binary']=str(wrapper)
 provenance[side]={'app':str(app),'app_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'wrapper':str(wrapper),'wrapper_sha256':hashlib.sha256(wrapper.read_bytes()).hexdigest(),'wrapper_source':script}
config['test_quit_delay_ns']=delay
(k/'quit-slowdown-v6-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
(k/'quit-slowdown-v6-config.json').write_text(json.dumps(config,indent=2)+'\n')
# The real primary comparison is independent of the deliberate slowdown.
real=json.load(open(k/'comparison-v6-template.json'));real['aa_report']=str(aa_path)
(k/'comparison-v6-config.json').write_text(json.dumps(real,indent=2)+'\n')
for cfg,label in [('quit-slowdown-v6-config.json','quit-slowdown-v6'),('comparison-v6-config.json','comparison-v6-primary')]:
 print('starting',label,flush=True)
 subprocess.run(['python3',str(k/'campaign.py'),str(k/cfg),label],check=True)
# Upstream is descriptive and collected only after the primary AB/BA blocks.
completed=json.load(open(k/'comparison-v6-primary-complete.json'))
real['resume_report']=completed['report'];real['acquisition_sides']=['upstream']
(k/'comparison-v6-upstream-config.json').write_text(json.dumps(real,indent=2)+'\n')
subprocess.run(['python3',str(k/'campaign.py'),str(k/'comparison-v6-upstream-config.json'),'comparison-v6-upstream'],check=True)
print('ALL TYPICAL MATRICES COMPLETE',flush=True)
