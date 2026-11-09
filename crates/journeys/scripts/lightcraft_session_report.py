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
    if action == 'quit':
        return [session['exit_ns'] - session['quit_request_ns']]
    if action == 'startup':
        return [session['startup_library_ns']]
    return [x['duration_ns'] for x in session['samples'] if x['action'] == action and not x['warmup']]


def summarize(sessions, resamples=2000):
    rows = []
    sides = ('point', 'main', 'upstream')
    for tier in sorted({s['tier'] for s in sessions}):
        groups = {side: sorted([s for s in sessions if s['tier'] == tier and s['side'] == side], key=lambda s: s['pair']) for side in sides}
        for group in groups.values():
            for session in group:
                validate_session(session)
        if len({len(g) for g in groups.values()}) != 1:
            raise ValueError('unpaired sessions')
        n = len(groups['point'])
        for action in (*ACTIONS, 'startup', 'quit'):
            clusters = {side: [durations(s, action) for s in group] for side, group in groups.items()}
            if not all(all(cluster for cluster in group) for group in clusters.values()):
                raise ValueError('missing action samples')
            stats = {}
            for side, group in clusters.items():
                flat = [x for cluster in group for x in cluster]
                stats[side] = dict(n=len(flat), median_ns=statistics.median(flat), p95_ns=percentile(flat, .95), max_ns=max(flat))
            rng = random.Random(313)
            ratios = []
            for _ in range(resamples):
                indices = [rng.randrange(n) for _ in range(n)]
                med = {side: statistics.median(x for i in indices for x in group[i]) for side, group in clusters.items()}
                ratios.append(med['point'] / med['main'])
            ci = [percentile(ratios, .025), percentile(ratios, .975)]
            rows.append(dict(tier=tier, action=action, sides=stats, speedup=stats['point']['median_ns']/stats['main']['median_ns'], ci95=ci,
                             verdict='faster' if ci[0] > 1 else 'slower' if ci[1] < 1 else 'no measurable change'))
    return rows


def markdown(rows):
    lines = ['Ratio = fork point / fork main; >1 favors fork main. Times in ms. CI resamples whole paired sessions, not individual slider steps.']
    for tier in sorted({r['tier'] for r in rows}):
        lines += ['', f'Payload: {tier}', '', '| Action | Fork point median/p95 | Fork main median/p95 | Ratio (95% CI) | Upstream median | Verdict |', '|---|---:|---:|---:|---:|---|']
        for r in rows:
            if r['tier'] != tier:
                continue
            s = r['sides']
            cells = [f"{s[side]['median_ns']/1e6:.2f}/{s[side]['p95_ns']/1e6:.2f}" for side in ('point', 'main')]
            lines.append(f"| {r['action']} | {cells[0]} | {cells[1]} | {r['speedup']:.3f} ({r['ci95'][0]:.3f}–{r['ci95'][1]:.3f}) | {s['upstream']['median_ns']/1e6:.2f}{'†' if not r.get('upstream_equivalent',True) else ''} | {r['verdict']} |")
    if any(not r.get('upstream_equivalent',True) for r in rows):
        lines += ['', '† Upstream output exceeded the pixel-parity bound. Its medians are descriptive observations only; no upstream-relative speed claim is made.']
    return '\n'.join(lines) + '\n'


def check_pixels(sessions):
    from PIL import Image, ImageChops, ImageStat
    checks=[]
    for tier,pair in sorted({(s['tier'],s['pair']) for s in sessions}):
        group={s['side']:s for s in sessions if s['tier']==tier and s['pair']==pair}
        for session in group.values():
            jpeg=Image.open(session['export_sample']).convert('RGB')
            expected=Image.open(session['export_oracle']).convert('RGB')
            if jpeg.size!=expected.size:
                if max(abs(a-b) for a,b in zip(jpeg.size,expected.size))>1:
                    raise ValueError('JPEG output dimensions differ from requested source render')
                # Preview and export paths round the short edge differently (1366 vs 1365).
                expected=expected.resize(jpeg.size,Image.Resampling.BILINEAR)
            mean=ImageStat.Stat(ImageChops.difference(jpeg,expected)).mean
            if max(mean)>8:raise ValueError(f'JPEG does not reproduce its photo/settings within lossy MAE 8: {mean}')
        for side in ('main','upstream'):
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
