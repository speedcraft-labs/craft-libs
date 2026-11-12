#!/usr/bin/env python3
"""Prepare one LightCraft session build; run before acquiring benchmark/GPU locks."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def digest(path):
    return hashlib.file_digest(open(path, 'rb'), 'sha256').hexdigest()


def apply_app_base_patch(checkout, patch):
    """Same fail-closed forward/reverse-check protocol as craft-journeys prepare."""
    command = ['git', '-C', str(checkout), 'apply']
    forward = subprocess.run(command + ['--check', str(patch)], capture_output=True)
    if forward.returncode == 0:
        subprocess.run(command + [str(patch)], check=True)
        return 'applied'
    reverse = subprocess.run(command + ['--reverse', '--check', str(patch)], capture_output=True)
    if reverse.returncode == 0:
        return 'already present'
    raise RuntimeError('recorder patch incompatible; reject this build, update one common patch and rebuild ALL sides: '
                       + forward.stderr.decode(errors='replace'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'checkout', 'target', 'binary', 'app-base-patch'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    patch = args.app_base_patch.resolve()
    if args.binary.exists():
        raise RuntimeError('binary already exists; choose a fresh build destination')
    revision = subprocess.check_output(['git', '-C', str(args.repo), 'rev-parse', args.revision], text=True).strip()
    if args.checkout.exists():
        raise RuntimeError('checkout must be fresh for an independently prepared build')
    subprocess.run(['git', '-C', str(args.repo), 'worktree', 'add', '--detach', str(args.checkout), revision], check=True)
    patch_sha256=digest(patch)
    status = apply_app_base_patch(args.checkout, patch)
    env = dict(os.environ, CARGO_TARGET_DIR=str(args.target.resolve()), CARGO_BUILD_JOBS='8', SQLX_OFFLINE='true', RUST_MIN_STACK='8388608')
    args.target.mkdir(parents=True,exist_ok=True)
    # Cargo can reuse stale path-workspace artifacts across revisions in a shared target.
    # Lock the entire clean/build/copy transaction, not just the cargo invocation.
    with (args.target/'.session-prepare.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        metadata=json.loads(subprocess.check_output(['cargo','metadata','--locked','--no-deps','--format-version','1'],cwd=args.checkout,env=env))
        members=set(metadata['workspace_members'])
        packages=[p['name'] for p in metadata['packages'] if p['id'] in members]
        clean=['cargo','clean','--release']
        for package in packages:clean+=['-p',package]
        prefix=['taskset','-c','0-21','nice','-n','19']
        subprocess.run(prefix+clean,cwd=args.checkout,env=env,check=True)
        subprocess.run(prefix+['cargo','build','--release','--locked','-p','lightcraft'],cwd=args.checkout,env=env,check=True)
        if digest(patch)!=patch_sha256: raise RuntimeError('common recorder patch changed during build; reject artifact and rebuild all sides')
        args.binary.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.target / 'release/lightcraft', args.binary)
    # Binaries stay outside prunable targets, but never go in NAS evidence directories.
    provenance = dict(revision=revision, app_base_patch=str(patch), patch_sha256=patch_sha256,
                      binary_sha256=digest(args.binary), workspace_clean=True, patch_status=status, checkout=str(args.checkout),
                      command=['cargo', 'build', '--release', '--locked', '-p', 'lightcraft'])
    args.binary.with_suffix('.provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


if __name__ == '__main__':
    main()
