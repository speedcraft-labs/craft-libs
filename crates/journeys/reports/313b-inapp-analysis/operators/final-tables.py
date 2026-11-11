"""Render complete, unchanged cohort evidence; no outlier filters or gate changes."""
import json,statistics,sys
from pathlib import Path
root=Path(__file__).parent.parent
sys.path.insert(0,'/jobs/work/speedcraft-labs/wt/313b-libs/crates/journeys/scripts')
from lightcraft_session_report import markdown
from mde_floor import corrected_rows
paths=json.loads((root/'ALL-PHASES.json').read_text())
reports={k:json.loads(Path(paths[k]).read_text()) for k in ('aa','slowdown','real50','heavy_aa','heavy_real')}
for name,r in reports.items():
 assert r['comparison_complete'] and r['output_checked'] and r['gpu_process_checks_passed'] and r['prior_acquisitions_passed'] and r['guard']['contended'] is False,(name,'incomplete or unclean')
 assert r['publishable'],(name,'not publishable')
for key,calibration in [('slowdown','aa'),('real50','aa'),('heavy_real','heavy_aa')]:
 reports[key]['rows']=corrected_rows(reports[key],reports[calibration])
 (root/(key+'-corrected-analysis.json')).write_text(json.dumps({'raw_report':paths[key],'calibration':paths[calibration],'rows':reports[key]['rows'],'correction':'comparison-count-scaled A/A floor and current CI-derived floor; raw observations/CI/verdicts unchanged'},indent=2)+'\n')
aa_rows=reports['aa']['rows']+reports['heavy_aa']['rows'];real_rows=reports['real50']['rows']+reports['heavy_real']['rows']
warm_aa=[r for r in aa_rows if r['phase']=='warm'];warm_real=[r for r in real_rows if r['phase']=='warm']
def ratio(r):return f"{r['speedup']:.4f} ({r['ci95'][0]:.4f}–{r['ci95'][1]:.4f})"
def effect(r):
 m=r.get('minimum_detectable_effect_pct');return f'{m:.2f}%' if m is not None else 'uncalibrated'
def name(r):return ('1259 import' if r['tier']=='import-1259' else r['action'])+(' (external)' if r['action']=='quit' else '')
def aa_table(rows):
 out=['| Warm action | A/B ratio (95% CI) | Half-width | MDE¹ | Gate |','|---|---:|---:|---:|---|']
 for r in rows:
  assert r['observed_pairs']==20
  passed=r['aa_pass'] and r['observed_pairs']==20
  out.append(f"| {name(r)} | {ratio(r)} | {r['half_width_pct']:.2f}% | {effect(r)} | {'PASS' if passed else 'FAIL'} |")
 return '\n'.join(out)
def real_table(rows):
 out=['| Warm action | Fork point ms | Fork main ms | Upstream ms² | Point/main ratio (95% CI) | Verdict; MDE¹ |','|---|---:|---:|---:|---:|---|']
 for r in rows:
  med=lambda side:f"{r['sides'][side]['median_ns']/1e6:.2f}"
  out.append(f"| {name(r)} | {med('point')} | {med('main')} | {med('upstream')} | {ratio(r)} | {r['verdict']}; {effect(r)} |")
 return '\n'.join(out)
comparison=[]
for r in (reports['aa'],reports['heavy_aa']):
 comparison.extend(x for x in r['timing_comparison'] if x['side']=='main')
control=['| Warm action | External driver upper bound ms³ | App first response ms | App completion ms | Control wait in app clock |','|---|---:|---:|---:|---:|']
for r in comparison:
 control.append(f"| {('1259 import' if r['tier']=='import-1259' else r['action'])} | {r['driver_median_ms']:.2f} | {r['app_first_response_median_ms']:.2f} | {r['app_completion_median_ms']:.2f} | 0% |")
# Startup uses entry point -> photo frame; never attribute its external excess to RPC alone.
starts=[x for s in reports['aa']['sessions'] if s['side']=='main' for x in s['startup_samples'] if x['phase']=='warm']
control.append(f"| startup | {statistics.median(x['driver_duration_ns'] for x in starts)/1e6:.2f} | — | {statistics.median(x['in_app']['duration_ns'] for x in starts)/1e6:.2f} | 0% |")
slow=next(r for r in reports['slowdown']['rows'] if r['action']=='switch' and r['phase']=='warm')
dose=json.loads((root/'switch-dose-result.json').read_text())
app_rows=[r for r in warm_aa if r['action']!='quit']
pass_count=sum(r['aa_pass'] for r in app_rows)
power5=[name(r) for r in app_rows if r['aa_pass'] and r['minimum_detectable_effect_pct']<=5]
lead=(f"With20 paired sessions, a5% change is detectable at the stated approximate80% power for {', '.join(power5)}." if power5 else 'This fixed20-pair experiment does not establish80% power to detect a5% change for any app action.')
lead+=f" The specified A/A precision gate passes {pass_count}/{len(app_rows)} app/tier rows; failed gates are retained below. The app clocks contain0% control waiting by construction. The10-pair real comparisons have their own larger count-adjusted sensitivity floors shown below."
sections=[lead,'HANDOFF 313b — final fixed cohorts. Times are UI-thread acceptance to GPU work for the first reflecting frame confirmed complete. This is an enabled worker callback timestamp, an upper bound affected by scheduling; it is not scanout or swapchain-present return. Startup starts at native entry. Quit is separately labelled external process exit.',
'20 independent-build pairs per A/A tier, AB/BA primary order; two warmups. Typical50 uses6 measured repetitions/action and4 measured exposure steps/repetition. Import1259 uses2 measured repetitions and import-only scope. Real comparisons use10 primary pairs plus separately acquired upstream samples. Bootstrap resamples whole paired sessions, stratified by fixed order;4000 resamples, seed313. Cold means first use within each session, not OS/shader-cache flushing.',
aa_table(warm_aa),'¹ MDE assumes two-sided alpha=.05 and80% power on log latency. A/A uses its CI width; comparison MDE is the larger of its current CI-derived estimate and the A/A floor scaled by sqrt(A/A pairs/comparison pairs) on log scale. Gates use unrounded values. A narrow CI alone does not prove5% power. An A/A CI excluding1 rejects that comparison; its numerical MDE is only a width diagnostic, not valid calibration. Gates require unity in CI and half-width≤5%, or≤10% for import/startup. Thresholds are unchanged.',
'External versus app times from the same final A/A runs:', '\n'.join(control),'³ The external column retains driver send/capture timing. Its difference from app time includes transport, verification and endpoint boundaries; it is not an isolated estimate of RPC overhead. The app record is read once on the socket thread after completion, without UI dispatch/repaints or timed inspect polling. Import starts at confirmation and completes when import/scan are done and every visible thumbnail is shown. All catalog filenames and every virtualized page are verified outside timing. Switch retains first response and full-quality completion.',
f"Physical slowdown: switch {ratio(slow)}, verdict **{slow['verdict']}**. Fixed app-side delay={dose['requested_delay_ns']/1e6:.3f}ms,10% of an independent contemporary2-pair untreated pilot. Actual median delay={dose['actual_delay_median_ns']/1e6:.3f}ms, {dose['actual_dose_control_pct']:.2f}% of contemporaneous untreated test switch latency. Pilot excluded; inference uses10 independent interleaved pairs. Both binaries contain identical delay code; no duration arithmetic is substituted for real sleeping.",
real_table(warm_real),'² Upstream tip is a descriptive column acquired separately; no upstream speedup verdict is inferred. The primary fork point/main pair remains contiguous in one acquisition. Upstream developed-pixel equivalence is retained per row in JSON. Every “no measurable change” carries the conservative count-adjusted A/A/current-CI MDE; rejected A/A controls stay descriptive.',
'Pinned app revisions: fork point fc97c728644d399843d8201f83d25ccf81b89669; fork main d97557e02188f6466c448773d98127222e702daf; upstream c2e9c456c9bfdcd4d56d8b88b8a5b546b69a3223. All builds use common patch44fe9373aab994e3db26f2e3f95683bcc827fe84e3717709036426430bfbc8c9. Forward application on pristine source succeeds on all three revisions; both recorder source files are byte-identical across all builds. A/A binaries come from separate clean builds and have identical.text/.rodata/.data.rel.ro. Incompatible patch/provenance/clock checks fail loudly; update one common patch and rebuild every side rather than comparing different recorders.',
'Each primary pair ran under bench.lock then exclusive gpu.lock then scripts/bench-run on reserved CPUs22–27, with an840s hard lease; all binaries were built beforehand and copied outside targets. GPU graphics1350MHz/memory7000MHz, mode1 checked before each action; foreign GPU processes/incorrect clocks/idle timeouts reject samples.1259-tier admissions defer when benchmark waiters exist. No successful whole pair is trimmed. Superseded12-repeat observations and incomplete budget attempts remain diagnostic and are not pooled into final cohorts.',
'Full cold/warm A/A tables:',markdown(aa_rows),'Full cold/warm real tables:',markdown(real_rows),
'Validation: cargo test -p craft-journeys passes (3 Rust,45 Python checks; optional Pillow checks skip cleanly if absent). Full craft-libs workspace3835 passed,0 failed,127 ignored. Three recorder CPU tests and socket-reader no-dispatch/no-repaint regression pass; app/UI strict clippy passes. Both PR CI suites green at app62b1627c and libs65838523. The local app workspace had6365 passing tests and4 denoise GPU failures; clean main reproduces the same4 under matching features (65pass,4fail,11ignored); targeted UI32/32passes. A prior full UI executable exited with SIGSEGV after32passing tests; targeted clean-main UI did not reproduce that exit. Unchanged full-libs shader clippy errors are recorded separately.',
'Raw paths and immutable provenance: ALL-PHASES.json, EVIDENCE-INDEX.json, build-provenance-r3.json, patch-pristine-proof-r3.json, recorder-source-parity.json, aa-code-sections.json and per-acquisition logs under keep/313b-inapp-timing. Supplemental scheduling diagnostics are descriptive and never filter observations. Passing images are reduced to hashes after final review; failing/disputed images alone retained. Final NAS path and final PR heads/merge states will be appended by the operator after review.'
]
(root/'FINAL-TABLES.md').write_text('\n\n'.join(sections)+'\n')
(root/'FINAL-SHORT-TABLES.md').write_text('\n\n'.join([lead,aa_table(warm_aa),real_table(warm_real)])+'\n')
(root/'chart-data.json').write_text(json.dumps(dict(aa=aa_rows,real=real_rows),indent=2)+'\n')
print('\n\n'.join([lead,aa_table(warm_aa),real_table(warm_real)]))
