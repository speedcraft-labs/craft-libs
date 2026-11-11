The fixed in-app protocol does not establish universal 5% warm-action sensitivity.

At 20 independent-build pairs, typical50 preview has CI half-width12.43% and MDE20.18%; switch half-width9.18% and MDE14.31%. Both miss their unchanged5% gate. Typical import/startup pass their allowed10% precision gate but do not establish5% detection power. Exposure MDE4.64% and export3.79% support approximately80% power for a5% change.

Import1259 uses two warmups/two measured repetitions per session,20 contiguousAB/BA pairs: ratio.9852 CI[.8908,1.1158], half-width11.42%, MDE17.46%; it misses the unchanged10% gate. App completion spans30..32frames with a roughly516ms first-to-completion gap. Source limits import to4prepared batches per host frame. Exact frame-stall causes are unresolved.

The failed universal sensitivity claim is dropped; all observations, failed gates and achieved floors are retained. No complete pair is discarded and no threshold is loosened or rerun until passing. The recorder/driver still ship because app duration now contains zero control wait and the request explicitly allows reporting an action's achieved floor and measured cause. Clock source remains0e541934… with post-clock validator88e6735f; real comparisons remain queued and use identical recorder code. See the adjacent A/A tables, trace proofs and diagnostics, and issue291.
