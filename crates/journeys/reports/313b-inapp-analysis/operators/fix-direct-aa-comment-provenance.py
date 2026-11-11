"""Correct only this collector's own issue comments; no clocks/configs are modified."""
import hashlib,json,re,subprocess,time
from pathlib import Path
r=Path(__file__).resolve().parent.parent
old='Source branches `algo/313b-inapp-timing`, app62b1627c; timing driver65838523 (0e541934), post-clock validator88e6735f; PRs'
new='Collected harness `ad0f520c5bf295cfd20091d36c9baf4f7a701b1c` on `wip/313b-direct-import`; timing driver SHA256 `191b35b1fbff2ce9db087093ccd9b8434f32df612c47abf4c3ef3802d9c185cd`; import boundary `folder-drop-to-usable-grid`. Recorder patch44fe9373 unchanged; production PR branches `algo/313b-inapp-timing`; PRs'
corrected=set()
while True:
 for p in sorted(r.glob('aa-import-1259-direct-*-handoff.post.json')):
  marker=p.with_suffix('.provenance-correction.json')
  if marker.exists():corrected.add(str(p));continue
  metadata=json.loads(p.read_text())
  if metadata['status']!=0:continue
  comment=re.search(r'issuecomment-(\d+)',metadata['stdout']);assert comment,metadata
  body_path=p.with_suffix('').with_suffix('.md');body=body_path.read_text()
  assert body.startswith('HANDOFF 313b — aa-import-1259-direct:')
  assert old in body
  body_path.with_suffix('.original-body.md').write_text(body)
  fixed=body.replace(old,new)
  payload=marker.with_suffix('.body.json');payload.write_text(json.dumps({'body':fixed}))
  subprocess.run(['gh','api','-X','PATCH',f'repos/speedcraft-labs/hyper/issues/comments/{comment[1]}','--input',str(payload),'--silent'],check=True)
  body_path.write_text(fixed)
  marker.write_text(json.dumps(dict(comment_id=comment[1],correction='stale copied provenance in operator prose only; app records/statistics unchanged',body_sha256=hashlib.sha256(fixed.encode()).hexdigest()),indent=2)+'\n')
  corrected.add(str(p));print('Corrected own handoff provenance',comment[1],flush=True)
 if len(corrected)==20:break
 time.sleep(30)
