# Retained foreign-GPU admission / lease expiry

The calibrated physical-switch experiment completed six whole pairs. Pair 6
then lost two main attempts to foreign 312-daily GPU tests, waited for admission,
and reached its 840-second deadline before the last main report acquired the
outer guard. Cleanup took 842.216841 seconds, restored owned display mode 2,
and left the owned run-p4081625-i121471674.service inactive.

The entire pair is rejected, including its lone guarded point. The unguarded
main's otherwise successful numbers are retained but cannot enter inference.
Resume only the six complete guarded pairs; rerun both builds of pair 6 in a
fresh acquisition. Original action clocks, 42.35933825 ms physical dose and
predeclared 20-pair count do not change. No duration-based trimming.

Raw: sensitivity/switch-slowdown-v6-calibrated-attempt-0-6/,
its .lease-expired.json, and switch-pair6-resource-review.json. GPU process
snapshots, rejected attempts and all diagnostics remain in the same NAS keep
root. This is an acquisition failure, not a slowdown or sensitivity result.
