use craft_resample::{NearestAlignment, reduce_box_f32, resize_nearest};
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
