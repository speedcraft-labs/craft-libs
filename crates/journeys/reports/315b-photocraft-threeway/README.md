# 315b measurement configs

These JSON files pin the payload, recorder hash, app revisions, executable hashes, and UI coordinates for the pixel proof, typical and heavy A/A gates, three-build comparisons, and pre-#10013 cause checkpoint. Build artifacts live under `/jobs/work/speedcraft-labs/targets/315b/pinned`; raw reports and failed attempts are preserved under the ticket keep directory and NAS snapshots.

The typical three-build runs used `python3 /jobs/work/speedcraft-labs/keep/315b-photocraft-threeway/operators/run-campaign.py threeway typical --retries 2`. A/A pairs and remaining tiers use the same runner with their acquisition and tier names; each pair takes a fresh bench/GPU lease.

The tracked runner passes explicit bench/GPU ownership markers into the lease controller. A nested lease reuses those locks instead of reacquiring `gpu.lock`; `BENCH_LOCK_FILE` is pinned to `bench.lock.guard.flock` for the inner `bench-run` wrapper. Each measurement lease is limited to 840 seconds and one pair.
