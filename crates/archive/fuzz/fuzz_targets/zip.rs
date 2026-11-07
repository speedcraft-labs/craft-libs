#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let limits = craft_archive::ZipLimits { max_entries: 128, max_entry_bytes: 1 << 20, max_total_bytes: 4 << 20 };
    if let Ok(mut zip) = craft_archive::ZipReader::open(data, limits) {
        let names = zip.names().to_vec();
        for name in names.iter().take(128) {
            let _ = zip.read_bounded(name, 1 << 20);
        }
    }
});
