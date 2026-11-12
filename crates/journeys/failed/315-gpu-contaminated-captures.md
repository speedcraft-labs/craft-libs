# Failed approach: retain samples collected with a foreign GPU process

A session is not publishable if the GPU watcher observes another process during a timed capture, even if PhotoCraft itself reports the NVIDIA path and the semantic assertions pass. Heavy A/A pair 06 attempt 1 and pair 08 attempt 1 observed a foreign `pdfcraft` process; they were preserved and excluded, then each pair passed on retry. The deliberate-slowdown campaign’s first four pairs passed; subsequent admissions were rejected before app launch while a LightCraft GPU process remained active.

Never pool those refused attempts or label them as slowdowns. The session runner requires a fresh exclusive acquisition and successful GPU checks for every pair. The exact refusal artifacts and process metadata live under `keep/315-photocraft-latency/reports/`; see handoffs 31, 33, 43, and 44 on hyper #291.

This is a data-quality note, not a PhotoCraft change.
