use std::env;
use std::error::Error;
use std::hint::black_box;
use std::path::{Path, PathBuf};

use craft_bench::{Config, Paired, report::Revs};
use craft_resample::{
    NearestAlignment, downsample2_clamped_rgba, downsample2_floor_rgba_f32, reduce_box_f32, resize_bilinear_u8_coverage, resize_nearest,
};
use rayon::prelude::*;

const MAX_BATCH: usize = 64;

#[derive(Clone)]
struct Pixels {
    width: usize,
    height: usize,
    rgba: Vec<[f32; 4]>,
    flat: Vec<f32>,
    gray: Vec<f32>,
    mask: Vec<u8>,
}

fn corpus_image(path: &Path) -> Result<Pixels, Box<dyn Error>> {
    let rgba = image::open(path)?.to_rgba32f();
    let (width, height) = (rgba.width() as usize, rgba.height() as usize);
    let flat = rgba.into_raw();
    let pixels = flat.as_chunks::<4>().0.to_vec();
    let gray = pixels.iter().map(|px| px[0]).collect();
    if width < 2 || height < 2 || pixels.is_empty() || !width.is_multiple_of(2) || !height.is_multiple_of(2) {
        return Err("benchmark corpus image must have even dimensions of at least 2×2".into());
    }
    let mask = pixels.iter().map(|px| (px[3] * 255.0 + 0.5) as u8).collect();
    Ok(Pixels { width, height, rgba: pixels, flat, gray, mask })
}

fn repeated<T>(batch: usize, mut f: impl FnMut() -> T) -> T {
    let mut result = f();
    for _ in 1..batch {
        result = f();
    }
    result
}

fn old_box(input: &Pixels, channels: usize) -> Vec<f32> {
    let (dw, dh) = (input.width / 2, input.height / 2);
    let source = if channels == 1 { &input.gray } else { &input.flat };
    let mut output = vec![0.0; dw * dh * channels];
    output.par_chunks_mut(dw * channels).enumerate().for_each(|(y, row)| {
        for x in 0..dw {
            let dest = &mut row[x * channels..x * channels + channels];
            for dy in 0..2 {
                for dx in 0..2 {
                    let i = ((2 * y + dy) * input.width + 2 * x + dx) * channels;
                    for (c, value) in dest.iter_mut().enumerate() {
                        *value += source[i + c];
                    }
                }
            }
            for value in dest {
                *value *= 0.25;
            }
        }
    });
    output
}

fn old_pyramid_level(input: &[[f32; 4]], width: usize, height: usize) -> (usize, usize, Vec<[f32; 4]>) {
    let (dw, dh) = (width.div_ceil(2), height.div_ceil(2));
    let mut output = vec![[0.0; 4]; dw * dh];
    output.par_chunks_mut(dw).enumerate().for_each(|(y, row)| {
        for (x, out) in row.iter_mut().enumerate() {
            for (dx, dy) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
                let sx = (2 * x + dx).min(width - 1);
                let sy = (2 * y + dy).min(height - 1);
                let px = input[sy * width + sx];
                for (acc, value) in out.iter_mut().zip(px) {
                    *acc += value;
                }
            }
            for value in out.iter_mut() {
                *value *= 0.25;
            }
        }
    });
    (dw, dh, output)
}

fn new_clamped_pyramid(input: &Pixels) -> Vec<Vec<[f32; 4]>> {
    let mut levels = Vec::new();
    let mut current = input.rgba.as_slice();
    let (mut width, mut height) = (input.width, input.height);
    while width > 1 || height > 1 {
        let Some((next_width, next_height, next)) = downsample2_clamped_rgba(current, width, height) else { break };
        levels.push(next);
        (width, height) = (next_width, next_height);
        current = levels.last().map(Vec::as_slice).unwrap_or_default();
    }
    levels
}

fn old_clamped_pyramid(input: &Pixels) -> Vec<Vec<[f32; 4]>> {
    let mut levels = Vec::new();
    let mut current = input.rgba.as_slice();
    let (mut width, mut height) = (input.width, input.height);
    while width > 1 || height > 1 {
        let (next_width, next_height, next) = old_pyramid_level(current, width, height);
        levels.push(next);
        (width, height) = (next_width, next_height);
        current = levels.last().map(Vec::as_slice).unwrap_or_default();
    }
    levels
}

fn old_pyramid_flat_level(input: &[f32], width: usize, height: usize) -> (usize, usize, Vec<f32>) {
    let (dw, dh) = ((width / 2).max(1), (height / 2).max(1));
    let mut output = vec![0.0; dw * dh * 4];
    output.par_chunks_mut(dw * 4).enumerate().for_each(|(y, row)| {
        for x in 0..dw {
            for (dx, dy) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
                let sx = (2 * x + dx).min(width - 1);
                let sy = (2 * y + dy).min(height - 1);
                let i = (sy * width + sx) * 4;
                for c in 0..4 {
                    row[x * 4 + c] += input[i + c];
                }
            }
            for c in 0..4 {
                row[x * 4 + c] *= 0.25;
            }
        }
    });
    (dw, dh, output)
}

fn old_floor_pyramid(input: &Pixels) -> Vec<Vec<f32>> {
    let mut levels = Vec::new();
    let mut current = input.flat.as_slice();
    let (mut width, mut height) = (input.width, input.height);
    while width > 1 || height > 1 {
        let (next_width, next_height, next) = old_pyramid_flat_level(current, width, height);
        levels.push(next);
        (width, height) = (next_width, next_height);
        current = levels.last().map(Vec::as_slice).unwrap_or_default();
    }
    levels
}

fn new_floor_pyramid(input: &Pixels) -> Vec<Vec<f32>> {
    let mut levels = Vec::new();
    let mut current = input.flat.as_slice();
    let (mut width, mut height) = (input.width, input.height);
    while width > 1 || height > 1 {
        let Some((next_width, next_height, next)) = downsample2_floor_rgba_f32(current, width, height) else { break };
        levels.push(next);
        (width, height) = (next_width, next_height);
        current = levels.last().map(Vec::as_slice).unwrap_or_default();
    }
    levels
}

fn old_coverage(input: &Pixels) -> Vec<u8> {
    let (sw, sh, dw, dh) = (input.width, input.height, input.width / 2, input.height / 2);
    let at = |x: usize, y: usize| f64::from(input.mask[y.min(sh - 1) * sw + x.min(sw - 1)]);
    let mut output = Vec::with_capacity(dw * dh);
    for y in 0..dh {
        let fy = ((y as f64 + 0.5) * sh as f64 / dh as f64 - 0.5).max(0.0);
        let (y0, ty) = (fy.floor() as usize, fy.fract());
        for x in 0..dw {
            let fx = ((x as f64 + 0.5) * sw as f64 / dw as f64 - 0.5).max(0.0);
            let (x0, tx) = (fx.floor() as usize, fx.fract());
            let top = at(x0, y0) * (1.0 - tx) + at(x0 + 1, y0) * tx;
            let bottom = at(x0, y0 + 1) * (1.0 - tx) + at(x0 + 1, y0 + 1) * tx;
            output.push((top * (1.0 - ty) + bottom * ty).round().clamp(0.0, 255.0) as u8);
        }
    }
    output
}

fn old_nearest(input: &Pixels) -> Vec<u8> {
    let (dw, dh) = (input.width / 2, input.height / 2);
    (0..dh).flat_map(|y| (0..dw).map(move |x| input.mask[(y * input.height / dh) * input.width + (x * input.width / dw)])).collect()
}

fn old_nearest_center(input: &Pixels) -> Vec<u8> {
    let (dw, dh) = (input.width / 2, input.height / 2);
    (0..dh)
        .flat_map(|y| {
            (0..dw).map(move |x| {
                let sx = (((x as f64 + 0.5) * input.width as f64 / dw as f64) as usize).min(input.width - 1);
                let sy = (((y as f64 + 0.5) * input.height as f64 / dh as f64) as usize).min(input.height - 1);
                input.mask[sy * input.width + sx]
            })
        })
        .collect()
}

fn bench<I, O>(name: &str, old: impl Fn(&I) -> O + 'static, new: impl Fn(&I) -> O + 'static, input: I, out: &Path) -> Result<(), Box<dyn Error>>
where
    I: 'static,
    O: PartialEq + 'static,
{
    let report = Paired::new(name)
        .old(move |input| black_box(old(input)))
        .new(move |input| black_box(new(input)))
        .inputs([(name.to_owned(), input)])
        .equal()
        .run(&Config {
            repetitions: 40,
            revs: Revs { old: Some("legacy-inline".into()), new: Some(env!("CARGO_PKG_VERSION").into()) },
            ..Config::default()
        })?;
    std::fs::write(out, report.to_json())?;
    println!("{}", report.to_markdown());
    if let Err(error) = report.require_publishable() {
        eprintln!("benchmark is not publishable: {error}");
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut args = env::args_os().skip(1);
    let corpus = PathBuf::from(args.next().ok_or("usage: image_bench <corpus-image> <output-dir>")?);
    let output = PathBuf::from(args.next().ok_or("usage: image_bench <corpus-image> <output-dir>")?);
    std::fs::create_dir_all(&output)?;
    let input = corpus_image(&corpus)?;
    let label = corpus.file_stem().and_then(|s| s.to_str()).unwrap_or("corpus");
    let dims = format!("{}×{}", input.width, input.height);
    let (dw, dh) = (input.width / 2, input.height / 2);
    let batch = (65_536 / (input.width * input.height)).clamp(1, MAX_BATCH);
    let batch_label = format!("{label} {dims}→{dw}×{dh} (×{batch})");

    bench(
        &format!("{batch_label} integer box"),
        move |src: &Pixels| repeated(batch, || old_box(src, 4)),
        move |src| repeated(batch, || reduce_box_f32(&src.flat, [src.width, src.height], [dw, dh], 4).unwrap_or_default()),
        input.clone(),
        &output.join("box.json"),
    )?;
    bench(
        &format!("{batch_label} grayscale integer box"),
        move |src: &Pixels| repeated(batch, || old_box(src, 1)),
        move |src| repeated(batch, || reduce_box_f32(&src.gray, [src.width, src.height], [dw, dh], 1).unwrap_or_default()),
        input.clone(),
        &output.join("box-gray.json"),
    )?;
    bench(
        &format!("{batch_label} clamped mip pyramid"),
        move |src: &Pixels| repeated(batch, || old_clamped_pyramid(src)),
        move |src| repeated(batch, || new_clamped_pyramid(src)),
        input.clone(),
        &output.join("pyramid.json"),
    )?;
    bench(
        &format!("{batch_label} floor mip pyramid"),
        move |src: &Pixels| repeated(batch, || old_floor_pyramid(src)),
        move |src| repeated(batch, || new_floor_pyramid(src)),
        input.clone(),
        &output.join("pyramid-floor.json"),
    )?;
    bench(
        &format!("{batch_label} corner mask"),
        move |src: &Pixels| repeated(batch, || old_nearest(src)),
        move |src| repeated(batch, || resize_nearest(&src.mask, [src.width, src.height], [dw, dh], 1, NearestAlignment::Corner).unwrap_or_default()),
        input.clone(),
        &output.join("mask.json"),
    )?;
    bench(
        &format!("{batch_label} center mask"),
        move |src: &Pixels| repeated(batch, || old_nearest_center(src)),
        move |src| repeated(batch, || resize_nearest(&src.mask, [src.width, src.height], [dw, dh], 1, NearestAlignment::Center).unwrap_or_default()),
        input.clone(),
        &output.join("mask-center.json"),
    )?;
    bench(
        &format!("{batch_label} bilinear coverage"),
        move |src: &Pixels| repeated(batch, || old_coverage(src)),
        move |src| repeated(batch, || resize_bilinear_u8_coverage(&src.mask, [src.width, src.height], [dw, dh]).unwrap_or_default()),
        input,
        &output.join("coverage.json"),
    )?;
    Ok(())
}
