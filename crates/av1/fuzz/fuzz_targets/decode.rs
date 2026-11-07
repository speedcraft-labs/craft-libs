#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let mut d = craft_av1::Decoder::new();
    let _ = d.decode(data);
    let _ = d.flush_result();
});
