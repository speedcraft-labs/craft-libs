# Retained heavy-pair resource plan

The 1,259-photo pilot passed all catalog, thumbnail and output checks. It took
385.803002 s wall / 381.878705 s accepted work through cleanup for one app.
Two nominal apps leave 68.394 s of an 840 s work lease; the existing 1.5x+30s
counterpart reserve correctly declines it. No paired heavy run was attempted
under that unsuitable forecast, and no numerical observation was trimmed.

Keep the two warmups: import progressed from 92.409 s first use through a
41.755 s transitional warmup to 15.633/17.761 s measured warm samples. Reducing
warmups would mix transient cache work into the steady-state row.

The predeclared replacement keeps two repetitions and runs each build in its
own bounded acquisition, alternating A/B then B/A between pairs. Both heavy
A/A and real primary comparison use this exact cadence, ten whole pairs, and
empty-queue stress admission. Report actual between-build gaps and MDE floors.
The successful lone pilot is descriptive and is not seeded into calibration.

Raw: sensitivity/heavy-aa-pilot-1259/point/report.json and point.forecast.json;
configuration: heavy-1259-protocol-predeclared.json. Operators are retained
on wip/313-agentbox-operators. No action clocks or app performance code changed.
