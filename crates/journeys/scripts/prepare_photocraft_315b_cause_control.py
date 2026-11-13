#!/usr/bin/env python3
"""Build the pre-#10013 control and pin it into the 315b cause config.

This is compile/config work only. It never acquires the bench or GPU locks.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path('/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway')
TARGET = Path('/jobs/work/speedcraft-labs/targets/315b/pinned')
SOURCE = Path('/jobs/work/speedcraft-labs/wt/315b-photocraft-pre10013')
REVISION = 'ffc413ca85f9258cdb10a068e646e273f999f81f'
AFTER_BIG_BRUSH_FIX = '0e2d24db264aa20d0fa9f4040ddb3d608c6fbe56'
ASYNC_PAINT_WORKER = 'a2cbf1c9b97fa729f5571471d2410ece38311611'
OUTPUT = TARGET / 'photocraft-pre10013'


def sha256(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main() -> int:
    head = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain'], text=True)
    if head != REVISION or dirty:
        raise RuntimeError(f'cause source must be clean at {REVISION}; got {head}, dirty={bool(dirty)}')
    subprocess.run(['git', '-C', str(SOURCE), 'merge-base', '--is-ancestor', AFTER_BIG_BRUSH_FIX, 'HEAD'], check=True)
    absent = subprocess.run(['git', '-C', str(SOURCE), 'merge-base', '--is-ancestor', ASYNC_PAINT_WORKER, 'HEAD'])
    if absent.returncode == 0:
        raise RuntimeError('cause source unexpectedly includes the #10013 async paint worker')
    if absent.returncode != 1:
        raise RuntimeError('could not check #10013 ancestry')
    if not (SOURCE / 'crates/ui-egui/src/latency.rs').is_file():
        raise RuntimeError('cause source is missing the common latency recorder')

    env = dict(os.environ)
    env['CARGO_BUILD_JOBS'] = '6'
    command = [
        'taskset', '-c', '0-21', 'nice', '-n', '19',
        'cargo', 'build', '--release', '--locked', '-p', 'photocraft', '--bin', 'photocraft',
    ]
    print(f'$ (cd {SOURCE} && ' + ' '.join(command) + ')', flush=True)
    subprocess.run(command, cwd=SOURCE, env=env, check=True)
    binary = SOURCE / 'target/release/photocraft'
    TARGET.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, OUTPUT)
    binary_sha = sha256(OUTPUT)

    matrix = json.loads((ROOT / 'configs/threeway-typical/pair-00.json').read_text())
    role_a, role_c = (side.copy() for side in matrix['sides'] if side['role'] in {'a', 'c'})
    role_b = {
        'name': 'pre10013',
        'role': 'b',
        'revision': REVISION,
        'binary': str(OUTPUT),
        'binary_sha256': binary_sha,
    }
    matrix.update({'acquisition': 'cause-control-typical', 'planned_pairs': 1, 'pair': 0})
    matrix['sides'] = [role_a, role_b, role_c]
    matrix.setdefault('source_pins', {})['cause_control'] = {
        'revision': REVISION,
        'includes': 'PhotoCraft #10010 big-brush path',
        'excludes': 'PhotoCraft #10013 async paint worker',
    }
    out = ROOT / 'configs/cause-control-typical/pair-00.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(matrix, indent=2) + '\n')

    manifest = TARGET / 'rebuild-manifest.json'
    if manifest.is_file():
        data = json.loads(manifest.read_text())
        data['cause_control'] = {
            'source_head': head,
            'binary': str(OUTPUT),
            'binary_sha256': binary_sha,
            'includes': AFTER_BIG_BRUSH_FIX,
            'excludes': ASYNC_PAINT_WORKER,
        }
        manifest.write_text(json.dumps(data, indent=2) + '\n')
    print(f'cause checkpoint sha256={binary_sha}; config={out}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
