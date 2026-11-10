#!/usr/bin/env python3
"""Materialize tier folders with hard links from a craft-corpus-verified download tree."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('manifest',type=Path)
    parser.add_argument('root',type=Path)
    parser.add_argument('tiers',type=Path)
    parser.add_argument('--out',type=Path,required=True,help='Tier root OUTSIDE the stamped download root')
    args=parser.parse_args()
    manifest=tomllib.loads(args.manifest.read_text())
    tiers=json.loads(args.tiers.read_text())
    entries={f['path']:f for f in manifest['file']}
    if args.out.resolve().is_relative_to(args.root.resolve()):
        raise ValueError('tier folders must be outside the stamped corpus tree')
    args.out.mkdir(parents=True,exist_ok=True)
    for tier,names in tiers.items():
        if isinstance(names,dict):
            names=[name for name,entry in entries.items() if names['tag'] in entry.get('tags',[])]
        directory=args.out/tier
        directory.mkdir(exist_ok=True)
        for name in names:
            source=args.root/name
            with source.open('rb') as stream:
                actual=hashlib.file_digest(stream,'sha256').hexdigest()
            if actual!=entries[name]['sha256']:
                raise ValueError(f'corpus SHA mismatch: {name}')
            target=directory/name
            if not target.exists():target.hardlink_to(source)
        actual_names={p.name for p in directory.iterdir()}
        if actual_names!=set(names):raise ValueError(f'unexpected files in {directory}')
        print(f'{tier}: {len(names)} SHA-verified real files')


if __name__=='__main__':main()
