#!/usr/bin/env python3
"""Rebuild the exact PhotoCraft 315b pins after target cleanup.

This only compiles release binaries; it does not run tests or acquire benchmark/GPU locks.
Separate Cargo target directories keep path-workspace artifacts isolated by source revision.
"""
from __future__ import annotations

import hashlib
import json
import os
import argparse
from pathlib import Path
import shutil
import subprocess
import sys


TARGET = Path('/jobs/work/speedcraft-labs/targets/315b')
PINS = TARGET / 'pinned'
KEEP = Path('/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway')
CONFIG_GENERATOR = KEEP / 'operators/generate-configs.py'
WORKTREES = {
    'a': {
        'source': Path('/jobs/work/speedcraft-labs/wt/315b-photocraft-threeway'),
        'revision': '316e00a97eab730e60584df578c295b5c2539d95',
        'name': 'photocraft-a-mergebase',
        'sha256': '9e127556cf8826f3e944ec72c4cb7fdb9196ddb332a766fc1ce2781ff676c52a',
    },
    'b': {
        'source': Path('/jobs/work/speedcraft-labs/wt/315b-photocraft-fork-tip'),
        'revision': 'f07b6b895331287cde377dbffe61abfbdc2a6d5d',
        'name': 'photocraft-b-fork-tip',
        'sha256': '19aab350144684e655c529f4472917f788694895b7349d9a648d29c13bec28f1',
    },
    'c': {
        'source': Path('/jobs/work/speedcraft-labs/wt/315b-photocraft-upstream'),
        'revision': 'eee667f1d92e34db6c438ddd20f3e4f5339cf8a7',
        'name': 'photocraft-c-upstream-tip',
        'sha256': 'fe08d44fa693968b6deba4448d06a8aa743a006739a20a69cad842d59aedef6b',
    },
}


def digest(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    print(f'$ (cd {cwd} && ' + ' '.join(command) + ')', flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def build(cwd: Path, package: str, binary: str) -> Path:
    env = dict(os.environ)
    env['CARGO_BUILD_JOBS'] = '6'
    command = [
        'taskset', '-c', '0-21', 'nice', '-n', '19',
        'cargo', 'build', '--release', '--locked', '-p', package, '--bin', binary,
    ]
    run(command, cwd, env)
    return cwd / 'target' / 'release' / binary


def ensure_source(role: str, item: dict[str, object]) -> None:
    source = item['source']
    assert isinstance(source, Path)
    revision = str(item['revision'])
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True)
    if dirty:
        raise RuntimeError(f'{role} source worktree is not clean: {source}')
    subprocess.run(['git', '-C', str(source), 'merge-base', '--is-ancestor', revision, 'HEAD'], check=True)
    if not (source / 'crates/ui-egui/src/latency.rs').is_file():
        raise RuntimeError(f'{role} source is missing the common latency recorder')
    print(f'{role}: source={head} includes pinned revision {revision}', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--refresh-configs', action='store_true',
        help='after backup, regenerate configs if rebuilt binary hashes differ from their old pins',
    )
    args = parser.parse_args()
    TARGET.mkdir(parents=True, exist_ok=True)
    PINS.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[3]

    harness = build(repo, 'craft-journeys', 'craft-journeys')
    harness_out = PINS / 'craft-journeys'
    shutil.copy2(harness, harness_out)
    print(f'harness sha256={digest(harness_out)}', flush=True)

    built: list[dict[str, str]] = []
    mismatches: list[str] = []
    for role, item in WORKTREES.items():
        ensure_source(role, item)
        source = item['source']
        assert isinstance(source, Path)
        app = build(source, 'photocraft', 'photocraft')
        actual = digest(app)
        expected = str(item['sha256'])
        print(f'{role}: app sha256={actual} expected={expected}', flush=True)
        output = PINS / str(item['name'])
        PINS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(app, output)
        if actual != expected:
            mismatches.append(role)
        built.append({
            'role': role,
            'source_head': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
            'revision': str(item['revision']),
            'binary': str(output),
            'binary_sha256': digest(output),
            'previous_config_sha256': expected,
        })

    manifest = {
        'harness': {'binary': str(harness_out), 'binary_sha256': digest(harness_out)},
        'apps': built,
        'configs_refreshed': False,
    }
    manifest_path = PINS / 'rebuild-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    if mismatches and not args.refresh_configs:
        raise RuntimeError(
            'rebuilt hashes differ for roles ' + ', '.join(mismatches)
            + '; preserve the old configs with nas-keep, then rerun with --refresh-configs'
        )
    if mismatches:
        subprocess.run(['python3', str(CONFIG_GENERATOR)], check=True, cwd=KEEP)
        config = json.loads((KEEP / 'configs/threeway-typical/pair-00.json').read_text())
        actual_by_role = {item['role']: item['binary_sha256'] for item in built}
        configured_by_role = {item['role']: item['binary_sha256'] for item in config['sides']}
        if configured_by_role != actual_by_role:
            raise RuntimeError(f'regenerated config hashes differ: {configured_by_role!r} != {actual_by_role!r}')
        manifest['configs_refreshed'] = True
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Wrote {manifest_path}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
