#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let mut options = craft_pdf::OpenOptions::default();
    options.max_input_bytes = 4 << 20;
    options.decode_limits = craft_pdf::syntax::DecodeLimits::default().with_max_decoded_stream(4 << 20);
    let _ = craft_pdf::open_slice_with_options(data, None, &options);
});
