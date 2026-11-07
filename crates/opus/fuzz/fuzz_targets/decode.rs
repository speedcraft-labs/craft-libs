#![no_main]

use craft_opus::{Decoder, OpusHead, Packet, StreamDecoder};
use libfuzzer_sys::fuzz_target;

const MAX_INPUT: usize = 4 << 20;

fuzz_target!(|data: &[u8]| {
    if data.len() > MAX_INPUT {
        return;
    }

    let _ = Packet::parse(data);
    let _ = OpusHead::parse(data);

    if let Ok(mut decoder) = StreamDecoder::new(48_000, 2) {
        let mut pcm = Vec::new();
        let _ = decoder.decode_interleaved(Some(data), &mut pcm);
    }

    if let Ok(mut decoder) = Decoder::new(data) {
        let _ = decoder.decode(Some(data));
    }
});
