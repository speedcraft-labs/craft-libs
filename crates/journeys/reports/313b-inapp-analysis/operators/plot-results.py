"""Standalone export figure plus a local, interactive inline forest chart."""
import json,math
from pathlib import Path
root=Path(__file__).parent.parent
data=json.loads((root/'chart-data.json').read_text())
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
matplotlib.rcParams.update({'svg.fonttype':'none','font.size':9})
fig,axes=plt.subplots(1,2,figsize=(13,5.3),layout='constrained')
for ax,key,title in zip(axes,('aa','real'),('A/A: independent clean builds','Real: fork point / fork main')):
 rows=[r for r in data[key] if r['phase']=='warm']
 for i,r in enumerate(rows):
  lo,hi=r['ci95'];ratio=r['speedup'];label=('1259 import' if r['tier']=='import-1259' else r['action'])+(' (external)' if r['action']=='quit' else '')
  color=('#287a48' if r['aa_pass'] else '#ba3444') if key=='aa' else '#276fa5'
  ax.errorbar(ratio,i,xerr=[[ratio-lo],[hi-ratio]],fmt='o',color=color,capsize=3)
  ax.text(1.01,i,f'{ratio:.3f} [{lo:.3f}, {hi:.3f}]',transform=ax.get_yaxis_transform(),va='center',fontsize=8)
 ax.set_yticks(range(len(rows)),[('1259 import' if r['tier']=='import-1259' else r['action'])+(' (external)' if r['action']=='quit' else '') for r in rows]);ax.invert_yaxis()
 ax.axvline(1,color='#777777',linestyle='--',linewidth=1);ax.set_xscale('log');ax.set_title(title);ax.set_xlabel('A/B ratio; >1 favors B (95% whole-session CI)');ax.grid(axis='x',alpha=.2)
fig.savefig(root/'latency-forest.png',dpi=180);fig.savefig(root/'latency-forest.svg');plt.close(fig)
(root/'plot-tool-version.json').write_text(json.dumps({'matplotlib':matplotlib.__version__},indent=2)+'\n')
html='''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;color:var(--foreground);font:14px var(--font-sans,system-ui)}
.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:18px}select{font:inherit;color:var(--foreground);background:var(--secondary);border:1px solid var(--border);border-radius:var(--radius);padding:6px 10px}label{display:flex;gap:8px;align-items:center}
section{margin:16px 0 24px}h3{font-size:15px;font-weight:600;margin:0 0 8px}p{color:var(--muted-foreground);font-size:12px;line-height:1.5;margin:8px 0}.scroll{overflow-x:auto}.chart{display:block;min-width:620px;width:100%}.label{fill:var(--foreground);font-size:12px}.detail{fill:var(--muted-foreground);font:11px var(--font-mono,monospace)}.axis{stroke:var(--border)}.unity{stroke:var(--muted-foreground);stroke-dasharray:4 4}.tick{fill:var(--muted-foreground);font-size:11px}.gate-pass{stroke:var(--success);fill:var(--success)}.gate-fail{stroke:var(--destructive);fill:var(--destructive)}.real{stroke:var(--chart-1);fill:var(--chart-1)}
</style></head><body><div class="controls"><label>State <select id="phase"><option value="warm">Warm</option><option value="cold">First use in session</option></select></label><span style="color:var(--muted-foreground);font-size:12px">Point / main ratio · unity = identical latency</span></div><section><h3>A/A · 20 independent-build pairs per tier</h3><div class="scroll" id="aa"></div><p>Green passes the fixed gate: CI includes 1 and half-width ≤5% (≤10% for import/startup). Red is a failed gate. Quit is an external process-exit clock.</p></section><section><h3>Real comparison · fork point / fork main</h3><div class="scroll" id="real"></div><p>Ratios above 1 favor fork main. Upstream is descriptive and appears in the accompanying table. CIs resample whole paired sessions, stratified by order. “No measurable change” requires an accepted A/A control and its reported MDE.</p></section><script>const data=__DATA__;
const NS='http://www.w3.org/2000/svg';function el(tag,attrs,text){const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs||{}))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e}
function draw(key){const rows=data[key].filter(r=>r.phase===document.querySelector('#phase').value);const w=700,h=rows.length*40+50,left=125,right=480;const lo=Math.min(.90,...rows.map(r=>r.ci95[0]))*.98,hi=Math.max(1.10,...rows.map(r=>r.ci95[1]))*1.02;const x=v=>left+(Math.log(v)-Math.log(lo))/(Math.log(hi)-Math.log(lo))*(right-left);const svg=el('svg',{viewBox:`0 0 ${w} ${h}`,class:'chart',role:'img','aria-label':key==='aa'?'A/A confidence intervals':'Fork comparison confidence intervals'});
svg.append(el('line',{x1:x(1),x2:x(1),y1:4,y2:h-32,class:'unity'}));for(let i=0;i<=4;i++){const v=Math.exp(Math.log(lo)+(Math.log(hi)-Math.log(lo))*i/4);svg.append(el('line',{x1:x(v),x2:x(v),y1:h-30,y2:h-25,class:'axis'}));svg.append(el('text',{x:x(v),y:h-10,'text-anchor':'middle',class:'tick'},v.toFixed(2)))}
rows.forEach((r,i)=>{const y=i*40+20,c=key==='aa'?(r.aa_pass?'gate-pass':'gate-fail'):'real',title=(r.tier==='import-1259'?'1259 import':r.action)+(r.action==='quit'?' *':'');svg.append(el('text',{x:0,y:y+4,class:'label'},title));const line=el('line',{x1:x(r.ci95[0]),x2:x(r.ci95[1]),y1:y,y2:y,class:c,'stroke-width':2});svg.append(line);for(const v of r.ci95)svg.append(el('line',{x1:x(v),x2:x(v),y1:y-5,y2:y+5,class:c}));const dot=el('circle',{cx:x(r.speedup),cy:y,r:4,class:c});dot.append(el('title',{},`${title}: ${r.speedup.toFixed(4)} [${r.ci95.map(v=>v.toFixed(4)).join(', ')}]; ${r.verdict}`));svg.append(dot);svg.append(el('text',{x:500,y:y+4,class:'detail'},`${r.speedup.toFixed(3)} [${r.ci95.map(v=>v.toFixed(3)).join(', ')}]`));});document.getElementById(key).replaceChildren(svg)}
function render(){draw('aa');draw('real')}document.querySelector('#phase').addEventListener('change',render);render();</script></body></html>'''
(root/'latency-results.html').write_text(html.replace('__DATA__',json.dumps(data)))
print(root/'latency-results.html')
