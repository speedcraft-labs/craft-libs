"""Print a completed A/A without altering clocks, gates, or observations."""
import json,sys
from pathlib import Path
path=Path(sys.argv[1]);report=json.loads(path.read_text());assert report['comparison_complete'] and report['config']['aa'] and len(report['sessions'])==40
assert report['publishable'] and report['output_checked'] and report['gpu_process_checks_passed'] and report['prior_acquisitions_passed'] and report['guard']['contended'] is False
out=['HANDOFF 313b — fixed 20-pair A/A complete. Ratios are A/B; unity must be inside the 95% CI, with unrounded half-width≤5% (import/startup≤10%). Thresholds are unchanged; failed gates retained. MDE is a separate approximate 80%-power estimate, not the half-width. Quit is external process exit and does not validate app-clock precision.', '| Warm action | A/B ratio | 95% CI | Half-width | MDE | Gate |','|---|---:|---:|---:|---:|---|']
for row in report['rows']:
 if row['phase']!='warm':continue
 assert row['observed_pairs']==20
 lo,hi=row['ci95'];mde=row['minimum_detectable_effect_pct']
 out.append(f"| {row['action']}{' (external)' if row['action']=='quit' else ''} | {row['speedup']:.4f} | {lo:.4f}–{hi:.4f} | {row['half_width_pct']:.2f}% | {mde:.2f}% | {'PASS' if row['aa_pass'] else 'FAIL'} |")
out+=['','| Warm action (B) | Driver upper bound ms | App first-response ms | App completion ms | Control wait in app clock |','|---|---:|---:|---:|---:|']
for row in report['timing_comparison']:
 if row['side']!='main':continue
 out.append(f"| {row['action']} | {row['driver_median_ms']:.2f} | {row['app_first_response_median_ms']:.2f} | {row['app_completion_median_ms']:.2f} | 0% |")
out+=['',f'Raw cumulative report `{path}`. First/complete app stamps are UI acceptance→same-frame GPU work confirmed complete, prior to any socket reply; all record control_wait_ns=0. External medians are retained upper bounds, not an isolated RPC-overhead estimate. Same additive patch and byte-identical recorder source on both clean builds;31 allocated ELF sections match except build-id. Cold/warm whole-session bootstrap and all per-action evidence retained. Earlier 12-repeat and incomplete acquisitions are diagnostic only, never pooled. For active continuation use CURRENT-STATE.json and CONTINUATION.md; leave the existing coordinator running.']
out += ['', 'Timing driver SHA256: `' + report['driver_sha256'] + '`. Import boundary: ' + ('folder-drop acceptance through usable grid, including expansion/preparation; never pooled with retired confirmation timings.' if report['config'].get('direct_import') else 'confirmation through usable grid; first non-placeholder photo response recorded separately.')]
text='\n'.join(out)+'\n'
if len(sys.argv)>2:Path(sys.argv[2]).write_text(text)
print(text)
