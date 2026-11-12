#!/usr/bin/env python3
"""Run one 315b acquisition per exclusive bench/GPU lease and retain all attempts."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path('/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway')
BENCH = '/jobs/work/speedcraft-labs/bench.lock'
GPU = '/jobs/work/speedcraft-labs/gpu.lock'
LEASE = ROOT / 'operators/lease.py'
HARNESS = Path('/jobs/work/speedcraft-labs/targets/315b/pinned/craft-journeys')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('campaign', choices=('proof','aa','threeway'))
    parser.add_argument('tier', choices=('typical','heavy'))
    parser.add_argument('--retries', type=int, default=2)
    parser.add_argument('--only-pairs', type=int, nargs='+')
    args=parser.parse_args()
    acquisition=f'{args.campaign}-{args.tier}'
    configs=ROOT/'configs'/acquisition
    reports=ROOT/'reports'/acquisition
    reports.mkdir(parents=True, exist_ok=True)
    pairs={'proof':1,'aa':20,'threeway':10}[args.campaign]
    good=json.loads((reports/'successful-pairs.json').read_text()) if (reports/'successful-pairs.json').exists() else []
    failed=json.loads((reports/'failed-pairs.json').read_text()) if (reports/'failed-pairs.json').exists() else []
    selected_pairs=list(range(pairs)) if args.only_pairs is None else args.only_pairs
    if len(set(selected_pairs)) != len(selected_pairs) or any(pair < 0 or pair >= pairs for pair in selected_pairs):
        parser.error(f'--only-pairs values must be unique integers in [0, {pairs - 1}]')
    for pair in selected_pairs:
        config=configs/f'pair-{pair:02d}.json'
        config_value=json.loads(config.read_text())
        expected={(side.get('role'),side.get('revision'),side.get('binary_sha256')) for side in config_value.get('sides',[])}
        selected=None
        for existing_out in sorted(reports.glob(f'pair-{pair:02d}-try-[0-9][0-9]')):
            report_path=existing_out/'report.json'
            if not report_path.exists():
                continue
            value=json.loads(report_path.read_text())
            recorded=value.get('config',{})
            actual={(side.get('role'),side.get('revision'),side.get('binary_sha256')) for side in recorded.get('sides',[])}
            if actual!=expected or recorded.get('expected_driver_sha256')!=config_value.get('expected_driver_sha256'):
                continue
            if all(value.get(k) is True for k in ('session_complete','publishable','gpu_process_checks_passed','gpu_state_passed','output_checked')):
                selected=existing_out
                break
        if selected:
            failed=[item for item in failed if item != pair]
            good=[item for item in good if not Path(item).name.startswith(f'pair-{pair:02d}-try-')]
            good.append(str(selected))
            print(f'{acquisition} pair {pair:02d}: already publishable at {selected}',flush=True)
            (reports/'successful-pairs.json').write_text(json.dumps(good,indent=2)+'\n')
            (reports/'failed-pairs.json').write_text(json.dumps(failed,indent=2)+'\n')
            continue
        good=[item for item in good if not Path(item).name.startswith(f'pair-{pair:02d}-try-')]
        existing = [int(path.name.rsplit('-try-', 1)[1]) for path in reports.glob(f'pair-{pair:02d}-try-[0-9][0-9]') if path.is_dir()]
        first_attempt = max(existing, default=0) + 1
        for attempt in range(first_attempt,first_attempt+args.retries+1):
            out=reports/f'pair-{pair:02d}-try-{attempt:02d}'
            if out.exists():
                continue
            # Each invocation is one lock acquisition. Never queue for either global lock:
            # on contention retain the failed attempt and retry only after checking the
            # separate bench.lock.guard.flock is free, without holding the GPU lock.
            command=['flock','-n','-x',BENCH,'flock','-n','-x',GPU,'env',f'CRAFT_JOURNEYS_HARNESS_BIN={HARNESS}','python3',str(LEASE),str(config),str(out)]
            print(f'{acquisition} pair {pair:02d} try {attempt}: one locked acquisition',flush=True)
            result=subprocess.run(command,text=True,capture_output=True)
            (reports/f'pair-{pair:02d}-try-{attempt:02d}.operator.log').write_text(f'exit_code={result.returncode}\nCOMMAND={" ".join(command)}\n\nSTDOUT\n{result.stdout}\nSTDERR\n{result.stderr}')
            if result.stdout.strip(): print(result.stdout.strip(),flush=True)
            report_path=out/'report.json'
            if result.returncode==0 and report_path.exists():
                value=json.loads(report_path.read_text())
                if all(value.get(k) is True for k in ('session_complete','publishable','gpu_process_checks_passed','gpu_state_passed','output_checked')):
                    selected=out
                    break
            print(f'{acquisition} pair {pair:02d} try {attempt} failed; preserved {out}',flush=True)
        if selected:
            failed=[item for item in failed if item != pair]
            good=[item for item in good if not Path(item).name.startswith(f'pair-{pair:02d}-try-')]
            good.append(str(selected))
        else:
            failed=sorted(set([*failed,pair]))
        (reports/'successful-pairs.json').write_text(json.dumps(good,indent=2)+'\n')
        (reports/'failed-pairs.json').write_text(json.dumps(failed,indent=2)+'\n')
    print(f'{acquisition}: {len(good)}/{pairs} complete; failed={failed}',flush=True)
    return 0 if not failed else 1

if __name__=='__main__':
    raise SystemExit(main())
