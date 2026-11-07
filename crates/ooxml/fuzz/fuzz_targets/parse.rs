#![no_main]

use craft_archive::ZipLimits;
use craft_ooxml::{
    dom::{self, Limits},
    opc::{LazyPackage, OpcLimits, Package},
};
use libfuzzer_sys::fuzz_target;

const MAX_INPUT: usize = 4 << 20;
const MAX_EXPANDED: u64 = 16 << 20;
const MAX_XML: usize = 1 << 20;

fn limits() -> OpcLimits {
    OpcLimits {
        zip: ZipLimits { max_entries: 512, max_entry_bytes: MAX_EXPANDED, max_total_bytes: MAX_EXPANDED },
        xml: Limits {
            max_depth: 128,
            max_nodes: 20_000,
            max_text_bytes: MAX_XML,
            max_attr_bytes: MAX_XML,
            max_total_bytes: MAX_XML,
            ..Limits::default()
        },
        max_archive_bytes: MAX_INPUT,
    }
}

fuzz_target!(|data: &[u8]| {
    if data.len() > MAX_INPUT {
        return;
    }

    let limits = limits();
    let _ = dom::parse(data, &limits.xml);

    if let Ok(package) = Package::open(data, &limits) {
        for name in package.part_names() {
            if name.to_ascii_lowercase().ends_with(".xml") || name.to_ascii_lowercase().ends_with(".rels") {
                if let Some(xml) = package.part(name) {
                    let _ = dom::parse(xml, &limits.xml);
                }
            }
        }
    }

    if let Ok(mut package) = LazyPackage::open(data, &limits) {
        let names: Vec<_> = package.part_names().take(64).map(str::to_owned).collect();
        for name in names {
            if name.to_ascii_lowercase().ends_with(".xml") || name.to_ascii_lowercase().ends_with(".rels") {
                if let Ok(xml) = package.read(&name, MAX_XML as u64) {
                    let _ = dom::parse(&xml, &limits.xml);
                }
            }
        }
    }
});
