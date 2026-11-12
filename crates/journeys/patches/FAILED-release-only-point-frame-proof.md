# Rejected 315b release-only point-frame proof

The first typical pixel proof sampled only the image after `latency.wait` completed. It showed
that each build's release frame matched its settled stroke, but it did not show that upstream's
recorded down/move frame contained the stroke. That evidence was insufficient for validating
the upstream point-latency number and must not be cited for that claim.

The corrected recorder requests a screenshot for each accepted down/move/up frame and retains
the RGB crop for the median point frame. The driver compares that crop with the pre-stroke and
settled crops, records changed-pixel counts, and checks dab counts. The rejected capture remains
in the keep bundle as `reports/proof-typical/pair-00-try-05/`; the corrected capture is
`reports/proof-typical/pair-00-try-07/`.
