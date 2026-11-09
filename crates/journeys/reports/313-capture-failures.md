# Rejected session pilots (313)

The first attempt at the primary matrix used 31 single-camera RAWs, below the
requested approximately 50. It completed fork point and fork main, but upstream
logged three native compositor screenshot timeouts and used headless fallback.
The harness correctly rejected the report; no ratio from it is published.
The recorded affected action bounds were 7,624.85 ms and 8,117.30 ms exposure,
and 10,022.24 ms photo switch, including the screenshot failure path.

The partially started 500-file matrix was stopped to replace that capture policy
consistently. Its data is retained but not used in the replacement comparison.
The new policy keeps failed captures, retries up to three times without resetting
the original action clock, and requires a native result. It therefore retains
stall latency rather than filtering slow observations.

All 50 replacement RAWs from RawNIND were validated as Sony ILCE-7C, 6000×4000,
with distinct SHA-256 values. Their direct URLs and CC-BY-SA-4.0 provenance are
pinned; the original 31-file tier remains explicitly labeled as an abandoned pilot.

Raw evidence is in NAS ticket `313-session-latency`, directories `paired-typical`
and `paired-heavy`; the replacement reports use new output directories. No old
launch-per-task journey or published report was changed.


The first 50-file block then exposed a retry-boundary error: a main exposure sample
was 6315.13 ms through retry, while an earlier retained X11 frame was provably the
same result 5571.34 ms earlier (743.79 ms input-to-frame). It was stopped, not
published. The final implementation compares the successful native PNG against
candidates from **all** attempts and uses the earliest exact match. No timeout is
subtracted by assumption. The original `paired-typical-50` data remains retained;
the replacement output directories use the suffix `-verified`.
