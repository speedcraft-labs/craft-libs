import unittest
from mde_floor import comparison_floor
class Sensitivity(unittest.TestCase):
 def test_half_as_many_pairs_has_a_higher_noise_floor(self):
  floor,adjusted=comparison_floor({'observed_pairs':10,'estimated_mde_pct':1},{'ci95':[.95,1.05],'minimum_detectable_effect_pct':10,'calibration_pairs':20})
  self.assertGreater(floor,14);self.assertLess(floor,15);self.assertEqual(floor,adjusted)
 def test_more_comparison_noise_cannot_be_hidden_by_a_quiet_control(self):
  floor,adjusted=comparison_floor({'observed_pairs':10,'estimated_mde_pct':30},{'ci95':[.95,1.05],'minimum_detectable_effect_pct':10,'calibration_pairs':20})
  self.assertEqual(floor,30);self.assertLess(adjusted,30)
 def test_twice_as_many_pairs_can_lower_the_control_floor(self):
  floor,_=comparison_floor({'observed_pairs':40,'estimated_mde_pct':1},{'ci95':[.95,1.05],'minimum_detectable_effect_pct':10,'calibration_pairs':20})
  self.assertGreater(floor,6);self.assertLess(floor,8)
 def test_rejected_or_missing_control_is_uncalibrated(self):
  for ref in (None,{}, {'ci95':[1.01,1.02],'minimum_detectable_effect_pct':1,'calibration_pairs':20}):
   self.assertEqual(comparison_floor({'observed_pairs':10,'estimated_mde_pct':2},ref),(None,None))
if __name__=='__main__':unittest.main()
