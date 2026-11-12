"""Render fixed cohorts unchanged; keep the two import boundaries separate."""
import copy
import hashlib
import json
import statistics
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, '/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts')
from lightcraft_session_report import markdown
from mde_floor import corrected_rows

paths = json.loads((root / 'ALL-PHASES.json').read_text())
keys = ('aa', 'slowdown', 'real50', 'heavy_aa', 'heavy_real',
        'legacy_heavy_aa', 'legacy_heavy_real_partial')
reports = {key: json.loads(Path(paths[key]).read_text()) for key in keys}
for name, report in reports.items():
    assert report['output_checked'] and report['gpu_process_checks_passed']
    assert report['prior_acquisitions_passed'] and report['guard']['contended'] is False
    if name == 'legacy_heavy_real_partial':
        assert not report['comparison_complete'] and not report['publishable']
        assert len(report['sessions']) == 15
        assert all(row['observed_pairs'] == 5 and row['verdict'] == 'insufficient paired sessions'
                   for row in report['rows'])
    elif name == 'real50':
        assert report['comparison_complete'] and report['descriptive_publishable']
        assert not report['publishable'] and not report['primary_output_equivalent']
        assert all(row['verdict'] == 'outputs differ; descriptive only' for row in report['rows'])
    else:
        assert report['comparison_complete'] and report['publishable'], name
    direct = name in ('heavy_aa', 'heavy_real')
    cohort = 'direct_import' if direct else 'typical'
    assert report['driver_sha256'] == paths['driver_sha256_by_cohort'][cohort], name
    if direct:
        assert all(s['import_boundary'] == 'folder-drop-to-usable-grid' for s in report['sessions'])

for name, calibration in (('slowdown', 'aa'), ('real50', 'aa'), ('heavy_real', 'heavy_aa')):
    reports[name]['rows'] = corrected_rows(reports[name], reports[calibration])
    (root / (name + '-corrected-analysis.json')).write_text(json.dumps(dict(
        raw_report=paths[name], calibration=paths[calibration], rows=reports[name]['rows'],
        correction='max(current CI MDE, count-adjusted A/A MDE); observations/CI/verdicts unchanged'),
        indent=2) + '\n')

def rows(name, phase='warm'):
    return [r for r in reports[name]['rows'] if r['phase'] == phase]

def display_name(row, cohort):
    if row['tier'] == 'import-1259':
        return '1259 import (' + ('folder drop' if cohort in ('heavy_aa', 'heavy_real') else 'confirmation, legacy') + ')'
    return row['action'] + (' (external)' if row['action'] == 'quit' else '')

def ratio(row):
    return f"{row['speedup']:.4f} [{row['ci95'][0]:.4f}, {row['ci95'][1]:.4f}]"

def effect(row):
    value = row.get('minimum_detectable_effect_pct')
    return f'{value:.2f}%' if value is not None else 'uncalibrated'

def aa_table(cohorts):
    out = ['| Warm action | A/B ratio [95% CI] | Half-width | MDE¹ | Gate |',
           '|---|---:|---:|---:|---|']
    for cohort in cohorts:
        for row in rows(cohort):
            assert row['observed_pairs'] == 20
            out.append(f"| {display_name(row, cohort)} | {ratio(row)} | {row['half_width_pct']:.2f}% | {effect(row)} | {'PASS' if row['aa_pass'] else 'FAIL'} |")
    return '\n'.join(out)

def real_table(cohorts):
    out = ['| Warm action | Fork point ms | Fork main ms | Upstream ms² | Point/main ratio [95% CI] | Verdict; MDE¹ |',
           '|---|---:|---:|---:|---:|---|']
    for cohort in cohorts:
        for row in rows(cohort):
            med = lambda side: f"{row['sides'][side]['median_ns']/1e6:.2f}"
            out.append(f"| {display_name(row, cohort)} | {med('point')} | {med('main')} | {med('upstream')} | {ratio(row)} | {row['verdict']}; {effect(row)} |")
    return '\n'.join(out)

control = ['| Warm action | External driver upper bound ms³ | App first response ms | App completion ms | Control wait in app clock |',
           '|---|---:|---:|---:|---:|']
for cohort in ('aa', 'heavy_aa', 'legacy_heavy_aa'):
    for row in reports[cohort]['timing_comparison']:
        if row['side'] != 'main':
            continue
        assert row['control_wait_share_pct'] == 0
        control.append(f"| {display_name(row, cohort)} | {row['driver_median_ms']:.2f} | {row['app_first_response_median_ms']:.2f} | {row['app_completion_median_ms']:.2f} | 0% |")
starts = [x for s in reports['aa']['sessions'] if s['side'] == 'main'
          for x in s['startup_samples'] if x['phase'] == 'warm']
control.append(f"| startup | {statistics.median(x['driver_duration_ns'] for x in starts)/1e6:.2f} | {statistics.median(x['in_app']['first_response_ns'] for x in starts)/1e6:.2f} | {statistics.median(x['in_app']['duration_ns'] for x in starts)/1e6:.2f} | 0% |")

app_rows = [(cohort, row) for cohort in ('aa', 'heavy_aa') for row in rows(cohort) if row['action'] != 'quit']
pass_count = sum(row['aa_pass'] for _, row in app_rows)
power5 = [display_name(row, cohort) for cohort, row in app_rows
          if row['aa_pass'] and row['minimum_detectable_effect_pct'] <= 5]
lead = ('On Agentbox, this 20-pair experiment supports detecting a 5% change at the stated approximate 80% power for '
        + ', '.join(power5) + '.' if power5 else
        'This 20-pair experiment does not establish 80% power to detect a 5% change in any app action.')
lead += (f' The specified A/A precision gate passes {pass_count}/{len(app_rows)} current app/tier rows; '
         'failed gates are retained. Control wait is 0% of every in-app interval by construction. '
         'The retired confirmation-import cohort is reported separately and is never pooled with folder-drop imports.')
slow = next(row for row in rows('slowdown') if row['action'] == 'switch')
dose = json.loads((root / 'switch-dose-result.json').read_text())
slow_table = '\n'.join(['| Physical slowdown | Control ms | Delayed ms | Actual dose | A/B ratio [95% CI] | Verdict | MDE¹ |', '|---|---:|---:|---:|---:|---|---:|', f"| switch | {slow['sides']['point']['median_ns']/1e6:.2f} | {slow['sides']['main']['median_ns']/1e6:.2f} | {dose['actual_dose_control_pct']:.2f}% | {ratio(slow)} | {slow['verdict']} | {effect(slow)} |"])
legacy = json.loads((root / 'legacy-confirmation-retirement.json').read_text())
resources = []
for p in sorted(root.glob('*.incomplete.json')):
    value = json.loads(p.read_text())
    resources.append(dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), details=value))
(root / 'final-incomplete-attempt-index.json').write_text(json.dumps(resources, indent=2) + '\n')

sections = [lead,
    'HANDOFF 313b — final fixed cohorts. App times run from UI-thread acceptance through confirmation that GPU work for the first qualifying content frame is complete. A callback attaches to the actual egui frame encoder without forking eframe. Its timestamp is an upper bound affected by enabled poll-worker scheduling; it is not scanout or swapchain-present return. Pending-work snapshots describe the qualifying frame when assembled, before that callback. Startup begins at native entry and ends with an active full-quality photo frame (or the explicitly empty grid); quit is external process exit.',
    'Each current A/A cohort has 20 independent-build primary pairs, interleaved AB/BA, with two warmups. Typical50 has six measured repetitions/action and four measured exposure steps/repetition. Import1,259 has two measured repetitions and import-only scope. Each current real comparison has ten contiguous primary pairs plus ten separately acquired upstream sessions. Bootstrap resamples whole paired sessions, stratified by fixed order; 4,000 resamples, seed313. Cold means first use within a session, without flushing OS/shader caches.',
    aa_table(('aa', 'heavy_aa')),
    '¹ MDE is the approximate detectable change at two-sided alpha=.05 and 80% power on log latency. Comparisons use the larger of their current CI-derived floor and the accepted A/A floor scaled by sqrt(A/A pairs/comparison pairs). A narrow interval alone does not prove 5% power. If the A/A CI excludes1, comparison verdicts are rejected and a numerical CI-width MDE is diagnostic only. Gates require unity in the CI and half-width ≤5%, or ≤10% for import/startup; thresholds are unchanged and gates use unrounded values.',
    'Same-run external and native medians:', '\n'.join(control),
    '³ External time retains driver send/capture boundaries. Excess over native time includes transport, verification and boundary differences; it is not isolated RPC overhead. After a tagged command the driver makes one native record wait on the socket thread, without dispatching to the UI or repainting. No inspect-poll result enters an app interval. Idle gates require empty task/queue/activity state for one second plus the authoritative native idle check; timeout fails the sample.',
    'There are two explicitly different import protocols. Typical50 and the retired heavy cohort start at confirmation after review preparation. The current1,259 cohort starts at folder-drop acceptance with the existing importDroppedDirectly setting, so directory expansion/preparation is inside its clock. Both end after import/scan complete and every visible thumbnail is shown; exact catalogue names and all virtualized pages are verified outside timing. Empty-grid checks before direct drops prevent prior thumbnails satisfying completion. These durations must not be compared as an app optimization. Switch records both first photo response and full-quality completion; export ends with its completed task/result frame.',
    f"Physical10% slowdown: switch {ratio(slow)}, **{slow['verdict']}**. App-side requested delay {dose['requested_delay_ns']/1e6:.3f}ms was10% of an independent two-pair untreated pilot. Actual median delay {dose['actual_delay_median_ns']/1e6:.3f}ms was {dose['actual_dose_control_pct']:.2f}% of contemporaneous test control latency. Pilot excluded; inference uses ten fresh interleaved pairs. Both binaries contain identical delay code; timestamps were never adjusted arithmetically.",
    slow_table,
    real_table(('real50', 'heavy_real')),
    '² The50-RAW defaults use processV4 at fork point andV7 at main/upstream. Their strict developed-pixel gate FAILED; publishable remains false and all those rows are descriptive only. Their numerical MDEs describe width and do not authorize a speed claim. Aliased acquisition roles were mapped to actual revision names only after timing; no durations changed. Import1,259 checks exact catalogue membership and every non-placeholder thumbnail, without asserting developed-pixel equality. Upstream is a descriptive column acquired separately, with no upstream speed verdict. Every “no measurable change” has a count-adjusted A/A/current-CI MDE; rejected controls stay descriptive.',
    'Retired reviewed-import protocol — all results retained separately:',
    aa_table(('legacy_heavy_aa',)), real_table(('legacy_heavy_real_partial',)),
    'The legacy real comparison has only five complete primary pairs and five upstream sessions, not the required ten. All fifteen complete sessions and all incomplete attempts remain archived. Its insufficient-session rows support no speed verdict. Repeated primary-pair840s budget expiries led to retiring that workflow at an acquisition boundary, without stopping a running process. A completed fork-point session lasted511.67s and included36,872 inspect calls,27,555 widget reads and181 screenshots. Those untimed lifecycle intervals include app waiting and transport, not an isolated cost decomposition. The fresh direct cohort starts from zero and is not pooled with any legacy observation.',
    'Pinned app revisions: fork point fc97c728644d399843d8201f83d25ccf81b89669; fork main d97557e02188f6466c448773d98127222e702daf; upstream c2e9c456c9bfdcd4d56d8b88b8a5b546b69a3223. Common recorder patch SHA25644fe9373aab994e3db26f2e3f95683bcc827fe84e3717709036426430bfbc8c9 applies forward on all three pristine sources. Both recorder files are byte-identical across builds. A/A executables are separate clean builds with identical allocated sections except the build-id. A patch/provenance mismatch fails; update the single adapter and rebuild every side before comparing. Timing driver hashes: ' + json.dumps(paths['driver_sha256_by_cohort'], sort_keys=True) + '.',
    'Each primary pair acquired bench.lock then exclusive gpu.lock then scripts/bench-run on reserved CPUs22–27, with an840s hard work lease and cleanup inside15minutes. Binaries were built beforehand and copied outside targets. GPU graphics1350MHz/memory7000MHz mode1 checked before actions; foreign processes, wrong clocks, idle timeouts or resource failures reject samples. Heavy-tier acquisition defers when benchmark waiters exist. Resource forecasts became advisory; a fixed30s allowance admits a new side and the unchanged hard lease is authoritative. No successful complete pair was trimmed. Superseded12-repeat runs, forecasts and incomplete attempts remain diagnostic; final-incomplete-attempt-index.json lists the retained resource failures. No foreign process was stopped.',
    "Residual typical A/A variation: preview session medians80.54–199.18ms; switch54.80–169.14ms. Within-side latency tracks app sharp-preview/render observations at approximately0.999 correlation despite matching photo, geometry, exposure sequence and cache paths, with empty completion pending lists. This places substantial variation inside app work rather than timed control polling, but does not isolate its cause. Warm MDE floors are20.18% and14.31%. Whole-session scheduling diagnostics include untimed work and supply context, not a causal partition.",
    'Legacy confirmation1,259 A/A failed:11.42% half-width,17.46% MDE. Session completion medians range517.55–1137.15ms onA and522.39–911.80ms onB, with30–32 completion frames and empty pending lists. First-response-to-completion gap is about516ms. Source allows four prepared batches to commit per host frame; six available CPUs give12files/batch, so1259files require at least27commitframes. This is consistent with a frame-paced app pipeline. Per-frame timestamps were not recorded, so varying frame stalls remain unresolved. See aa-import-1259-residual-variation.json; this evidence concerns the legacy boundary only.',
    'The fresh direct1,259 A/A passes its10% half-width gate at9.77%, with estimated MDE15.75%. Native completion medians are15.89/18.24s onA/B, while first-photo medians are0.103/0.109s. Session completion medians span15.35–79.41s onA and15.44–72.83s onB, with478–1265/479–1340 frames; all first-photo snapshots still show import work and all completion snapshots are empty. The spread lies after the first photo while the app continues expansion/probing/preparation and frame-paced commits. Source caps commits at4prepared batches per host frame. These observations locate the stage but do not causally partition CPU, disk, GPU, frame pacing or callback scheduling. All20pairs were retained with zero incomplete acquisitions. See aa-import-1259-direct-residual-variation.json, action-diagnostics.json and clock-isolation-proof.json; this broader folder-drop clock is never pooled with legacy confirmation.',
    'Full cold/warm current A/A tables:', markdown(reports['aa']['rows'] + reports['heavy_aa']['rows']),
    'Full cold/warm current real tables:', markdown(reports['real50']['rows'] + reports['heavy_real']['rows']),
    'Full cold/warm retired confirmation A/A:', markdown(reports['legacy_heavy_aa']['rows']),
    'Full cold/warm retired partial real:', markdown(reports['legacy_heavy_real_partial']['rows']),
    'Candidate craft-journeys:3Rust/55Python checks pass, including report-count sensitivity and direct-import boundary tests. Full craft-libs workspace baseline3835passed,0failed,127ignored. Three recorder CPU tests plus socket no-dispatch/no-repaint regression pass; app/UI strict clippy passes. Local app workspace6365passed with four denoise GPU failures reproduced on matching-feature clean main (65pass,4fail,11ignored). Targeted UI32/32 passes; an earlier full UI executable exited SIGSEGV after32passes, not reproduced by targeted clean-main UI. Unchanged full-libs shader clippy errors are separately recorded. Final source validation and PR states are appended after integration.',
    'Immutable reports/provenance: ALL-PHASES.json, EVIDENCE-INDEX.json, final-analysis-identity-proof.json, build-provenance-r3.json, patch-pristine-proof-r3.json, recorder-source-parity.json, aa-code-sections.json and acquisition logs. Passing image artifacts become hashes after final review; failing/disputed images are retained. Final NAS path and PR heads/checks/reviews are appended by the operator.'
]
(root / 'FINAL-TABLES.md').write_text('\n\n'.join(sections) + '\n')
(root / 'FINAL-SHORT-TABLES.md').write_text('\n\n'.join([
    lead, aa_table(('aa', 'heavy_aa')), real_table(('real50', 'heavy_real')),
    'Retired confirmation protocol (kept separately):', aa_table(('legacy_heavy_aa',)),
    real_table(('legacy_heavy_real_partial',))]) + '\n')
charts = {}
for key, cohorts in (('aa', ('aa', 'heavy_aa', 'legacy_heavy_aa')),
                     ('real', ('real50', 'heavy_real', 'legacy_heavy_real_partial'))):
    charts[key] = []
    for cohort in cohorts:
        for row in reports[cohort]['rows']:
            item = copy.deepcopy(row)
            item.update(display_label=display_name(row, cohort), cohort=cohort,
                        legacy=cohort.startswith('legacy_'))
            charts[key].append(item)
(root / 'chart-data.json').write_text(json.dumps(charts, indent=2) + '\n')
print((root / 'FINAL-SHORT-TABLES.md').read_text())
