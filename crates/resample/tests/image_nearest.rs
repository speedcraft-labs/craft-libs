use craft_resample::{
    NearestAlignment, downsample2_clamped_rgba, downsample2_floor_rgba, downsample2_floor_rgba_f32, reduce_box_f32, resize_bilinear_u8_coverage,
    resize_nearest,
};
use proptest::prelude::*;

proptest! {
    #[test]
    fn constant_images_stay_constant(
        sw in 1usize..18, sh in 1usize..18, dw in 1usize..18, dh in 1usize..18,
        channels in 1usize..5, value in any::<u8>(),
    ) {
        let source = vec![value; sw * sh * channels];
        for alignment in [NearestAlignment::Corner, NearestAlignment::Center] {
            let output = resize_nearest(&source, [sw, sh], [dw, dh], channels, alignment)
                .expect("small valid dimensions");
            prop_assert_eq!(output, vec![value; dw * dh * channels]);
        }
    }

    #[test]
    fn categorical_values_are_never_invented(
        sw in 1usize..18, sh in 1usize..18, dw in 1usize..18, dh in 1usize..18,
        alignment in prop_oneof![Just(NearestAlignment::Corner), Just(NearestAlignment::Center)],
    ) {
        let source: Vec<u8> = (0..sw * sh).map(|i| ((i * 37 + 11) % 251) as u8).collect();
        let output = resize_nearest(&source, [sw, sh], [dw, dh], 1, alignment)
            .expect("small valid dimensions");
        prop_assert!(output.iter().all(|value| source.contains(value)));
    }
}

#[test]
fn both_alignments_preserve_identity_grid() {
    let source = [0, 1, 2, 3, 4, 5];
    for alignment in [NearestAlignment::Corner, NearestAlignment::Center] {
        assert_eq!(resize_nearest(&source, [3, 2], [3, 2], 1, alignment), Some(source.to_vec()));
    }
}

proptest! {
    #[test]
    fn nearest_alignments_match_legacy_coordinates(
        sw in 1usize..18, sh in 1usize..18, dw in 1usize..18, dh in 1usize..18,
    ) {
        let source = (0..sw * sh).collect::<Vec<_>>();
        for alignment in [NearestAlignment::Corner, NearestAlignment::Center] {
            let source = &source;
            let expected = (0..dh).flat_map(|y| (0..dw).map(move |x| {
                let sx = match alignment {
                    NearestAlignment::Corner => x * sw / dw,
                    NearestAlignment::Center => (((x as f64 + 0.5) * sw as f64 / dw as f64) as usize).min(sw - 1),
                };
                let sy = match alignment {
                    NearestAlignment::Corner => y * sh / dh,
                    NearestAlignment::Center => (((y as f64 + 0.5) * sh as f64 / dh as f64) as usize).min(sh - 1),
                };
                source[sy * sw + sx]
            })).collect::<Vec<_>>();
            prop_assert_eq!(resize_nearest(&source, [sw, sh], [dw, dh], 1, alignment), Some(expected));
        }
    }
}

#[test]
fn rejects_invalid_sizes_and_short_input() {
    assert_eq!(resize_nearest(&[1u8], [0, 1], [1, 1], 1, NearestAlignment::Corner), None);
    assert_eq!(resize_nearest(&[1u8], [2, 1], [1, 1], 1, NearestAlignment::Corner), None);
}

proptest! {
    #[test]
    fn integer_box_reduction_preserves_constants(
        dw in 1usize..12, dh in 1usize..12, fx in 1usize..5, fy in 1usize..5,
        channels in 1usize..5, value in -100.0f32..100.0f32,
    ) {
        let source = vec![value; dw * fx * dh * fy * channels];
        let output = reduce_box_f32(&source, [dw * fx, dh * fy], [dw, dh], channels)
            .expect("exact integer shrink");
        prop_assert!(output.iter().all(|v| (*v - value).abs() < 0.001));
    }
}

#[test]
fn box_reducer_rejects_noninteger_ratios_and_enlargements() {
    assert_eq!(reduce_box_f32(&[1.0; 6], [3, 2], [2, 1], 1), None);
    assert_eq!(reduce_box_f32(&[1.0; 4], [2, 2], [4, 2], 1), None);
}

fn legacy_bilinear_u8(source: &[u8], sw: usize, sh: usize, dw: usize, dh: usize) -> Vec<u8> {
    let at = |x: usize, y: usize| f64::from(source[y.min(sh - 1) * sw + x.min(sw - 1)]);
    let mut out = Vec::with_capacity(dw * dh);
    for y in 0..dh {
        let fy = ((y as f64 + 0.5) * sh as f64 / dh as f64 - 0.5).max(0.0);
        let (y0, ty) = (fy.floor() as usize, fy.fract());
        for x in 0..dw {
            let fx = ((x as f64 + 0.5) * sw as f64 / dw as f64 - 0.5).max(0.0);
            let (x0, tx) = (fx.floor() as usize, fx.fract());
            let top = at(x0, y0) * (1.0 - tx) + at(x0 + 1, y0) * tx;
            let bottom = at(x0, y0 + 1) * (1.0 - tx) + at(x0 + 1, y0 + 1) * tx;
            out.push((top * (1.0 - ty) + bottom * ty).round().clamp(0.0, 255.0) as u8);
        }
    }
    out
}

proptest! {
    #[test]
    fn coverage_resize_matches_legacy_coordinate_and_rounding(
        sw in 1usize..12, sh in 1usize..12, dw in 1usize..12, dh in 1usize..12,
        source in prop::collection::vec(any::<u8>(), 1..144),
    ) {
        prop_assume!(source.len() >= sw * sh);
        let source = &source[..sw * sh];
        prop_assert_eq!(
            resize_bilinear_u8_coverage(source, [sw, sh], [dw, dh]),
            Some(legacy_bilinear_u8(source, sw, sh, dw, dh)),
        );
    }
}

#[test]
fn odd_pyramid_levels_clamp_the_edge_and_round_up() {
    let input = [[0.0; 4]; 3];
    let (w, h, output) = downsample2_clamped_rgba(&input, 3, 1).expect("non-empty image");
    assert_eq!((w, h), (2, 1));
    assert_eq!(output, vec![[0.0; 4]; 2]);
}

#[test]
fn floor_pyramid_levels_drop_odd_trailing_rows_and_columns() {
    let input = (0..15).map(|v| [v as f32; 4]).collect::<Vec<_>>();
    let (w, h, output) = downsample2_floor_rgba(&input, 5, 3).expect("non-empty image");
    assert_eq!((w, h), (2, 1));
    assert_eq!(output, vec![[3.0; 4], [5.0; 4]]);
    let packed = input.iter().flatten().copied().collect::<Vec<_>>();
    let (packed_w, packed_h, packed_output) = downsample2_floor_rgba_f32(&packed, 5, 3).expect("packed non-empty image");
    assert_eq!((packed_w, packed_h), (w, h));
    assert_eq!(packed_output, output.iter().flatten().copied().collect::<Vec<_>>());
}

proptest! {
    #[test]
    fn rgba_pyramid_preserves_constant_odd_or_even(
        width in 1usize..20, height in 1usize..20,
        pixel in prop::array::uniform4(-100.0f32..100.0f32),
    ) {
        let input = vec![pixel; width * height];
        let (_, _, output) = downsample2_clamped_rgba(&input, width, height)
            .expect("small non-empty image");
        prop_assert!(output.iter().flatten().zip(pixel).all(|(actual, expected)| (*actual - expected).abs() < 0.001));
    }
}
