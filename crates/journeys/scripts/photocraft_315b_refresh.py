#!/usr/bin/env python3
"""Refresh the 315b brush matrix without waiting while holding shared locks."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path('/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway')
TARGET = Path('/jobs/work/speedcraft-labs/targets/315b')
RUNNER = ROOT / 'operators/run-campaign.py'
REPORTER = Path(__file__).with_name('photocraft_threeway_report.py')
LEASE = ROOT / 'operators/lease.py'
NAS_KEEP = Path('/jobs/work/speedcraft-labs/scripts/nas-keep')
HARNESS = TARGET / 'pinned/craft-journeys'
BENCH = '/jobs/work/speedcraft-labs/bench.lock'
GUARD = '/jobs/work/speedcraft-labs/bench.lock.guard.flock'
GPU = '/jobs/work/speedcraft-labs/gpu.lock'
BUSY_PATHS = {BENCH, GUARD, GPU}
LOG = ROOT / 'reports/refresh-scheduler.log'


def log(message: str) -> None:
    stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    line = f'{stamp} {message}'
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a') as handle:
        handle.write(line + '\n')


def locks_busy() -> tuple[bool, str]:
    raw = subprocess.check_output(
        ['sudo', '-n', 'lslocks', '--json', '--output', 'PID,COMMAND,MODE,PATH'],
        text=True,
    )
    rows = json.loads(raw).get('locks', [])
    busy = [row for row in rows if row.get('path') in BUSY_PATHS]
    return bool(busy), ', '.join(f"{row.get('command')}:{row.get('path')}" for row in busy)


def wait_for_admission() -> None:
    last_note = 0.0
    while True:
        busy, detail = locks_busy()
        if not busy:
            return
        now = time.monotonic()
        if now - last_note >= 300:
            log(f'no lock acquired; benchmark queue is occupied ({detail})')
            last_note = now
        time.sleep(30)


def backup(note: str) -> bool:
    env = dict(os.environ, NAS_KEEP_NOTE=note)
    result = subprocess.run(
        [str(NAS_KEEP), '315b-photocraft-threeway', str(ROOT)],
        text=True,
        capture_output=True,
        env=env,
    )
    if result.stdout.strip():
        log(result.stdout.strip())
    if result.stderr.strip():
        log(f'NAS backup stderr: {result.stderr.strip()}')
    if result.returncode:
        log(f'NAS backup failed (exit {result.returncode}): {note}')
        return False
    return True


def current_success(acquisition: str, pair: int) -> bool:
    configs = ROOT / 'configs' / acquisition
    reports = ROOT / 'reports' / acquisition
    config_path = configs / f'pair-{pair:02d}.json'
    config = json.loads(config_path.read_text())
    expected = {
        (side.get('role'), side.get('revision'), side.get('binary_sha256'))
        for side in config.get('sides', [])
    }
    good_path = reports / 'successful-pairs.json'
    if not good_path.exists():
        return False
    for item in json.loads(good_path.read_text()):
        if Path(item).name[:7] != f'pair-{pair:02d}':
            continue
        report_path = Path(item) / 'report.json'
        if not report_path.exists():
            continue
        report = json.loads(report_path.read_text())
        recorded = report.get('config', {})
        actual = {
            (side.get('role'), side.get('revision'), side.get('binary_sha256'))
            for side in recorded.get('sides', [])
        }
        if (
            actual == expected
            and recorded.get('expected_driver_sha256') == config.get('expected_driver_sha256')
            and all(report.get(key) is True for key in (
                'session_complete', 'publishable', 'gpu_process_checks_passed',
                'gpu_state_passed', 'output_checked',
            ))
        ):
            return True
    return False


def run_pair(campaign: str, tier: str, pair: int, max_attempts: int = 3) -> bool:
    acquisition = f'{campaign}-{tier}'
    for attempt in range(1, max_attempts + 1):
        if current_success(acquisition, pair):
            log(f'{acquisition} pair {pair:02d}: current hash-matched result already present')
            return True
        wait_for_admission()
        command = [
            sys.executable, str(RUNNER), campaign, tier,
            '--only-pairs', str(pair), '--retries', '0',
        ]
        log(f'{acquisition} pair {pair:02d}: start one lock-bounded acquisition, try {attempt}')
        result = subprocess.run(command, text=True, capture_output=True)
        if result.stdout.strip():
            log(result.stdout.strip().replace('\n', ' | '))
        if result.stderr.strip():
            log(f'{acquisition} pair {pair:02d} stderr: {result.stderr.strip()}')
        if current_success(acquisition, pair):
            log(f'{acquisition} pair {pair:02d}: publishable current-hash result')
            return True
        log(f'{acquisition} pair {pair:02d}: attempt {attempt} did not publish (exit {result.returncode})')
        time.sleep(30)
    return False


def current_reports(acquisition: str, pair_count: int) -> list[Path]:
    return [
        Path(item)
        for pair in range(pair_count)
        if current_success(acquisition, pair)
        for item in json.loads((ROOT / 'reports' / acquisition / 'successful-pairs.json').read_text())
        if Path(item).name[:7] == f'pair-{pair:02d}'
    ]


def make_summary(tier: str) -> Path | None:
    aa = current_reports(f'aa-{tier}', 20)
    threeway = current_reports(f'threeway-{tier}', 10)
    if len(aa) != 20 or len(threeway) != 10:
        log(f'{tier}: cannot summarize exact-hash matrix ({len(aa)}/20 A/A, {len(threeway)}/10 three-build)')
        return None
    out = ROOT / 'reports' / f'threeway-{tier}-summary-current.json'
    command = [sys.executable, str(REPORTER), '--aa', *map(str, aa), '--threeway', *map(str, threeway), '--out', str(out)]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.stdout.strip():
        log(f'{tier} summary: ' + result.stdout.strip().replace('\n', ' | '))
    if result.returncode:
        log(f'{tier} summary failed: {result.stderr.strip()}')
        return None
    return out


def run_cause_control() -> bool:
    config_path = ROOT / 'configs/cause-control-typical/pair-00.json'
    config = json.loads(config_path.read_text())
    out_root = ROOT / 'reports/cause-control-typical'
    out_root.mkdir(parents=True, exist_ok=True)
    expected = {
        (side.get('role'), side.get('revision'), side.get('binary_sha256'))
        for side in config.get('sides', [])
    }
    for existing_out in sorted(out_root.glob('pair-00-try-[0-9][0-9]')):
        report_path = existing_out / 'report.json'
        if not report_path.exists():
            continue
        report = json.loads(report_path.read_text())
        recorded = report.get('config', {})
        actual = {
            (side.get('role'), side.get('revision'), side.get('binary_sha256'))
            for side in recorded.get('sides', [])
        }
        if actual == expected and recorded.get('expected_driver_sha256') == config.get('expected_driver_sha256') and report.get('publishable') is True:
            log('cause checkpoint: current-hash result already present')
            return True
    existing_attempts = [
        int(path.name.rsplit('-try-', 1)[1])
        for path in out_root.glob('pair-00-try-[0-9][0-9]')
        if path.is_dir()
    ]
    first_attempt = max(existing_attempts, default=0) + 1
    for attempt in range(first_attempt, first_attempt + 3):
        out = out_root / f'pair-00-try-{attempt:02d}'
        report_path = out / 'report.json'
        wait_for_admission()
        command = [
            'flock', '-n', '-x', BENCH,
            'flock', '-n', '-x', GPU,
            'env', f'CRAFT_JOURNEYS_HARNESS_BIN={HARNESS}',
            sys.executable, str(LEASE), str(config_path), str(out),
        ]
        log(f'cause checkpoint: start one lock-bounded acquisition, try {attempt}')
        result = subprocess.run(command, text=True, capture_output=True)
        if result.stdout.strip():
            log(result.stdout.strip().replace('\n', ' | '))
        if result.stderr.strip():
            log(f'cause checkpoint stderr: {result.stderr.strip()}')
        if report_path.exists():
            report = json.loads(report_path.read_text())
            recorded = report.get('config', {})
            actual = {
                (side.get('role'), side.get('revision'), side.get('binary_sha256'))
                for side in recorded.get('sides', [])
            }
            if actual == expected and recorded.get('expected_driver_sha256') == config.get('expected_driver_sha256') and report.get('publishable') is True:
                log('cause checkpoint: publishable current-hash result')
                return True
        log(f'cause checkpoint: attempt {attempt} did not publish (exit {result.returncode})')
        time.sleep(30)
    return False


def needs_cause(summary: Path | None) -> bool:
    if summary is None:
        return False
    data: dict[str, Any] = json.loads(summary.read_text())
    return any(
        row.get('tier') in {'typical', 'heavy'}
        and row.get('phase') == 'warm'
        and row.get('metric') == 'stroke total'
        and row.get('label') in {'brush-500px-soft', 'brush-canvas-width-soft'}
        and row.get('left_role') == 'a'
        and row.get('right_role') == 'c'
        and row.get('aa_gate') == 'PASS'
        and row.get('ci95', [0, 0])[0] > 1.0
        for row in data.get('rows', [])
    )


def main() -> int:
    stages = [
        ('aa', 'typical', range(20)),
        ('threeway', 'typical', range(10)),
        ('aa', 'heavy', range(20)),
        ('threeway', 'heavy', range(10)),
    ]
    missing = []
    for campaign, tier, pairs in stages:
        for pair in pairs:
            if not run_pair(campaign, tier, pair):
                missing.append(f'{campaign}-{tier}:{pair:02d}')
        if not backup(f'Exact-hash {campaign}-{tier} stage checkpoint; retain successful and failed attempts.'):
            missing.append(f'nas-backup:{campaign}-{tier}')
    typical = make_summary('typical')
    heavy = make_summary('heavy')
    if needs_cause(typical) or needs_cause(heavy):
        if not run_cause_control():
            missing.append('cause-control-typical:00')
        if not backup('Cause checkpoint and exact-hash 315b summary reports.'):
            missing.append('nas-backup:cause-control')
    else:
        log('cause checkpoint skipped: exact-hash typical matrix did not show a gated upstream win on a large brush')
    if not backup('Final exact-hash 315b PhotoCraft research reports, summaries and logs.'):
        missing.append('nas-backup:final')
    if missing:
        log('campaign refresh incomplete: ' + ', '.join(missing))
        return 1
    log('campaign refresh complete')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
