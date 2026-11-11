"""Conservative comparison sensitivity; raw clocks/bootstrap/A/A gates are untouched."""
import copy,math

def comparison_floor(row,reference):
    ci=reference.get('ci95') if reference else None
    if not ci or not ci[0]<=1<=ci[1]:return None,None
    effect=reference.get('minimum_detectable_effect_pct')
    pairs=reference.get('calibration_pairs',reference.get('observed_pairs'))
    if effect is None or not pairs or not row.get('observed_pairs'):return None,None
    adjusted=math.expm1(math.log1p(effect/100)*math.sqrt(pairs/row['observed_pairs']))*100
    return max(row['estimated_mde_pct'],adjusted),adjusted

def corrected_rows(report,calibration):
    references={(r['tier'],r['action'],r.get('phase','warm')):r for r in calibration['rows']}
    rows=copy.deepcopy(report['rows'])
    for row in rows:
        if row.get('is_aa'):continue
        reference=references.get((row['tier'],row['action'],row.get('phase','warm')))
        floor,adjusted=comparison_floor(row,reference)
        row['original_reported_mde_pct']=row.get('minimum_detectable_effect_pct')
        row['aa_pair_count_adjusted_mde_pct']=adjusted
        row['minimum_detectable_effect_pct']=floor
        row['sensitivity_method']='max(current CI-derived MDE, A/A MDE scaled by sqrt(calibration_pairs/comparison_pairs) on log scale); rejected A/A is uncalibrated'
        if row['verdict']=='no measurable change' and floor is None:raise ValueError('unchanged claim lacks valid sensitivity')
    return rows
