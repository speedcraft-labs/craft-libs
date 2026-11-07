//! Paired, same-binary comparison of the old three-box cascade and deployed RecursiveRaw quality.
//! The output change is intentional; correctness is gated separately by the impulse variance and
//! shape properties in `contracts.rs` and `variance.rs` against the calibrated sampled Gaussian.

use craft_bench::{Config, Paired};
use craft_blur::{Cancel, Edge, Gaussian, Quality, Scratch, Shape};

struct Input {
    sigma: f32,
    shape: Shape,
    pixels: Vec<f32>,
}

fn run(input: &Input, quality: Quality) -> Vec<f32> {
    let mut pixels = input.pixels.clone();
    let filter = Gaussian::new(input.sigma, quality).expect("bench sigma is valid");
    filter.apply(&mut pixels, input.shape, Edge::Clamp, &mut Scratch::default(), Cancel::Never).expect("valid plane");
    pixels
}

#[test]
#[ignore = "paired 4 MP timing; run --release --test recursive_gaussian_bench -- --ignored --nocapture"]
fn paired_box_vs_recursive_by_sigma() -> Result<(), Box<dyn std::error::Error>> {
    let shape = Shape::new(2048, 2048, 1)?;
    let inputs = [1.0_f32, 4.0, 8.0, 16.0, 32.0, 64.0].into_iter().map(|sigma| {
        let pixels = (0..shape.samples()).map(|i| ((i * 17 % 1021) as f32) / 1021.0).collect();
        (format!("sigma={sigma}"), Input { sigma, shape, pixels })
    });
    let report = Paired::new("craft-blur: three-box vs RecursiveRaw")
        .old(|input: &Input| run(input, Quality::BoxApprox { passes: 3 }))
        .new(|input: &Input| run(input, Quality::RecursiveRaw))
        .inputs(inputs)
        // Gaussian generations intentionally differ. Both outputs must be well-formed finite
        // images; the documented independent oracle tests establish the numeric error bounds.
        .check(|old, new| old.len() == new.len() && old.iter().chain(new).all(|value| value.is_finite()))
        .run(&Config::default())?;
    println!("{}", report.to_markdown());
    if let Some(path) = std::env::var_os("CRAFT_BLUR_BENCH_JSON") {
        std::fs::write(path, report.to_json())?;
    }
    Ok(())
}
