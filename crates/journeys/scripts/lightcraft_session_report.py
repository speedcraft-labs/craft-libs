"""Session evidence validation and paired, session-cluster bootstrap (no app runner)."""
import math
import random
import statistics

ACTIONS = ('import', 'preview', 'exposure', 'switch', 'export')


def validate_session(session):
    """Reject action clocks that include launch/exit, even if a plausible duration is supplied."""
    if not session['launch_ns'] < session['interactive_ns'] < session['quit_request_ns'] < session['exit_ns']:
        raise ValueError('invalid lifecycle ordering')
    if not session['gpu_adapter']:
        raise ValueError('empty GPU adapter')
    own=set(session.get('process_ids',[]))
    snapshots=[session.get(field) for field in ('gpu_admission_snapshot','gpu_processes_before','gpu_processes_driver_after','gpu_processes_after')]
    snapshots+=session.get('gpu_poll_snapshots',[])
    for snapshot in snapshots:
        if not session.get('gpu_provisional') and snapshot is not None and any(p['pid'] not in own for p in snapshot['processes']):
            raise ValueError('foreign GPU process makes session not publishable')
    for action in session['samples']:
        if action['action'] not in ACTIONS:
            raise ValueError('unknown action')
        if not session['interactive_ns'] <= action['sent_ns'] < action['frame_ns'] <= session['quit_request_ns']:
            raise ValueError('launch or exit inside action')
        if action['duration_ns'] != action['frame_ns'] - action['sent_ns']:
            raise ValueError('duration includes work outside input-to-frame boundary')
        if not action['checked'] or not action['frame_sha256']:
            raise ValueError('unchecked output')
        proof=action.get('evidence',{}).get('capture')
        if proof is not None:
            if proof.get('native') is False:
                raise ValueError('headless capture is not a native result frame')
            if proof['frame_ns']!=action['frame_ns'] or not action['frame_ns']<=proof['verified_ns']<=session['quit_request_ns']:
                raise ValueError('capture verification overlaps a different lifecycle interval')
            if proof['rgb_sha256']!=action['frame_sha256']:
                raise ValueError('capture output hash differs from sample')
            if proof['method']=='verified-x11':
                matching=[c['ns'] for c in proof['candidates'] if c['ns']<=proof['verified_ns'] and c['rgb_sha256']==proof['rgb_sha256'] and (c['width'],c['height'])==(proof['width'],proof['height'])]
                if not matching or min(matching)!=action['frame_ns']:
                    raise ValueError('early frame has no matching native-pixel proof')
            elif proof['method']!='native-upper-bound' or action['frame_ns']!=proof['verified_ns']:
                raise ValueError('invalid native capture endpoint')



def percentile(xs, p):
    xs = sorted(xs)
    at = (len(xs) - 1) * p
    lo = math.floor(at)
    return xs[lo] + (xs[math.ceil(at)] - xs[lo]) * (at - lo)


def durations(session, action):
    if action in ('startup','quit') and action+'_samples' in session:
        return [x['duration_ns'] for x in session[action+'_samples'] if x['phase']=='warm']
    if action == 'quit':
        return [session['exit_ns'] - session['quit_request_ns']]
    if action == 'startup':
        return [session['startup_library_ns']]
    return [x['duration_ns'] for x in session['samples'] if x['action'] == action and not x['warmup']]


def variance_components(clusters):
    """Balanced one-way random effects on log latency; do not confuse repeats with sessions."""
    usable = [xs for xs in clusters if len(xs) > 1]
    if len(usable) != len(clusters) or len(clusters) < 2:
        return dict(within_log_sd=None, between_log_sd=None)
    logs = [[math.log(x) for x in xs] for xs in clusters]
    within = statistics.mean(statistics.variance(xs) for xs in logs)
    between = max(0, statistics.variance(statistics.mean(xs) for xs in logs)
                  - statistics.mean(within / len(xs) for xs in logs))
    return dict(within_log_sd=math.sqrt(within), between_log_sd=math.sqrt(between))


def summarize(sessions, resamples=4000, calibration=None, aa=False):
    # A/A precision is empirical; MDE additionally assumes asymptotic log-normal
    # location errors, two-sided alpha=.05 and power=.80. Never call CI width power.
    import json
    if isinstance(calibration, str):
        calibration = json.load(open(calibration))
    calibrated = {(r['tier'], r['action'], r.get('phase','warm')): r
                  for r in (calibration or {}).get('rows', [])} if calibration else {}
    rows = []
    for tier in sorted({s['tier'] for s in sessions}):
        sides = tuple(side for side in ('point','main','upstream')
                      if any(s['side']==side and s['tier']==tier for s in sessions))
        groups = {side: sorted([s for s in sessions if s['tier']==tier and s['side']==side], key=lambda s:s['pair']) for side in sides}
        for group in groups.values():
            for session in group: validate_session(session)
        if 'point' not in groups or 'main' not in groups or len({tuple(s['pair'] for s in g) for g in groups.values()}) != 1:
            raise ValueError('unpaired sessions')
        n = len(groups['point'])
        for action in (*ACTIONS, 'startup', 'quit'):
            phases = ('cold','warm') if ((action in ('startup','quit') and all(action+'_samples' in session for g in groups.values() for session in g)) or action in ACTIONS and all('phase' in x for g in groups.values() for session in g for x in session['samples'])) else ('warm',)
            for phase in phases:
                def values(session):
                    if action in ('startup','quit'):
                        if action+'_samples' in session:return [x['duration_ns'] for x in session[action+'_samples'] if x['phase']==phase]
                        return durations(session,action)
                    if phase=='cold': return [x['duration_ns'] for x in session['samples'] if x['action']==action and x.get('phase')=='cold']
                    return durations(session,action)
                clusters = {side:[values(session) for session in group] for side,group in groups.items()}
                if not all(all(cluster for cluster in group) for group in clusters.values()):
                    raise ValueError('missing action samples')
                stats = {}
                for side,group in clusters.items():
                    flat = [x for cluster in group for x in cluster]
                    stats[side] = dict(n=len(flat), median_ns=statistics.median(flat), p95_ns=percentile(flat,.95), max_ns=max(flat), **variance_components(group))
                rng = random.Random(313)
                ratios = []
                for _ in range(resamples):
                    indices = [rng.randrange(n) for _ in range(n)]
                    med = {side:statistics.median(x for i in indices for x in group[i]) for side,group in clusters.items()}
                    ratios.append(med['point']/med['main'])
                ci = [percentile(ratios,.025),percentile(ratios,.975)]
                ratio = stats['point']['median_ns']/stats['main']['median_ns']
                half_width = (ci[1]-ci[0])/2/ratio*100
                # CI-derived MDE on log scale, with 80% power explicitly declared.
                mde = math.expm1((math.log(ci[1])-math.log(ci[0]))/2 * (1.959964+.841621)/1.959964)*100
                reference = calibrated.get((tier,action,phase))
                sensitivity = mde if aa else reference.get('minimum_detectable_effect_pct') if reference else None
                limit = 10 if action in ('import','startup') else 5
                offenders = {name for group in groups.values() for session in group for name in session.get('gpu_tier_offenders',[])}
                verdict = 'faster' if ci[0]>1 else 'slower' if ci[1]<1 else 'no measurable change' if sensitivity is not None else 'sensitivity uncalibrated'
                rows.append(dict(tier=tier,action=action,phase=phase,sides=stats,speedup=ratio,ci95=ci,
                    half_width_pct=half_width,minimum_detectable_effect_pct=sensitivity,estimated_mde_pct=mde,
                    is_aa=aa,aa_pass=aa and n>=10 and ci[0]<=1<=ci[1] and half_width<=limit,
                    threshold_pct=limit,calibration_pairs=n if aa else reference.get('calibration_pairs') if reference else None,
                    verdict=verdict,provisional=any(s.get('gpu_provisional') for g in groups.values() for s in g),gpu_offenders=sorted(offenders)))
    return rows


def markdown(rows):
    lines = ['Ratio = point / main; >1 favors main. Times in ms. Paired-session bootstrap; cold = first use in a session, warm = post-warm-up. OS/shader caches are not flushed.',
             'MDE: A/A-derived approximate two-sided 5% significance, 80% power detectable change on log scale. Uncalibrated comparisons cannot say "no measurable change".']
    for tier in sorted({r['tier'] for r in rows}):
        selected=[r for r in rows if r['tier']==tier]
        provisional=any(r.get('provisional') for r in selected)
        offenders=sorted({name for r in selected for name in r.get('gpu_offenders',[])})
        lines += ['', 'Payload: '+tier+(' — PROVISIONAL (shared GPU; '+', '.join(offenders)+')' if provisional else ''), '',
            '| Action / state | Point median/p95 | Main median/p95 | Ratio (95% CI) | Half-width % | Minimum detectable effect % | Upstream median/p95 | Verdict / A/A gate |',
            '|---|---:|---:|---:|---:|---:|---:|---|']
        for r in selected:
            stats=r['sides']
            def cell(side):
                return f"{stats[side]['median_ns']/1e6:.2f}/{stats[side]['p95_ns']/1e6:.2f}" if side in stats else '—'
            mde=r.get('minimum_detectable_effect_pct')
            if r['verdict']=='no measurable change' and mde is None:
                raise ValueError('no measurable change requires measured A/A MDE')
            # The explicit aa flag is attached below by the caller-independent statistic.
            gate=('PASS' if r['aa_pass'] else 'FAIL') if r.get('is_aa') else r['verdict']
            lines.append(f"| {r['action']} / {r.get('phase','warm')} | {cell('point')} | {cell('main')} | {r['speedup']:.3f} ({r['ci95'][0]:.3f}–{r['ci95'][1]:.3f}) | {r['half_width_pct']:.2f} | {f'{mde:.2f}' if mde is not None else 'uncalibrated'} | {cell('upstream')} | {gate} |")
    return '\n'.join(lines)+'\n'


def check_photo_frames(session):
    """Verify exposure changed the photo pixels inside each accepted native frame."""
    import hashlib
    from PIL import Image
    ppp=session['pre_quit_state']['pixelsPerPoint']
    previous=None
    checks=[]
    for index,sample in enumerate(session['samples']):
        if sample['action']!='exposure':continue
        evidence=sample['evidence']
        image=Image.open(evidence['capture']['reference_png']).convert('RGB')
        x,y,w,h=evidence['image_rect']
        box=tuple(round(value*ppp) for value in (x+w*.2,y+h*.2,x+w*.8,y+h*.8))
        if not 0<=box[0]<box[2]<=image.width or not 0<=box[1]<box[3]<=image.height:
            raise ValueError('photo output-check region is outside the native frame')
        digest=hashlib.sha256(image.crop(box).tobytes()).hexdigest()
        if not sample['warmup']:
            if previous is None:raise ValueError('exposure output checks require a warm-up frame')
            verify_photo_change(previous,digest)
            checks.append(dict(sample=index,step=evidence['step'],sha256=digest,previous_sha256=previous,box=box))
        previous=digest
    return checks


def verify_photo_change(previous,current):
    if not previous or not current or previous==current:
        raise ValueError('exposure result photo pixels did not change')


def check_export_pixels(session):
    from PIL import Image, ImageChops, ImageStat
    jpeg=Image.open(session['export_sample']).convert('RGB')
    expected=Image.open(session['export_oracle']).convert('RGB')
    if jpeg.size!=expected.size:
        if session.get('export_oracle_method')=='png-export-same-geometry':
            raise ValueError('JPEG and lossless PNG export geometry differ')
        if max(abs(a-b) for a,b in zip(jpeg.size,expected.size))>1:
            raise ValueError('JPEG output dimensions differ from requested source render')
        # Retain validation of the already-published legacy preview-based report.
        expected=expected.resize(jpeg.size,Image.Resampling.BILINEAR)
    mean=ImageStat.Stat(ImageChops.difference(jpeg,expected)).mean
    if max(mean)>8:raise ValueError(f'JPEG does not reproduce its photo/settings within lossy MAE 8: {mean}')
    return dict(mean_rgb=mean,dimensions=list(jpeg.size),oracle_method=session.get('export_oracle_method','legacy-ui-render'))


def check_pixels(sessions):
    from PIL import Image, ImageChops, ImageStat
    checks=[]
    for session in sessions:
        if not session.get('photo_output_checks'):session['photo_output_checks']=check_photo_frames(session)
    for tier,pair in sorted({(s['tier'],s['pair']) for s in sessions}):
        group={s['side']:s for s in sessions if s['tier']==tier and s['pair']==pair}
        for session in group.values():
            session['export_output_check']=check_export_pixels(session)
        for side in ('main','upstream'):
            if side not in group:continue
            a,b=group['point'],group[side]
            if a['oracle_source']!=b['oracle_source']:
                raise ValueError('oracle source mismatch')
            old,new=(Image.open(s['oracle']).convert('RGBA') for s in (a,b))
            if old.size!=new.size:raise ValueError('oracle dimensions differ')
            diff=ImageChops.difference(old,new)
            maximum=[high for low,high in diff.getextrema()]
            mean=ImageStat.Stat(diff).mean
            checks.append(dict(tier=tier,pair=pair,side=side,max_rgba=maximum,mean_rgba=mean))
            jold,jnew=(Image.open(s['export_sample']).convert('RGB') for s in (a,b))
            if jold.size!=jnew.size:raise ValueError('JPEG dimensions differ between revisions')
            jdiff=ImageChops.difference(jold,jnew)
            jmax=[high for low,high in jdiff.getextrema()]
            jmean=ImageStat.Stat(jdiff).mean
            checks[-1].update(jpeg_max_rgb=jmax,jpeg_mean_rgb=jmean)
            equivalent=max(maximum[:3])<=1 and maximum[3]==0 and max(jmax)<=16 and max(jmean)<=.5
            checks[-1]['equivalent']=equivalent
            if side=='main' and not equivalent:
                raise ValueError(f'primary output equivalence failed: {checks[-1]}')
    return checks
