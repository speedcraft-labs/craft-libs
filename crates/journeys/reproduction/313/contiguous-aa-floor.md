# Retained 20-pair contiguous A/A sensitivity floor

Two clean builds of app main 5f816e19 have identical binary SHA-256. Twenty
whole AB/BA pairs (40 guarded/output-checked sessions), four repetitions,
two warmups and fixed 1350/7000 MHz GPU clocks pass 0/14 requested gates.
Valid warm-action approximate MDEs are 12.79–44.36%, not 5%. Four rows'
intervals exclude unity and cannot validate sensitivity or later verdicts.
No successful observation was trimmed. Whole-session/order-stratified
bootstrap and action clocks are unchanged from the predeclared source.

The shorter design cuts median/max between-build gap to 27.72/181.94 s,
from 465.30/1301.47 s in the long-session trial. A foreign GPU admission
wait still occurred inside one lease. Warm switch duration correlates
0.997 with the preview worker's lastRenderMs and 0.766 with coarse VM
steal observations; the latter is descriptive, not independent causation.
These observations explain why interval width cannot be assumed to meet
5%. The finite-run floor is reported; it is not a fundamental hardware limit.

Raw: sensitivity/aa-v6-paired-attempt-37-19/report.json, variance-v6-final.md,
runtime-v6-final.md, scheduling-v6-final.md and pair-gap-final.md in the single
313 NAS keep root. This branch retains the failed acceptance experiment;
the final real comparison uses explicit achieved floors and rejects verdicts
for A/A intervals excluding unity.
