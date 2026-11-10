"""Prove the reporting guard leaves collected A/A numeric estimates unchanged."""
import hashlib,importlib.util,json,subprocess
from pathlib import Path
k=Path(__file__).parent;repo=Path('/jobs/work/speedcraft-labs/wt/313-session-latency')
relative='crates/journeys/scripts/lightcraft_session_report.py'
old=k/'report-before-label-guard.py';old.write_bytes(subprocess.check_output(['git','show','cb3ef47cebd8d1c72ff97060dc55edbd257deaf3:'+relative],cwd=repo))
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
report_path=k/'aa-v5-fixed-attempt-38-9/report.json';report=json.load(open(report_path))
a=module('before_guard',old).summarize(report['sessions'],aa=True)
b=module('after_guard',repo/relative).summarize(report['sessions'],aa=True)
fields=sorted(set(a[0]).intersection(b[0]))
assert len(a)==len(b)==14
assert all({key:x[key] for key in fields}=={key:y[key] for key in fields} for x,y in zip(a,b))
driver=repo/'crates/journeys/scripts/lightcraft_real_app.py';driver_sha=hashlib.sha256(driver.read_bytes()).hexdigest();assert driver_sha==report['driver_sha256']
result=dict(passed=True,rows=14,report=str(report_path),identical_fields=fields,old_statistics_sha256=hashlib.sha256(old.read_bytes()).hexdigest(),new_statistics_sha256=hashlib.sha256((repo/relative).read_bytes()).hexdigest(),unchanged_driver_sha256=driver_sha,note='Only comparison verdict eligibility/metadata changes; all original A/A fields are bit-identical.')
(k/'report-label-compatibility.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
