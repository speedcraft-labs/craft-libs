#!/usr/bin/env python3
"""Pure-statistics checks for PhotoCraft's paired session formatter."""

import unittest

from photocraft_session_report import rows_for


def report(pair, left_role, right_role, left_ns, right_ns):
    def session(role, duration):
        return {
            "pair": pair,
            "tier": "typical",
            "side": role,
            "side_role": role,
            "samples": [
                {
                    "action": "visibility",
                    "label": "large-layer-visibility",
                    "phase": "warm",
                    "duration_ns": duration,
                }
            ],
        }

    return {"sessions": [session(left_role, left_ns), session(right_role, right_ns)]}


class PhotoCraftSummaryTests(unittest.TestCase):
    def test_cold_and_warm_open_samples_are_reported(self):
        sessions = []
        for pair in range(20):
            for role, cold_ns, warm_ns in (("a", 5_000_000, 4_000_000), ("b", 6_000_000, 4_500_000)):
                sessions.append(
                    {
                        "pair": pair,
                        "tier": "typical",
                        "side": role,
                        "side_role": role,
                        "samples": [],
                        "open_samples": [
                            {"action": "open", "label": "open-first-composite", "phase": "cold", "duration_ns": cold_ns},
                            {"action": "open", "label": "open-first-composite", "phase": "warm", "duration_ns": warm_ns},
                        ],
                    }
                )

        rows = rows_for([{"sessions": sessions}], "aa")
        cold = next(row for row in rows if row["label"] == "open-first-composite" and row["phase"] == "cold")
        warm = next(row for row in rows if row["label"] == "open-first-composite" and row["phase"] == "warm")
        self.assertEqual(cold["pairs"], 20)
        self.assertEqual(cold["left_median_ms"], 5.0)
        self.assertEqual(cold["right_median_ms"], 6.0)
        self.assertEqual(warm["left_median_ms"], 4.0)
        self.assertEqual(warm["right_median_ms"], 4.5)

    def test_aa_gate_and_slowdown_ratio_direction(self):
        aa_reports = [
            report(i, "a", "b", base := 100_000_000 + i * 10_000, base + (200_000 if i % 2 else -200_000))
            for i in range(20)
        ]
        aa = rows_for(aa_reports, "aa")
        self.assertEqual(len(aa), 1)
        self.assertEqual(aa[0]["verdict"], "PASS")
        self.assertLess(aa[0]["half_width_pct"], 5)

        delayed = [report(i, "control", "slow", 100_000_000 + i * 10_000, 110_000_000 + i * 10_000) for i in range(10)]
        check = rows_for(delayed, "slowdown", aa)[0]
        self.assertGreater(check["ratio"], 1)
        self.assertEqual(check["verdict"], "slower detected")
        self.assertGreater(check["mde_pct"], 0)

    def test_real_comparison_ratio_is_fork_over_upstream(self):
        aa_reports = [report(i, "a", "b", base := 100_000_000, base + (100_000 if i % 2 else -100_000)) for i in range(20)]
        aa = rows_for(aa_reports, "aa")
        real = [report(i, "fork", "upstream", 110_000_000 + i * 50_000, 100_000_000 + i * 50_000) for i in range(10)]
        row = rows_for(real, "comparison", aa)[0]
        self.assertGreater(row["ratio"], 1)
        self.assertEqual(row["verdict"], "slower")
        self.assertEqual(row["pairs"], 10)


if __name__ == "__main__":
    unittest.main()
