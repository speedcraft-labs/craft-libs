#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let mut d = craft_vp9::Decoder::new();
    let _ = d.decode(data, 0);
    let _ = d.flush();
});
