//! vp9 conformance suite (see the crate docs). Run: `cargo test --release -p craft-conformance --test vp9 -- --nocapture`.

use craft_conformance::vp9;

/// Stream ffmpeg and libvpx cannot decode (docs/verification/codec-conformance.md).
const KNOWN_FAILURES: &[(&str, &str)] = &[
    // The bounded decoder reports exhaustion; ffmpeg 7.1.5 also rejects this stream.
    ("vp90-2-15-fuzz-flicker.webm", "boolean partition exhausted; ffmpeg rejects it too"),
    // Neither ffmpeg nor libvpx can decode it; the published md5 cannot be reproduced.
    ("vp91-2-04-yv444.webm", "boolean partition exhausted; reference md5 not reproducible"),
];
/// Floor: raise it when more streams pass, never lower it.
const MIN_PASS: usize = 341;

#[test]
fn vp9_conformance() {
    let Some(suite) = vp9::run() else { return };
    suite.assert_clean(KNOWN_FAILURES, MIN_PASS);
}
