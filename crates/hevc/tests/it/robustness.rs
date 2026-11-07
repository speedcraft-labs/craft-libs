//! hvcC / length-prefixed input and resilience against damaged streams.

use crate::common;

use craft_bitstream::annexb_nals;
use craft_hevc::Decoder;

fn damaged_fixture(name: &str) -> Vec<u8> {
    let f = common::fixture(name);
    let Some((path, _)) = common::ensure(f) else { panic!("ffmpeg fixture unavailable: {name}") };
    let mut data = std::fs::read(path).unwrap();
    let mut starts = Vec::new();
    let mut i = 0;
    while i + 3 <= data.len() {
        if i + 4 <= data.len() && data[i..i + 4] == [0, 0, 0, 1] {
            starts.push(i + 4);
            i += 4;
        } else if data[i..i + 3] == [0, 0, 1] {
            starts.push(i + 3);
            i += 3;
        } else {
            i += 1;
        }
    }
    let mut vcl = 0;
    for (n, &start) in starts.iter().enumerate() {
        if start + 2 >= data.len() || (data[start] >> 1) & 0x3f > 31 {
            continue;
        }
        if vcl == 8 {
            let end = starts.get(n + 1).copied().unwrap_or(data.len());
            let at = start + 3 + (end.saturating_sub(start + 4)) / 2;
            data[at] ^= 0x20;
            return data;
        }
        vcl += 1;
    }
    panic!("no suitable VCL NAL in {name}");
}

fn decode_hash(data: &[u8], threads: usize) -> (u64, bool) {
    let mut dec = Decoder::with_threads(threads);
    let mut hash = 0xcbf29ce484222325u64;
    let mut add = |bytes: &[u8]| {
        for &byte in bytes {
            hash = (hash ^ u64::from(byte)).wrapping_mul(0x100000001b3);
        }
    };
    for (i, au) in common::split_access_units(data).into_iter().enumerate() {
        match dec.decode(au, i as i64) {
            Ok(pics) => {
                for p in pics {
                    add(&p.width.to_le_bytes());
                    add(&p.height.to_le_bytes());
                    add(&p.pts.to_le_bytes());
                    add(&p.y.to_le_bytes());
                    add(&p.u.to_le_bytes());
                    add(&p.v.to_le_bytes());
                }
            }
            Err(error) => add(error.to_string().as_bytes()),
        }
    }
    for p in dec.flush() {
        add(&p.width.to_le_bytes());
        add(&p.height.to_le_bytes());
        add(&p.pts.to_le_bytes());
        add(&p.y.to_le_bytes());
        add(&p.u.to_le_bytes());
        add(&p.v.to_le_bytes());
    }
    let worker_error = dec.take_error().is_some();
    drop(add);
    (hash, worker_error)
}

#[test]
fn damaged_stream_hash_is_stable_across_thread_counts() {
    let data = damaged_fixture("bframes");
    assert!(decode_hash(&data, 1).1, "mutation must trigger a worker decode error");
    for threads in [1, 2, 4] {
        let expected = decode_hash(&data, threads);
        for _ in 0..3 {
            assert_eq!(decode_hash(&data, threads), expected, "threads={threads}");
        }
    }
    let expected = decode_hash(&data, 1);
    for threads in [2, 4] {
        assert_eq!(decode_hash(&data, threads), expected, "thread count {threads}");
    }
}

/// Build an hvcC record and length-prefixed samples from an Annex-B stream.
fn to_hvcc(data: &[u8]) -> (Vec<u8>, Vec<Vec<u8>>) {
    let mut sets: [Vec<Vec<u8>>; 3] = [Vec::new(), Vec::new(), Vec::new()];
    let mut samples = Vec::new();
    for au in common::split_access_units(data) {
        let mut sample = Vec::new();
        for nal in annexb_nals(au) {
            let t = (nal[0] >> 1) & 0x3f;
            match t {
                32..=34 => sets[(t - 32) as usize].push(nal.to_vec()),
                _ => {
                    sample.extend((nal.len() as u32).to_be_bytes());
                    sample.extend_from_slice(nal);
                }
            }
        }
        if !sample.is_empty() {
            samples.push(sample);
        }
    }
    for s in sets.iter_mut() {
        s.dedup();
    }
    let mut hvcc = vec![1u8];
    hvcc.extend([0u8; 20]); // profile / level / misc fields (not used by the decoder)
    hvcc.push(0xfc | 3); // lengthSizeMinusOne = 3
    hvcc.push(3);
    for (k, s) in sets.iter().enumerate() {
        hvcc.push(0x80 | (32 + k as u8));
        hvcc.extend((s.len() as u16).to_be_bytes());
        for n in s {
            hvcc.extend((n.len() as u16).to_be_bytes());
            hvcc.extend_from_slice(n);
        }
    }
    (hvcc, samples)
}

#[test]
fn hvcc_input_matches_reference() {
    for name in ["medium", "intra_main10"] {
        let f = common::fixture(name);
        let Some((hevc, yuv)) = common::ensure(f) else { return };
        let (hvcc, samples) = to_hvcc(&std::fs::read(hevc).unwrap());
        let mut dec = Decoder::from_hvcc(&hvcc).unwrap();
        assert_eq!(dec.nal_length_size(), Some(4));
        let mut pics = Vec::new();
        for (i, s) in samples.iter().enumerate() {
            pics.extend(dec.decode(s, i as i64 * 1000).unwrap());
        }
        pics.extend(dec.flush());
        let reference = std::fs::read(yuv).unwrap();
        common::compare(&pics, &reference, f.width as usize, f.height as usize, f.bit_depth).unwrap();
        let mut pts: Vec<i64> = pics.iter().map(|p| p.pts).collect();
        pts.sort();
        assert_eq!(pts, (0..samples.len() as i64).map(|i| i * 1000).collect::<Vec<_>>());
        let p0 = &pics[0];
        assert!(p0.key);
        assert_eq!(p0.bit_depth, f.bit_depth);
        assert_eq!((p0.y_stride, p0.uv_stride), (f.width as usize, f.width as usize / 2));
    }
}

fn xorshift(seed: &mut u64) -> u64 {
    *seed ^= *seed << 13;
    *seed ^= *seed >> 7;
    *seed ^= *seed << 17;
    *seed
}

/// Damaged streams must never panic or hang; errors are fine.
#[test]
fn corrupted_streams_do_not_panic() {
    for name in ["medium", "bframes", "intra_main10", "rect_amp", "weightp"] {
        let f = common::fixture(name);
        let Some((hevc, _)) = common::ensure(f) else { return };
        let data = std::fs::read(hevc).unwrap();
        let mut seed = 0x1234_5678_9abc_def0u64 ^ name.len() as u64;
        for round in 0..12 {
            let mut d = data.clone();
            for _ in 0..(1 + round * 3) {
                let pos = 100 + (xorshift(&mut seed) as usize) % (d.len() - 100);
                d[pos] ^= 1 << (xorshift(&mut seed) % 8);
            }
            if round % 4 == 3 {
                d.truncate(d.len() * 2 / 3);
            }
            for threads in [1, 4] {
                let mut dec = Decoder::with_threads(threads);
                for au in common::split_access_units(&d) {
                    let _ = dec.decode(au, 0);
                }
                let _ = dec.flush();
                let _ = dec.take_error();
            }
        }
    }
}

#[test]
fn garbage_input_is_rejected_gracefully() {
    let mut seed = 42u64;
    for len in [0usize, 1, 5, 100, 5000] {
        for _ in 0..20 {
            let mut g: Vec<u8> = (0..len).map(|_| xorshift(&mut seed) as u8).collect();
            if len > 10 {
                g[..4].copy_from_slice(&[0, 0, 0, 1]);
            }
            let mut dec = Decoder::new();
            let _ = dec.decode(&g, 0);
            let _ = dec.flush();
        }
    }
    assert!(Decoder::from_hvcc(&[1, 2, 3]).is_err());
}
