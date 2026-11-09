# LightCraft session build notes

Initial pinned revisions (fetched 2026-11-09):

- Fork point: fc97c728644d399843d8201f83d25ccf81b89669
- Fork main: 09eb4c56accd9dc0e405510d099fee10d6a68f55
- Upstream main: f6b57b0b59f45f3cfae1fb8d26a834e336be5a11

The first sequential build attempt used one shared Cargo target with a binary copy
between worktrees. Fork point built, but fork main failed with four E0599 errors:
its pipeline referred to `Process::V5` while Cargo reused fork-point develop
artifacts (fork-main source does contain `V5`). No timing numbers were collected
from this invalid combination. This attempt is retained as
`failed/313-shared-target-cache`; logs and the original build script are retained
with the NAS evidence.

The corrected recipe cleans only the current LightCraft workspace's package
artifacts (`cargo metadata --no-deps` supplies their names), in the **release**
profile, between app revisions. Third-party dependencies and the debug journey
harness remain in the same one ticket target. Copy each completed binary into
`$CARGO_TARGET_DIR/binaries/lightcraft-{point,main,upstream}` before cleaning the
next revision. Never clean while another app build is using this target. Build
outside the bench lock and CPU set, with `taskset -c 0-21 nice -n 19` and
`CARGO_BUILD_JOBS=8`. No app source or dependency lockfiles are changed by this
recipe. Record binary SHA-256 and app revision with every run.


The initial corpus helper also put tier hard links under the stamped download
root. That would make craft-corpus prune the tiers as unlisted files. The in-flight
fetch was stopped before pruning; tiers now use a sibling root and the helper
rejects a destination inside the stamped source. No RAW content was lost. Initial
500-file membership, the six ignored extensions and failed preflight logs are
preserved with the raw evidence. The corrected selected manifest has 518 unique
files: 31 in the single-camera tier and 500 in the mixed tier, with 13 shared files.
