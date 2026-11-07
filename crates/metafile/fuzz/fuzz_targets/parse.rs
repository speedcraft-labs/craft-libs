#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let limits = craft_metafile::Limits::default();
    let _ = craft_metafile::parse_with_limits(data, limits);
});
