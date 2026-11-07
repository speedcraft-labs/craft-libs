#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let mut d = craft_vp8::Decoder::new();
    let _ = d.decode(data, 0);
});
