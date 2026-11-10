"""Synthetic rejection checks only; these are not app benchmark evidence."""
import copy,hashlib,json,math,subprocess,sys
from pathlib import Path
k=Path(__file__).parent;out=k/'switch-validator-selftest';out.mkdir(exist_ok=True)
p=json.load(open(k/'switch-slowdown-v6-provenance.json'));(out/'switch-slowdown-v6-provenance.json').write_text(json.dumps(p));source=(k/'validate-switch-slowdown.py').read_bytes();(out/'runner.py').write_bytes(source)
base=p['calibration_control_median_ns'];requested=p['requested_ms'];delay=math.ceil(requested*1e6)
r=dict(comparison_complete=True,output_checked=True,gpu_process_checks_passed=True,prior_acquisitions_passed=True,guard=dict(contended=False),config=dict(sessions=20,test_switch_delay_ms=requested),sessions=[],rows=[dict(action='switch',phase='warm',calibration_contains_unity=True,sides={'point':{'median_ns':base}},speedup=1/1.1,ci95=[.89,.93],verdict='slower',minimum_detectable_effect_pct=15,estimated_mde_pct=3)])
for pair in range(20):
 for side in ['point','main']:
  samples=[]
  for i in range(4):
   sent=1000000000+i*1000000000;d=dict(requested_ms=requested,queue_start_ns=sent,wire_send_ns=sent+delay,actual_delay_ns=delay) if side=='main' else None
   samples.append(dict(action='switch',warmup=False,sent_ns=sent,frame_ns=sent+delay+int(base),duration_ns=delay+int(base),evidence=dict(test_delay=d)))
  r['sessions'].append(dict(side=side,pair=pair,test_switch_delay_ms=requested if side=='main' else 0,samples=samples))
cases={'valid':(r,0)}
bad=copy.deepcopy(r);bad['sessions'][1]['samples'][0]['frame_ns']=1000000000+delay-1;cases['delay-outside-clock']=(bad,1)
bad=copy.deepcopy(r);bad['sessions'][1]['samples'][0]['evidence']['test_delay']['actual_delay_ns']+=1;cases['inconsistent-clock-difference']=(bad,1)
bad=copy.deepcopy(r);bad['rows'][0]['ci95']=[.89,1.01];bad['rows'][0]['verdict']='no measurable change';cases['not-significantly-slower']=(bad,2)
bad=copy.deepcopy(r);bad['rows'][0]['sides']['point']['median_ns']=base*2;cases['actual-injection-five-percent']=(bad,2)
results=[]
for label,(report,expected) in cases.items():
 path=out/(label+'.json');path.write_text(json.dumps(report));result=subprocess.run([sys.executable,str(out/'runner.py'),str(path)],capture_output=True,text=True);(out/(label+'.log')).write_text(result.stdout+result.stderr);assert result.returncode==expected,(label,result.returncode,result.stdout,result.stderr);results.append(dict(case=label,expected_exit=expected,actual_exit=result.returncode))
(out/'README.md').write_text('Synthetic validator boundary tests only; no app latency claims or positive-control benchmark evidence. Real physical proof is generated only after the 20-pair app campaign.\n')
(k/'switch-validator-selftest.json').write_text(json.dumps(dict(passed=True,validator_sha256=hashlib.sha256(source).hexdigest(),cases=results),indent=2)+'\n');print('Physical-delay validator: 5/5 synthetic acceptance/rejection checks pass. Not app benchmark evidence.')
