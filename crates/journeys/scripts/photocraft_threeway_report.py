#!/usr/bin/env python3
"""Report paired 315b PhotoCraft brush-only A/A and three-build runs."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import random
import statistics
from typing import Any

LABELS = ('brush-30px', 'brush-500px-soft', 'brush-canvas-width-soft')

def percentile(values: list[float], p: float) -> float:
    xs=sorted(values); at=(len(xs)-1)*p; lo=math.floor(at)
    return xs[lo]+(xs[math.ceil(at)]-xs[lo])*(at-lo)

def samples(session: dict[str,Any], label: str, phase: str, metric: str) -> list[int]:
    for sample in session.get('samples',[]):
        if sample.get('action')=='brush' and sample.get('label')==label and sample.get('phase')==phase:
            if metric=='point': return [int(v) for v in sample.get('point_latencies_ns',[])]
            return [int(sample['duration_ns'])]
    return []

def load(paths: list[Path]) -> list[dict[str,Any]]:
    reports=[]
    for path in paths:
        file=path/'report.json' if path.is_dir() else path
        report=json.loads(file.read_text())
        if not report.get('session_complete') or not report.get('gpu_process_checks_passed') or not report.get('gpu_state_passed'):
            raise ValueError(f'incomplete/unpublishable pair: {file}')
        reports.append(report)
    return reports

def session_by_role(report: dict[str,Any], tier: str) -> dict[str,dict[str,Any]]:
    return {s.get('side_role',s['side']):s for s in report.get('sessions',[]) if s.get('tier')==tier}

def pair_logs(reports: list[dict[str,Any]], tier: str, left: str, right: str, label: str, phase: str, metric: str) -> list[float]:
    logs=[]
    for report in reports:
        roles=session_by_role(report,tier)
        if left not in roles or right not in roles: continue
        a=samples(roles[left],label,phase,metric); b=samples(roles[right],label,phase,metric)
        if a and b: logs.append(math.log(statistics.median(a)/statistics.median(b)))
    if not logs: raise ValueError(f'no matched data: {tier} {label} {phase} {metric} {left}/{right}')
    return logs

def bootstrap(logs: list[float], seed: int) -> tuple[float,list[float],float,float]:
    rng=random.Random(seed); n=len(logs)
    ratios=[math.exp(statistics.median(rng.choice(logs) for _ in range(n))) for _ in range(10000)]
    ratio=math.exp(statistics.median(logs)); ci=[percentile(ratios,.025),percentile(ratios,.975)]
    half=(ci[1]-ci[0])/(2*ratio)*100
    mde=math.expm1((math.log(ci[1])-math.log(ci[0]))/2*(1.959964+0.841621)/1.959964)*100
    return ratio,ci,half,mde

def pooled(reports: list[dict[str,Any]], tier: str, role: str, label: str, phase: str, metric: str) -> list[int]:
    out=[]
    for report in reports:
        for session in report.get('sessions',[]):
            if session.get('tier')==tier and session.get('side_role',session['side'])==role:
                out.extend(samples(session,label,phase,metric))
    return out

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--aa',type=Path,nargs='+',required=True)
    p.add_argument('--threeway',type=Path,nargs='+',required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    aa=load(args.aa); comp=load(args.threeway)
    tiers=sorted({s['tier'] for r in comp for s in r.get('sessions',[])})
    gates=[]; rows=[]
    for tier in tiers:
        for label in LABELS:
            for phase in ('cold','warm'):
                for metric in ('point','stroke total'):
                    logs=pair_logs(aa,tier,'a','b',label,phase,metric)
                    ratio,ci,half,mde=bootstrap(logs,315+sum(map(ord,label+phase+metric)))
                    gate='PASS' if len(logs)>=20 and ci[0]<=1<=ci[1] and half<=5.0 else 'FAIL'
                    gates.append({'tier':tier,'label':label,'phase':phase,'metric':metric,'pairs':len(logs),'ratio_a_over_b':ratio,'ci95':ci,'half_width_pct':half,'mde_pct':mde,'verdict':gate})
                    contrast_logs={}
                    for left,right,name in (('a','b','a_over_b'),('a','c','a_over_c')):
                        clogs=pair_logs(comp,tier,left,right,label,phase,metric)
                        cratio,cci,chalf,cmde=bootstrap(clogs,731+sum(map(ord,label+phase+metric+name)))
                        contrast_logs[name]=clogs
                        rows.append({'tier':tier,'label':label,'phase':phase,'metric':metric,'pairs':len(clogs),'left_role':left,'right_role':right,'ratio':cratio,'ci95':cci,'half_width_pct':chalf,'mde_pct':max(cmde,mde*math.sqrt(20/len(clogs))),'current_mde_pct':cmde,'aa_gate':gate,'verdict':'A/A gate failed; descriptive only' if gate!='PASS' else 'a faster' if cci[1]<1 else 'a slower' if cci[0]>1 else 'no resolved difference'})
                    build={role:{'median_ms':statistics.median(pooled(comp,tier,role,label,phase,metric))/1e6,'p95_ms':percentile([float(v) for r in comp for s in r.get('sessions',[]) if s.get('tier')==tier and s.get('side_role',s['side'])==role for v in samples(s,label,phase,metric)],.95)/1e6} for role in ('a','b','c')}
                    rows[-1]['builds']=build
                    rows[-2]['builds']=build
    lines=['Ratio a/b compares merge-base with fork tip; a/c compares merge-base with upstream tip. Ratios use paired session medians and 10,000 bootstrap resamples. Point values use the 200 accepted down/move frame samples; stroke total is first accepted input through the release-frame GPU fence.','', '| Tier | Brush action | State | A median/p95 ms | B median/p95 ms | C median/p95 ms | a/b (95% CI) | a/c (95% CI) | A/A gate |','|---|---|---|---:|---:|---:|---:|---:|---|']
    point_rows=[r for r in rows if r['metric']=='point']
    for r in point_rows:
        build=r['builds']; same=next(x for x in rows if x['tier']==r['tier'] and x['label']==r['label'] and x['phase']==r['phase'] and x['metric']=='point' and x['left_role']=='a' and x['right_role']=='c')
        val=lambda role:f"{build[role]['median_ms']:.2f}/{build[role]['p95_ms']:.2f}"
        lines.append(f"| {r['tier']} | {r['label']} | {r['phase']} | {val('a')} | {val('b')} | {val('c')} | {r['ratio']:.3f} ({r['ci95'][0]:.3f}–{r['ci95'][1]:.3f}) | {same['ratio']:.3f} ({same['ci95'][0]:.3f}–{same['ci95'][1]:.3f}) | {r['aa_gate']} |")
    lines.extend(['','A/A gate uses 20 identical fork-tip pairs per tier. PASS requires the 95% interval to include 1.00 and relative half-width at most 5%. Contrasts failing that row gate remain descriptive.'])
    result={'aa_gates':gates,'rows':rows,'markdown':'\n'.join(lines)+'\n','aa_reports':[str(x) for x in args.aa],'threeway_reports':[str(x) for x in args.threeway]}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(result['markdown'],end='')
    return 0
if __name__=='__main__': raise SystemExit(main())
