# Corrected test-delay reference, before treatment inference

The hours-long A/A's pooled warm-switch control median was 979.993 ms, so
its calibrated fixed delay was 97.999 ms. The independent untreated pilot
then measured 423.593 ms: that delay was 23.135% of the current baseline.
The first whole pair is retained as a diagnostic injection pilot, not a
10% sensitivity proof. Its treatment CI/label was not used to stop or
choose the new delay. No successful numeric latency sample is trimmed.

A fresh predeclared 20-pair experiment uses 42.35933825 ms, exactly 10%
of the untreated pilot median. It must report slower with CI entirely
below unity, log every physical queued delay inside its result-frame
clock, and realize 9–11% of the independent control median. Otherwise
it fails the 10% proof. All-20-pair A/A remains its separate CI/MDE
calibration, and production comparisons use zero delay.

Raw: sensitivity/switch-slowdown-v6-attempt-0-0/report.json and
switch-delay-reference-correction.json. Active source/config is preserved
on wip/313-agentbox-operators. The action driver is unchanged.
