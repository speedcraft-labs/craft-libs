import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--aa',type=Path,required=True);p.add_argument('--additional-aa',type=Path,nargs='*',default=[]);p.add_argument('--comparison',type=Path,nargs='+',required=True);p.add_argument('--slowdown',type=Path);args=p.parse_args();k=Path(__file__).parent
read=lambda path:json.loads(path.read_text())
aa=read(args.aa);reports=[read(x) for x in args.comparison]
fmt=lambda x:f'{x:.2f}' if x is not None else 'uncalibrated'
lines=['User-visible results pending editorial interpretation. Ratio = exp(median log paired-session median(point)/median(main)); above 1 favors fork main. Pooled medians/p95 are descriptive and need not have this ratio. All latencies are ms. Cold means first timed use after setup, warm means measured repeats; OS/shader caches are not flushed.','', 'A/A: identical current-main commit, two separately clean-built binaries, contiguous AB/BA pairs. 95% CI resamples whole paired sessions. MDE is approximate alpha .05 / power .80 sensitivity, not the CI half-width.','', '| Action / state | Ratio | 95% CI | Ordinary paired 95% CI | Half-width % | Minimum detectable effect % | Allowed half-width % | Gate |','|---|---:|---:|---:|---:|---:|---:|---|']
for index,control in enumerate([aa,*[read(path) for path in args.additional_aa]]):
 if index:
  lines+=['', 'A/A calibration: '+', '.join(sorted({r['tier'] for r in control['rows']})), '', '| Action / state | Ratio | 95% CI | Ordinary paired 95% CI | Half-width % | Minimum detectable effect % | Allowed half-width % | Gate |','|---|---:|---:|---:|---:|---:|---:|---|']
 for r in control['rows']:
  lines.append(f"| {r['action']} / {r['phase']} | {r['speedup']:.3f} | {r['ci95'][0]:.3f}–{r['ci95'][1]:.3f} | {r['ordinary_ci95'][0]:.3f}–{r['ordinary_ci95'][1]:.3f} | {r['half_width_pct']:.2f} | {fmt(r['minimum_detectable_effect_pct'])} | {r['threshold_pct']} | {'PASS' if r['aa_pass'] else 'FAIL'} |")
if args.slowdown:
 slow=read(args.slowdown)
 if slow['config'].get('test_quit_delay_ns') is not None:
  proof=subprocess.check_output(['python3',str(k/'validate-quit-slowdown.py'),str(args.slowdown)],text=True)
  lines+=['',proof]
 else:
  r=next(x for x in slow['rows'] if x['action']=='switch' and x['phase']=='warm')
  delays=[x['evidence']['test_delay'] for s in slow['sessions'] if s['side']=='main' for x in s['samples'] if x['action']=='switch' and not x['warmup']]
  import statistics
  lines+=['',f"Deliberate slowdown: requested {delays[0]['requested_ms']:.3f} ms (10% of calibrated warm switch); actual median queued delay {statistics.median(d['actual_delay_ns'] for d in delays)/1e6:.3f} ms. Ratio {r['speedup']:.3f}, CI {r['ci95'][0]:.3f}–{r['ci95'][1]:.3f}: **{r['verdict']}**."]
for report in reports:
 for tier in sorted({r['tier'] for r in report['rows']}):
  lines+=['',f'LightCraft: {tier}. Upstream is descriptive only. MDE cells show A/A calibration / current-comparison approximate MDE; a noisier comparison is not assigned the calibration precision.', '', '| Action / state | Point median/p95 | Main median/p95 | Ratio (95% CI) | Minimum detectable effect % (AA/current) | Upstream median/p95 | Verdict |','|---|---:|---:|---:|---:|---:|---|']
  for r in report['rows']:
   if r['tier']!=tier:continue
   def cell(side):
    s=r['sides'].get(side);return f"{s['median_ns']/1e6:.2f}/{s['p95_ns']/1e6:.2f}" if s else 'not measured'
   lines.append(f"| {r['action']} / {r['phase']} | {cell('point')} | {cell('main')} | {r['speedup']:.3f} ({r['ci95'][0]:.3f}–{r['ci95'][1]:.3f}) | {('width only: ' if r.get('calibration_contains_unity') is False else '')+fmt(r['minimum_detectable_effect_pct'])}/{fmt(r['estimated_mde_pct'])} | {cell('upstream')} | {r['verdict']} |")
variance=subprocess.check_output(['python3',str(k/'analyze-variance.py'),str(k.parent/'paired-typical-50-resilient-v2/report.json'),str(k/'aa-v4-control-continuation-2-2/report.json'),str(args.aa)],text=True)
lines+=['',variance,'','Validation: `cargo test -p craft-journeys` (see exact current log); earlier full local workspace run: 3,835 passed, 127 ignored, zero failures. Post-rebase run hit H.264 reset and proof timing assertions; both baseline comparisons and exact logs are reported separately. Three strict lints reproduce on integration in untouched files. No trimming; failed/rejected attempts remain retained.','', 'Payload limit: import-1262 is 1,262 distinct CC0 camera originals. It approximates the count in #367, not its camera/storage distribution. #832 is a different Lightroom-catalog / 1.1 TB USB/exFAT workflow with 38,545 photos and ~25 minutes; it is out of scope.']
lines += ['', (k/'validation-summary.md').read_text()]
(k/'final-tables.md').write_text('\n'.join(lines)+'\n')
chartdata={'aa':aa['rows'],'comparisons':[r for report in reports for r in report['rows']]}
html='''<style>.controls{display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 16px}select{background:var(--secondary);color:var(--foreground);border:1px solid var(--border);border-radius:6px;padding:6px}p{color:var(--muted-foreground);font-size:13px}svg{width:100%;height:390px}text{fill:var(--foreground);font:12px var(--font-sans)}.tick{fill:var(--muted-foreground)}.axis{stroke:var(--border)}.unity{stroke:var(--foreground);stroke-dasharray:4 4}</style>
<div class="controls"><label>Tier <select id="tier"></select></label><label>State <select id="state"><option>warm</option><option>cold</option></select></label></div>
<svg id="plot" viewBox="0 0 712 390" role="img" aria-label="LightCraft median ratios and 95 percent confidence intervals"></svg>
<p>Point / main ratio; right of 1 favors main. Intervals resample whole paired sessions. Upstream observations are descriptive. MDE is approximate A/A sensitivity at 80% power. Rejected A/A controls make a row descriptive only; its interval width is not validated sensitivity.</p>
<script>const D=DATA;const tiers=[...new Set(D.comparisons.map(x=>x.tier))];tier.innerHTML=tiers.map(x=>`<option>${x}</option>`).join('');function draw(){const rows=D.comparisons.filter(x=>x.tier===tier.value&&x.phase===state.value);const lo=Math.min(.85,...rows.map(r=>r.ci95[0]))*.97,hi=Math.max(1.15,...rows.map(r=>r.ci95[1]))*1.03;const x=v=>145+(Math.log(v)-Math.log(lo))/(Math.log(hi)-Math.log(lo))*350;let s=`<line class="unity" x1="${x(1)}" x2="${x(1)}" y1="20" y2="330"/>`;for(let v=0;v<=4;v++){let a=Math.exp(Math.log(lo)+(Math.log(hi)-Math.log(lo))*v/4);s+=`<line class="axis" x1="${x(a)}" x2="${x(a)}" y1="330" y2="336"/><text class="tick" text-anchor="middle" x="${x(a)}" y="355">${a.toFixed(2)}×</text>`}rows.forEach((r,i)=>{let y=42+i*43,c=r.calibration_contains_unity===false?'var(--muted-foreground)':r.ci95[0]>1?'var(--success)':r.ci95[1]<1?'var(--destructive)':'var(--chart-1)';s+=`<text x="0" y="${y+4}">${r.action}</text><line x1="${x(r.ci95[0])}" x2="${x(r.ci95[1])}" y1="${y}" y2="${y}" stroke="${c}" stroke-width="3"/><circle cx="${x(r.speedup)}" cy="${y}" r="5" fill="${c}"/><text x="510" y="${y+4}">${r.speedup.toFixed(3)}× · MDE ${r.minimum_detectable_effect_pct==null?'unknown':r.minimum_detectable_effect_pct.toFixed(1)+'%'}</text>`});plot.innerHTML=s}tier.onchange=state.onchange=draw;draw()</script>'''.replace('DATA',json.dumps(chartdata,separators=(',',':')))
(k/'latency-ratios.html').write_text(html)
print(k/'final-tables.md');print(k/'latency-ratios.html')
