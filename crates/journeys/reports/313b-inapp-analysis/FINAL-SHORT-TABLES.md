On Agentbox, this 20-pair experiment supports detecting a 5% change at the stated approximate 80% power for exposure, export. The specified A/A precision gate passes 5/7 current app/tier rows; failed gates are retained. Control wait is 0% of every in-app interval by construction. The retired confirmation-import cohort is reported separately and is never pooled with folder-drop imports.

| Warm action | A/B ratio [95% CI] | Half-width | MDE¹ | Gate |
|---|---:|---:|---:|---|
| import | 0.9989 [0.9001, 1.0603] | 8.02% | 12.42% | PASS |
| preview | 1.0067 [0.8535, 1.1039] | 12.43% | 20.18% | FAIL |
| exposure | 1.0214 [0.9904, 1.0554] | 3.18% | 4.64% | PASS |
| switch | 1.0142 [0.9049, 1.0911] | 9.18% | 14.31% | FAIL |
| export | 1.0010 [0.9761, 1.0282] | 2.60% | 3.79% | PASS |
| startup | 1.0041 [0.8742, 1.0192] | 7.22% | 11.59% | PASS |
| quit (external) | 0.9970 [0.8676, 1.0285] | 8.07% | 12.93% | FAIL |
| 1259 import (folder drop) | 0.9504 [0.8177, 1.0033] | 9.77% | 15.75% | PASS |

| Warm action | Fork point ms | Fork main ms | Upstream ms² | Point/main ratio [95% CI] | Verdict; MDE¹ |
|---|---:|---:|---:|---:|---|
| import | 220.60 | 28.44 | 29.14 | 8.0084 [7.6049, 8.2922] | outputs differ; descriptive only; 18.01% |
| preview | 36.84 | 98.72 | 102.72 | 0.3976 [0.3367, 0.5255] | outputs differ; descriptive only; 37.47% |
| exposure | 7.87 | 7.38 | 7.68 | 1.0430 [0.9645, 1.1124] | outputs differ; descriptive only; 10.74% |
| switch | 401.95 | 79.43 | 69.36 | 5.4606 [3.9245, 6.6799] | outputs differ; descriptive only; 46.25% |
| export | 339.96 | 332.96 | 330.80 | 1.0390 [1.0011, 1.0929] | outputs differ; descriptive only; 6.47% |
| startup | 926.71 | 1205.49 | 1078.53 | 0.7531 [0.7203, 1.0177] | outputs differ; descriptive only; 28.02% |
| quit (external) | 127.07 | 145.32 | 134.80 | 0.8517 [0.7788, 1.0678] | outputs differ; descriptive only; 25.30% |
| 1259 import (folder drop) | 22244.83 | 17328.41 | 16994.56 | 1.3563 [0.8634, 1.4440] | no measurable change; 44.42% |

Retired confirmation protocol (kept separately):

| Warm action | A/B ratio [95% CI] | Half-width | MDE¹ | Gate |
|---|---:|---:|---:|---|
| 1259 import (confirmation, legacy) | 0.9852 [0.8908, 1.1158] | 11.42% | 17.46% | FAIL |

| Warm action | Fork point ms | Fork main ms | Upstream ms² | Point/main ratio [95% CI] | Verdict; MDE¹ |
|---|---:|---:|---:|---:|---|
| 1259 import (confirmation, legacy) | 1944.59 | 509.58 | 526.74 | 3.7829 [3.5681, 3.7829] | insufficient paired sessions; uncalibrated |
