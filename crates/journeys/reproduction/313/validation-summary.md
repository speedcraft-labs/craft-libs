Validation, with builds/tests on CPUs 0–21 and the one ticket target directory. Clean integration is `cd0f22bce74e85bedef7b963aacf23cd12f2642e`.

```text
cargo test -p craft-journeys
Ran 36 Python tests ... OK
test result: ok. 3 passed; 0 failed; 0 ignored

cargo test --workspace --no-fail-fast
latest post-rebase: 295 suites; 3833 passed; 2 failed; 127 ignored
prior full run:     295 suites; 3835 passed; 0 failed; 127 ignored
```

| Check / exact command | Branch | Clean integration |
|---|---|---|
| `cargo test -p craft-h264 --test it robustness::rapid_resets_do_not_hang -- --exact --nocapture` | Same test fails in full workspace at 300 s; `decoder hung after reset: Timeout` | 0 passed, 1 failed; 300.04 s; same timeout at robustness.rs:300 |
| `cargo test -p craft-proof --lib affix::tests::suggesting_with_a_long_try_line_shares_one_budget -- --exact --nocapture` | Same test fails in full workspace: 11.281228265 s vs 10 s assertion | 0 passed, 1 failed; 14.266492551 s vs same assertion, affix.rs:3831 |
| `cargo test -p craft-hevc conformance::bframes -- --nocapture` | Passes within full HEVC conformance: 43 passed, 2 ignored | 1 passed, 0 failed |
| `cargo test -p craft-hevc conformance::draft_mode_changes_only_flagged_non_reference_pictures -- --nocapture` | Passes within same conformance run | 1 passed, 0 failed |
| `cargo clippy --workspace --all-targets -- -D warnings` | Two assign_op_pattern errors, gpu-blur/shader/src/lib.rs:58,78 | Same two errors |
| `cargo clippy -p craft-av1 --all-targets -- -D warnings` | unnecessary_sort_by, crates/av1/tests/fuzz_hostile.rs:184 | Same error |

The HEVC failures previously reported are not reproducible. The two new timing assertions and three lints occur in files identical to integration and untouched by this PR. The earlier full passing run is retained; it does not replace the latest failing output. Journeys strict clippy and workspace formatting pass. Prefix for the local commands: `taskset -c 0-21 nice -n 19 env CARGO_BUILD_JOBS=8 CARGO_TARGET_DIR=/jobs/work/speedcraft-labs/targets/313-session-latency SQLX_OFFLINE=true RUST_MIN_STACK=8388608`.

Exact output: sensitivity/journeys-v5-final.log, workspace-v5.log, workspace-v4-rebased.log, workspace-tests-cpu.log, integration-cd0-{h264-reset,proof-budget,bframes,draft,clippy,av1-clippy}.log and branch-hevc.log. Latest source head cb3ef47c has frozen v5 clock observations; refresh hosted checks at final head before merge. Full v5 workspace repeats3833passed/2failed/127ignored; same two unchanged timing failures.
