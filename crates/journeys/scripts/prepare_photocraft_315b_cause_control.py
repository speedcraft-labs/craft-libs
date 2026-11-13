#!/usr/bin/env python3
"""Build a minimal checkpoint containing upstream PhotoCraft #11152.

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
SOURCE = Path('/jobs/work/speedcraft-labs/wt/315b-photocraft-stroke-budget')
REVISION = '0a6655ffe6ef5cdc885cd20027360311bdb60779'
SOURCE_HEAD = '8946de6589f5dade05e27059461a096be1ae458a'
MERGE_BASE = '74330157cb601573ae4523a95bb9132822fc3918'
STROKE_BUDGET_COMMITS = [
    'd98b9ea17be9b1b96aa3e052fb33e981b36928b9',
    'efd725cc89aa0cea7844319d8a6561d914ec92cf',
    '90cd7a78df19996af59184799befd7e93617923d',
]
OUTPUT = TARGET / 'photocraft-stroke-budget-control'
RECORDER_SHA256 = '0c5c15480a8ea911b24707a7001a743412d548b3f7fa93f503364ef7aec59653'


def sha256(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main() -> int:
    head = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain'], text=True)
    if head != SOURCE_HEAD or dirty:
        raise RuntimeError(f'cause source must be clean at {SOURCE_HEAD}; got {head}, dirty={bool(dirty)}')
    subprocess.run(['git', '-C', str(SOURCE), 'merge-base', '--is-ancestor', REVISION, 'HEAD'], check=True)
    subprocess.run(['git', '-C', str(SOURCE), 'merge-base', '--is-ancestor', MERGE_BASE, 'HEAD'], check=True)
    for commit in STROKE_BUDGET_COMMITS:
        subprocess.run(['git', '-C', str(SOURCE), 'merge-base', '--is-ancestor', commit, 'HEAD'], check=True)
    recorder = SOURCE / 'crates/ui-egui/src/latency.rs'
    if not recorder.is_file() or sha256(recorder) != RECORDER_SHA256:
        raise RuntimeError('cause source is missing the common recorder or its hash differs')

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
        'name': 'stroke-budget-control',
        'role': 'b',
        'revision': REVISION,
        'binary': str(OUTPUT),
        'binary_sha256': binary_sha,
    }
    matrix.update({'acquisition': 'cause-control-typical', 'planned_pairs': 1, 'pair': 0})
    matrix['sides'] = [role_a, role_b, role_c]
    matrix.setdefault('source_pins', {})['cause_control'] = {
        'revision': REVISION,
        'based_on_merge_base': MERGE_BASE,
        'includes': STROKE_BUDGET_COMMITS,
        'recorder_sha256': RECORDER_SHA256,
    }
    for tier in ('typical', 'heavy'):
        tier_matrix = matrix.copy()
        tier_matrix['tier'] = tier
        tier_matrix['payload'] = json.loads((ROOT / f'configs/threeway-{tier}/pair-00.json').read_text())['payload']
        tier_matrix['acquisition'] = f'cause-control-{tier}'
        tier_matrix['planned_pairs'] = 1
        tier_matrix['sides'] = [side.copy() for side in tier_matrix['sides']]
        out = ROOT / f'configs/cause-control-{tier}/pair-00.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(tier_matrix, indent=2) + '\n')

    manifest = TARGET / 'rebuild-manifest.json'
    if manifest.is_file():
        data = json.loads(manifest.read_text())
        data['cause_control'] = {
            'source_head': head,
            'revision': REVISION,
            'binary': str(OUTPUT),
            'binary_sha256': binary_sha,
            'based_on_merge_base': MERGE_BASE,
            'includes': STROKE_BUDGET_COMMITS,
            'recorder_sha256': RECORDER_SHA256,
        }
        manifest.write_text(json.dumps(data, indent=2) + '\n')
    print(f'#11152 cause checkpoint sha256={binary_sha}; configs=typical,heavy', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
