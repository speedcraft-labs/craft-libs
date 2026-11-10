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


The first corrected matrix was also stopped after a foreign GPU test process
(`targets/312-upstream-sync`, PID 2009059) was found using the RTX outside the CPU
benchmark lock. Its reports are explicitly marked `provisional-shared-gpu` and
excluded. The user added an exclusive GPU-lock rule; the final matrix is collected
again with both locks and before/after NVIDIA process snapshots. A foreign PID now
rejects publication in the harness. The earlier data is backed up, not deleted.


The first runs under both exclusive locks were rejected too: FilmCraft work under
`targets/291-media-journeys` did not yet honor the new GPU lock. The cold diagnostic
stopped after 65 accepted launches when its after-process listing contained foreign
PID 2516433. The typical-50 point session completed 74 samples but failed the same
gate; the heavy tier was rejected before launch (foreign PID 2666189), and a second
quit attempt saw foreign PID 2698448. Those reports remain not publishable and their
raw GPU CSVs/logs are backed up. The rejected quit iteration now also saves its
complete timing record before returning the GPU-isolation error.


A later clean-GPU cold quit attempt (`quit-diagnostic-exclusive-04`) observed
fork-main SIGSEGV on open pair 3 after three successful main attempts. The earlier
controller stopped before saving nonzero-exit clocks; the retained failed record
explicitly says those exact timestamps are unavailable. The diagnostic now keeps
every observed exit code and time, continues its planned attempts, and reports
failures alongside time-to-exit statistics. No crash is silently discarded or
called a successful quit. Mature session mode continues to reject abnormal exits.

The first `paired-typical-50-exclusive-03` attempt was canceled after its lock
wrappers had begun running; it is excluded and will be re-measured with intact
lock ownership. The final verifier additionally checks actual exposure photo-region
pixels in retained PNGs, outside all action clocks. The gate was calibrated on
retained pilot images: all 60 measured typical-tier exposure steps changed photo
pixels, and the 500-file pilot's steps also changed the photo region.


The first retry-aware matrix (`paired-typical-50-resilient`) accepted eight clean
sessions, then failed during upstream import: the giant trackpad scroll left the
grid at -2006.448 points with no visible thumbnails. The queued heavy run failed
similarly on its second import at -3023.768 points. This was a driver defect: the
trackpad gesture never ended, and `offset < 1` wrongly accepted any negative
overscroll as the top. Both datasets are excluded. The failed approach is kept
on `failed/313-grid-overscroll`. Use clamped wheel-point input for grid traversal
and require `abs(offset) < 1`; a regression test covers both retained offsets.


The wheel-based heavy preflight (`paired-heavy-500-resilient-v2`) completed point
and main, then all 74 upstream action samples and both oracle outputs. Its
untimed idle drain hit the fixed 180-second timeout while upstream was actively
preparing previews: 125/500 after about198 seconds, with no pending foreground
renders. This is normal extra upstream background work, not proof of a hang. The
failed approach is preserved as `failed/313-upstream-prep-timeout`; its two
completed sessions and the failed upstream record are excluded from the new
heavy matrix. Untimed background drains now allow 30 minutes and retain/log
progress every30 seconds. No timed action endpoint or background default is
changed. The completed typical50 table remains valid because its idle drains
finished within the old limit.
