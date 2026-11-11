"""After all checks close, hash passing captures and remove regenerable caches.

The nine pair-0 default-process comparison oracles remain disputed evidence.
Failed-session and explicitly rejected capture files are retained as failures.
No acquired RAW, catalog, log, report, or source file is deleted.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
assert root == Path('/jobs/work/speedcraft-labs/keep/313b-inapp-timing')
assert (root / 'ALL-PHASES.json').is_file(), 'Collectors must finish before cleanup'
assert not (root / 'final-artifact-pruning.json').exists(), 'Preserve the original deletion/hash manifest'
apply = sys.argv[1:] == ['--apply']
assert not sys.argv[1:] or apply
paths = json.loads((root / 'ALL-PHASES.json').read_text())
real = json.loads(Path(paths['real50']).read_text())
assert real['comparison_complete'] and real['primary_output_equivalent'] is False
disputed = {Path(s[k]).resolve() for s in real['sessions'] if s['pair'] == 0
            for k in ('oracle', 'export_sample', 'export_oracle')}
assert len(disputed) == 9 and all(p.is_file() for p in disputed)
failed = {p.parent.resolve() for p in root.rglob('failed-session.json')}
files = [Path(p) for p in subprocess.check_output(['rg', '--files', '--hidden', str(root)], text=True).splitlines()]
captures = []
caches = []
for path in files:
    assert path.is_relative_to(root)
    suffix = path.suffix.lower()
    if suffix in ('.lcthumb', '.lcpreview', '.pyc'):
        caches.append(dict(path=str(path.relative_to(root)), bytes=path.stat().st_size))
        continue
    if suffix not in ('.png', '.jpg', '.jpeg') or path.name == 'latency-forest.png':
        continue
    reason = ('disputed default V4/V7 output' if path.resolve() in disputed else
              'failed session' if any(p in failed for p in path.resolve().parents) else
              'rejected capture' if any(x in path.name for x in ('headless-attempt', '.rejected.', 'empty-grid-')) else None)
    captures.append(dict(path=str(path.relative_to(root)), bytes=path.stat().st_size,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         retain=reason is not None, reason=reason or 'passing/redundant capture; hash retained'))
manifest = dict(apply=apply, captures=captures, caches=caches,
                policy='keep disputed and failed captures; passing captures become hashes; caches are regenerable')
destination = root / ('final-artifact-pruning.json' if apply else 'final-artifact-pruning-dry-run.json')
destination.write_text(json.dumps(manifest, indent=2) + '\n')
if apply:
    for item in captures:
        if not item['retain']:
            (root / item['path']).unlink()
    for item in caches:
        (root / item['path']).unlink()
print(json.dumps(dict(apply=apply, retained=sum(x['retain'] for x in captures),
                      removed_captures=sum(not x['retain'] for x in captures),
                      removed_caches=len(caches), manifest=str(destination))))
