use std::env;
use std::error::Error;
use std::hint::black_box;
use std::path::{Path, PathBuf};

use craft_bench::{Config, Paired, report::Revs};
use craft_resample::{NearestAlignment, downsample2_clamped_rgba, reduce_box_f32, resize_nearest};
use rayon::prelude::*;

const SIDE: usize = 1024;

fn tiled_corpus_image(path: &Path) -> Result<Vec<[f32; 4]>, Box<dyn Error>> {
    let rgba = image::open(path)?.to_rgba32f();
    let (width, height) = (rgba.width() as usize, rgba.height() as usize);
    let pixels = rgba.into_raw().chunks_exact(4).map(|p| [p[0], p[1], p[2], p[3]]).collect::<Vec<_>>();
    if width == 0 || height == 0 || pixels.is_empty() {
        return Err("empty corpus image".into());
    }
    Ok((0..SIDE * SIDE).map(|i| pixels[(i / SIDE % height) * width + i % SIDE % width]).collect())
}

fn old_box(input: &Vec<f32>) -> Vec<f32> {
    let mut output = vec![0.0; (SIDE / 2) * (SIDE / 2) * 4];
    output.par_chunks_mut(4).enumerate().for_each(|(pixel, out)| {
        let (x, y) = (pixel % (SIDE / 2), pixel / (SIDE / 2));
        for dy in 0..2 {
            for dx in 0..2 {
                let i = ((2 * y + dy) * SIDE + 2 * x + dx) * 4;
                for c in 0..4 {
                    out[c] += input[i + c];
                }
            }
        }
        for c in 0..4 {
            out[c] *= 0.25;
        }
    });
    output
}

fn old_pyramid(input: &Vec<[f32; 4]>) -> Vec<[f32; 4]> {
    let mut output = vec![[0.0; 4]; (SIDE / 2) * (SIDE / 2)];
    output.par_iter_mut().enumerate().for_each(|(pixel, out)| {
        let (x, y) = (pixel % (SIDE / 2), pixel / (SIDE / 2));
        for (dx, dy) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
            let p = input[(2 * y + dy) * SIDE + 2 * x + dx];
            for c in 0..4 {
                out[c] += p[c];
            }
        }
        for c in 0..4 {
            out[c] *= 0.25;
        }
    });
    output
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
        .run(&Config { revs: Revs { old: Some("legacy-inline".into()), new: Some(env!("CARGO_PKG_VERSION").into()) }, ..Config::default() })?;
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
    let pixels = tiled_corpus_image(&corpus)?;
    let label = corpus.file_stem().and_then(|s| s.to_str()).unwrap_or("corpus");
    let box_src = pixels.iter().flat_map(|p| p.iter().copied()).collect::<Vec<_>>();
    bench(
        &format!("{label} integer box 1024→512"),
        old_box,
        |src: &Vec<f32>| reduce_box_f32(src, [SIDE, SIDE], [SIDE / 2, SIDE / 2], 4).unwrap_or_default(),
        box_src,
        &output.join("box.json"),
    )?;
    bench(
        &format!("{label} clamped pyramid 1024→512"),
        old_pyramid,
        |src| downsample2_clamped_rgba(src, SIDE, SIDE).map(|(_, _, pixels)| pixels).unwrap_or_default(),
        pixels.clone(),
        &output.join("pyramid.json"),
    )?;
    let mask = pixels.iter().map(|p| (p[3] * 255.0 + 0.5) as u8).collect::<Vec<_>>();
    bench(
        &format!("{label} corner mask 1024→512"),
        |src: &Vec<u8>| (0..SIDE / 2).flat_map(|y| (0..SIDE / 2).map(move |x| src[2 * y * SIDE + 2 * x])).collect::<Vec<_>>(),
        |src| resize_nearest(src, [SIDE, SIDE], [SIDE / 2, SIDE / 2], 1, NearestAlignment::Corner).unwrap_or_default(),
        mask,
        &output.join("mask.json"),
    )?;
    Ok(())
}
