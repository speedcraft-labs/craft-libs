//! Rational-ratio polyphase FIR resampler.
//!
//! The reference definition is the direct form: zero-stuff the input by `L`, convolve with the
//! prototype FIR `h`, keep every `M`-th sample.
//!
//! ```text
//! u[m] = x[m / L]  if L divides m, else 0
//! y[n] = (h * u)[n * M] = sum_k h[k] * u[n*M - k]
//! ```
//!
//! The polyphase form never builds `u`. Output `n` sits at upsampled index `n*M = i*L + p`
//! (`i` the whole input position, `p < L` the phase), and
//!
//! ```text
//! y[n] = sum_q h[p + q*L] * x[i - q]
//! ```
//!
//! [`Polyphase`] stores `coeffs[p * taps + q] = h[p + q*L]` (zero past the end of `h`) and walks
//! `(i, p)` with an integer accumulator: `p += M mod L`, `i += M div L`, carrying one into `i`
//! when `p` reaches `L`. All arithmetic on positions is exact integer arithmetic, so there is no
//! phase drift however long the stream runs. Samples outside the input read as zero, so
//! [`Polyphase::process`] over `0..out_len(x.len())` is the full convolution output.
//!
//! The equality of the two forms for every input, and the DC gain of a per-phase normalised
//! prototype, are proved in Lean 4 in `lean/` (see `lean/TRUST.md`).

#[cfg(feature = "rayon")]
use rayon::prelude::*;
use std::f64::consts::PI;
use std::ops::{Add, Mul};

/// Pixel-grid convention for nearest-neighbour resizing.
///
/// Both conventions are used by image formats and model pipelines. Naming the convention makes
/// compatibility explicit while sharing the checked indexing and allocation logic.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NearestAlignment {
    /// Map destination pixel `(x, y)` to `floor(x * source_width / dest_width)` (top-left aligned).
    Corner,
    /// Map destination pixel centers to the closest source pixel center.
    Center,
}

/// Nearest-neighbour resize of a packed row-major image or mask.
///
/// Returns `None` for zero dimensions, an undersized input, or an unrepresentable allocation.
/// The output contains only values copied from the source, so this is suitable for categorical
/// labels as well as exact legacy mask resampling. `channels` may be one for masks or larger for
/// packed pixel data.
pub fn resize_nearest<T: Copy>(
    source: &[T],
    source_size: [usize; 2],
    dest_size: [usize; 2],
    channels: usize,
    alignment: NearestAlignment,
) -> Option<Vec<T>> {
    let [sw, sh] = source_size;
    let [dw, dh] = dest_size;
    if sw == 0 || sh == 0 || dw == 0 || dh == 0 || channels == 0 {
        return None;
    }
    let source_len = sw.checked_mul(sh)?.checked_mul(channels)?;
    let dest_len = dw.checked_mul(dh)?.checked_mul(channels)?;
    if source.len() < source_len {
        return None;
    }
    let mut out = Vec::new();
    out.try_reserve_exact(dest_len).ok()?;
    if sw == dw && sh == dh {
        out.extend_from_slice(&source[..source_len]);
        return Some(out);
    }
    let xs = nearest_indices(sw, dw, alignment)?;
    let ys = nearest_indices(sh, dh, alignment)?;
    for &sy in &ys {
        for &sx in &xs {
            let start = (sy * sw + sx) * channels;
            out.extend_from_slice(&source[start..start + channels]);
        }
    }
    Some(out)
}

/// Bilinearly resize a single-channel 8-bit coverage mask using pixel-center coordinates.
///
/// This is for continuous coverage, not categorical labels: intermediate values are expected.
/// Edge samples clamp to the nearest source edge, and results round to the nearest integer.
pub fn resize_bilinear_u8_coverage(source: &[u8], source_size: [usize; 2], dest_size: [usize; 2]) -> Option<Vec<u8>> {
    let [sw, sh] = source_size;
    let [dw, dh] = dest_size;
    if sw == 0 || sh == 0 || dw == 0 || dh == 0 {
        return None;
    }
    let source_len = sw.checked_mul(sh)?;
    let dest_len = dw.checked_mul(dh)?;
    if source.len() < source_len {
        return None;
    }
    let xs = coverage_axis(sw, dw)?;
    let ys = coverage_axis(sh, dh)?;
    let mut out = Vec::new();
    out.try_reserve_exact(dest_len).ok()?;
    for y in &ys {
        let top_row = y.lo * sw;
        let bottom_row = y.hi * sw;
        for x in &xs {
            let tx = x.weight;
            let ty = y.weight;
            let top = f64::from(source[top_row + x.lo]) * (1.0 - tx) + f64::from(source[top_row + x.hi]) * tx;
            let bottom = f64::from(source[bottom_row + x.lo]) * (1.0 - tx) + f64::from(source[bottom_row + x.hi]) * tx;
            out.push((top * (1.0 - ty) + bottom * ty).round().clamp(0.0, 255.0) as u8);
        }
    }
    Some(out)
}

#[derive(Clone, Copy)]
struct CoverageTap {
    lo: usize,
    hi: usize,
    weight: f64,
}

fn coverage_axis(source: usize, dest: usize) -> Option<Vec<CoverageTap>> {
    let mut taps = Vec::new();
    taps.try_reserve_exact(dest).ok()?;
    for position in 0..dest {
        let sample = ((position as f64 + 0.5) * source as f64 / dest as f64 - 0.5).max(0.0);
        let lo = (sample.floor() as usize).min(source - 1);
        taps.push(CoverageTap { lo, hi: lo.saturating_add(1).min(source - 1), weight: sample.fract() });
    }
    Some(taps)
}

/// Box-reduce an `f32` image by exact integer ratios.
///
/// This reproduces the common integer-footprint average used by material and texture pipelines.
/// Non-integer ratios are rejected so callers can retain their established fallback filter.
pub fn reduce_box_f32(source: &[f32], source_size: [usize; 2], dest_size: [usize; 2], channels: usize) -> Option<Vec<f32>> {
    let [sw, sh] = source_size;
    let [dw, dh] = dest_size;
    if sw == 0 || sh == 0 || dw == 0 || dh == 0 || channels == 0 || dw > sw || dh > sh || !sw.is_multiple_of(dw) || !sh.is_multiple_of(dh) {
        return None;
    }
    let source_len = sw.checked_mul(sh)?.checked_mul(channels)?;
    if source.len() < source_len {
        return None;
    }
    let (fx, fy) = (sw / dw, sh / dh);
    let inv = 1.0 / (fx * fy) as f32;
    let reduction = BoxReduction { sw, dw, dh, channels, fx, fy, inv };
    match channels {
        1 => reduce_box_f32_const::<1>(source, reduction),
        4 => reduce_box_f32_const::<4>(source, reduction),
        _ => reduce_box_f32_dynamic(source, reduction),
    }
}

#[derive(Clone, Copy)]
struct BoxReduction {
    sw: usize,
    dw: usize,
    dh: usize,
    channels: usize,
    fx: usize,
    fy: usize,
    inv: f32,
}

fn reduce_box_f32_const<const CHANNELS: usize>(source: &[f32], reduction: BoxReduction) -> Option<Vec<f32>> {
    let BoxReduction { sw, dw, dh, fx, fy, inv, .. } = reduction;
    let dest_len = dw.checked_mul(dh)?.checked_mul(CHANNELS)?;
    let mut out = Vec::new();
    out.try_reserve_exact(dest_len).ok()?;
    out.resize(dest_len, 0.0);
    let reduce_row = |y: usize, row: &mut [f32]| {
        for x in 0..dw {
            let dest = &mut row[x * CHANNELS..(x + 1) * CHANNELS];
            for j in 0..fy {
                for i in 0..fx {
                    let si = ((y * fy + j) * sw + x * fx + i) * CHANNELS;
                    for c in 0..CHANNELS {
                        dest[c] += source[si + c];
                    }
                }
            }
            for value in dest {
                *value *= inv;
            }
        }
    };
    #[cfg(feature = "rayon")]
    out.par_chunks_mut(dw * CHANNELS).enumerate().for_each(|(y, row)| reduce_row(y, row));
    #[cfg(not(feature = "rayon"))]
    out.chunks_mut(dw * CHANNELS).enumerate().for_each(|(y, row)| reduce_row(y, row));
    Some(out)
}

fn reduce_box_f32_dynamic(source: &[f32], reduction: BoxReduction) -> Option<Vec<f32>> {
    let BoxReduction { sw, dw, dh, channels, fx, fy, inv } = reduction;
    let dest_len = dw.checked_mul(dh)?.checked_mul(channels)?;
    let mut out = Vec::new();
    out.try_reserve_exact(dest_len).ok()?;
    out.resize(dest_len, 0.0);
    let reduce_row = |y: usize, row: &mut [f32]| {
        for x in 0..dw {
            let dest = &mut row[x * channels..(x + 1) * channels];
            for j in 0..fy {
                for i in 0..fx {
                    let si = ((y * fy + j) * sw + x * fx + i) * channels;
                    for c in 0..channels {
                        dest[c] += source[si + c];
                    }
                }
            }
            for value in dest {
                *value *= inv;
            }
        }
    };
    #[cfg(feature = "rayon")]
    out.par_chunks_mut(dw * channels).enumerate().for_each(|(y, row)| reduce_row(y, row));
    #[cfg(not(feature = "rayon"))]
    out.chunks_mut(dw * channels).enumerate().for_each(|(y, row)| reduce_row(y, row));
    Some(out)
}

/// Build one RGBA pyramid level with a clamped 2×2 box footprint.
///
/// Odd source dimensions round up; the final footprint repeats the last row or column, matching
/// the common compositor minification pyramid convention.
pub fn downsample2_clamped_rgba(source: &[[f32; 4]], width: usize, height: usize) -> Option<(usize, usize, Vec<[f32; 4]>)> {
    downsample2_rgba(source, width, height, true)
}

/// Build one RGBA pyramid level with the floor-sized 2×2 convention used by FilmCraft.
///
/// Odd trailing rows and columns are dropped. A one-pixel dimension is retained and sampled with
/// clamped edges.
pub fn downsample2_floor_rgba(source: &[[f32; 4]], width: usize, height: usize) -> Option<(usize, usize, Vec<[f32; 4]>)> {
    downsample2_rgba(source, width, height, false)
}

/// Packed-float counterpart to [`downsample2_floor_rgba`], for RGBA buffers stored as a flat
/// row-major `f32` slice.
pub fn downsample2_floor_rgba_f32(source: &[f32], width: usize, height: usize) -> Option<(usize, usize, Vec<f32>)> {
    if width == 0 || height == 0 || source.len() < width.checked_mul(height)?.checked_mul(4)? {
        return None;
    }
    let (dw, dh) = ((width / 2).max(1), (height / 2).max(1));
    let mut out = Vec::new();
    out.try_reserve_exact(dw.checked_mul(dh)?.checked_mul(4)?).ok()?;
    out.resize(dw * dh * 4, 0.0);
    let reduce_row = |y: usize, row: &mut [f32]| {
        for x in 0..dw {
            for (dx, dy) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
                let index = ((2 * y + dy).min(height - 1) * width + (2 * x + dx).min(width - 1)) * 4;
                for channel in 0..4 {
                    row[x * 4 + channel] += source[index + channel];
                }
            }
            for channel in 0..4 {
                row[x * 4 + channel] *= 0.25;
            }
        }
    };
    #[cfg(feature = "rayon")]
    out.par_chunks_mut(dw * 4).enumerate().for_each(|(y, row)| reduce_row(y, row));
    #[cfg(not(feature = "rayon"))]
    out.chunks_mut(dw * 4).enumerate().for_each(|(y, row)| reduce_row(y, row));
    Some((dw, dh, out))
}

fn downsample2_rgba(source: &[[f32; 4]], width: usize, height: usize, round_up: bool) -> Option<(usize, usize, Vec<[f32; 4]>)> {
    if width == 0 || height == 0 || source.len() < width.checked_mul(height)? {
        return None;
    }
    let (dw, dh) = if round_up { (width.div_ceil(2), height.div_ceil(2)) } else { ((width / 2).max(1), (height / 2).max(1)) };
    let mut out = Vec::new();
    out.try_reserve_exact(dw.checked_mul(dh)?).ok()?;
    out.resize(dw * dh, [0.0; 4]);
    let reduce_row = |y: usize, row: &mut [[f32; 4]]| {
        for (x, px) in row.iter_mut().enumerate() {
            let (sx, sy) = (2 * x, 2 * y);
            let indices = [
                sy * width + sx,
                sy * width + (sx + 1).min(width - 1),
                (sy + 1).min(height - 1) * width + sx,
                (sy + 1).min(height - 1) * width + (sx + 1).min(width - 1),
            ];
            for index in indices {
                for (channel, value) in px.iter_mut().enumerate() {
                    *value += source[index][channel];
                }
            }
            px.iter_mut().for_each(|value| *value *= 0.25);
        }
    };
    #[cfg(feature = "rayon")]
    out.par_chunks_mut(dw).enumerate().for_each(|(y, row)| reduce_row(y, row));
    #[cfg(not(feature = "rayon"))]
    out.chunks_mut(dw).enumerate().for_each(|(y, row)| reduce_row(y, row));
    Some((dw, dh, out))
}

fn nearest_index(position: usize, source: usize, dest: usize, alignment: NearestAlignment) -> Option<usize> {
    let (n, d) = match alignment {
        NearestAlignment::Corner => ((position as u128).checked_mul(source as u128)?, dest as u128),
        NearestAlignment::Center => {
            let center = (position as u128).checked_mul(2)?.checked_add(1)?;
            (center.checked_mul(source as u128)?, (dest as u128).checked_mul(2)?)
        }
    };
    Some((n / d).min(source as u128 - 1) as usize)
}

fn nearest_indices(source: usize, dest: usize, alignment: NearestAlignment) -> Option<Vec<usize>> {
    let mut indices = Vec::new();
    indices.try_reserve_exact(dest).ok()?;
    for position in 0..dest {
        indices.push(nearest_index(position, source, dest, alignment)?);
    }
    Some(indices)
}

/// Sample and coefficient type of a [`Polyphase`] resampler.
pub trait Sample: Copy + Default + Add<Output = Self> + Mul<Output = Self> {}
impl Sample for f32 {}
impl Sample for f64 {}

/// Why a resampler could not be built.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    /// `L` or `M` is zero.
    ZeroRatio,
    /// The prototype filter is empty (or zero taps per phase were requested).
    EmptyPrototype,
    /// The tap table would exceed `usize`.
    TooLarge,
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Self::ZeroRatio => "upsample and downsample factors must be non-zero",
            Self::EmptyPrototype => "prototype filter must have at least one tap",
            Self::TooLarge => "tap table too large",
        })
    }
}

impl std::error::Error for Error {}

/// Polyphase resampler by `up / down`.
#[derive(Clone, Debug)]
pub struct Polyphase<S: Sample> {
    up: usize,
    down: usize,
    taps: usize,
    proto_len: usize,
    /// `coeffs[p * taps + q] = h[p + q * up]`, zero past the end of `h`.
    coeffs: Vec<S>,
}

impl<S: Sample> Polyphase<S> {
    /// Splits the prototype `h` (index 0 first) into `up` phases. `up` and `down` are used as
    /// given (not reduced): the direct form is defined for any positive pair.
    pub fn from_prototype(h: &[S], up: usize, down: usize) -> Result<Self, Error> {
        if up == 0 || down == 0 {
            return Err(Error::ZeroRatio);
        }
        if h.is_empty() {
            return Err(Error::EmptyPrototype);
        }
        let taps = h.len().div_ceil(up);
        let mut coeffs = vec![S::default(); up.checked_mul(taps).ok_or(Error::TooLarge)?];
        for (k, &c) in h.iter().enumerate() {
            if let Some(slot) = coeffs.get_mut((k % up) * taps + k / up) {
                *slot = c;
            }
        }
        Ok(Self { up, down, taps, proto_len: h.len(), coeffs })
    }

    /// `(up, down)`.
    pub fn ratio(&self) -> (usize, usize) {
        (self.up, self.down)
    }

    /// Taps per phase.
    pub fn taps_per_phase(&self) -> usize {
        self.taps
    }

    /// The coefficients of phase `p` (`h[p], h[p + L], ...`), if `p < L`.
    pub fn phase(&self, p: usize) -> Option<&[S]> {
        self.coeffs.get(p.checked_mul(self.taps)?..)?.get(..self.taps)
    }

    /// Length of the full convolution output for an input of `len` samples:
    /// `ceil(((len - 1) * L + N) / M)` where `N` is the prototype length; 0 for an empty input.
    pub fn out_len(&self, len: usize) -> usize {
        if len == 0 {
            return 0;
        }
        ((len - 1) * self.up + self.proto_len).div_ceil(self.down)
    }

    /// Output samples `first .. first + count` of the resampled stream. The position accumulator
    /// starts at `(first * M) divmod L` and is then advanced by integer steps.
    pub fn process(&self, x: &[S], first: usize, count: usize) -> Vec<S> {
        self.process_from(x, first as u128 * self.down as u128, count)
    }

    /// `count` outputs where output `n` sits at upsampled index `start + n*M`, i.e.
    /// `y[n] = (h * u)[start + n*M]`. [`Polyphase::process`] is `start = first * M`. Any `start`
    /// is allowed, so a filter centred on the output (taps reaching `lead` input samples ahead)
    /// is `start = lead * L + first * M`: the same theorem as a start offset of the direct form.
    pub fn process_from(&self, x: &[S], start: u128, count: usize) -> Vec<S> {
        let mut out = vec![S::default(); count];
        self.process_from_into(x, start, &mut out);
        out
    }

    /// [`Polyphase::process_from`] writing `out.len()` samples into `out`: no allocation, for
    /// real-time callers (for example a per-sample window of the last few inputs).
    pub fn process_from_into(&self, x: &[S], start: u128, out: &mut [S]) {
        let (mut i, mut p) = ((start / self.up as u128) as i64, (start % self.up as u128) as usize);
        let (step_i, step_p) = ((self.down / self.up) as i64, self.down % self.up);
        let len = x.len() as i64;
        for slot in out.iter_mut() {
            let mut acc = S::default();
            if let Some(w) = self.phase(p) {
                // taps q with 0 <= i - q < len
                let lo = (i - (len - 1)).max(0) as usize;
                let hi = if i < 0 { 0 } else { (i as usize + 1).min(self.taps) };
                for (q, &c) in w.iter().enumerate().take(hi).skip(lo) {
                    if let Some(&v) = x.get((i - q as i64) as usize) {
                        acc = acc + c * v;
                    }
                }
            }
            *slot = acc;
            i += step_i;
            p += step_p;
            if p >= self.up {
                p -= self.up;
                i += 1;
            }
        }
    }

    /// The whole resampled signal, `out_len(x.len())` samples.
    pub fn process_all(&self, x: &[S]) -> Vec<S> {
        self.process(x, 0, self.out_len(x.len()))
    }
}

/// The reference direct form, `y[n] = sum_k h[k] * u[n*M - k]` with `u` the zero-stuffed input,
/// computed literally (builds `u`). For tests and verification only: cost is `O(L * len * N)`.
pub fn direct_form<S: Sample>(x: &[S], h: &[S], up: usize, down: usize, count: usize) -> Vec<S> {
    let mut u = vec![S::default(); if x.is_empty() { 0 } else { (x.len() - 1) * up + 1 }];
    for (j, &v) in x.iter().enumerate() {
        if let Some(slot) = u.get_mut(j * up) {
            *slot = v;
        }
    }
    (0..count)
        .map(|n| {
            let m = n * down;
            let mut acc = S::default();
            for (k, &c) in h.iter().enumerate() {
                if let Some(&v) = m.checked_sub(k).and_then(|j| u.get(j)) {
                    acc = acc + c * v;
                }
            }
            acc
        })
        .collect()
}

fn bessel_i0(x: f64) -> f64 {
    let (mut sum, mut term, q) = (1.0, 1.0, x * x / 4.0);
    for k in 1..200 {
        term *= q / (k * k) as f64;
        sum += term;
        if term < sum * 1e-17 {
            break;
        }
    }
    sum
}

/// Kaiser-windowed sinc prototype of length `up * taps_per_phase` for resampling by `up / down`,
/// cut off at the lower of the two Nyquist frequencies, with every phase normalised to sum to 1
/// (so the whole filter sums to `up`, the gain of zero-stuffing, and DC passes unchanged).
pub fn kaiser_prototype(up: usize, down: usize, taps_per_phase: usize, beta: f64) -> Result<Vec<f64>, Error> {
    if up == 0 || down == 0 {
        return Err(Error::ZeroRatio);
    }
    let len = up.checked_mul(taps_per_phase).ok_or(Error::TooLarge)?;
    if len == 0 {
        return Err(Error::EmptyPrototype);
    }
    let centre = (len - 1) as f64 / 2.0;
    let cutoff = 1.0 / up.max(down) as f64; // fraction of the upsampled Nyquist
    let i0b = bessel_i0(beta);
    let mut h: Vec<f64> = (0..len)
        .map(|m| {
            let t = (m as f64 - centre) * cutoff;
            let sinc = if t.abs() < 1e-12 { 1.0 } else { (PI * t).sin() / (PI * t) };
            let r = (m as f64 - centre) / (centre + 1.0);
            sinc * bessel_i0(beta * (1.0 - r * r).max(0.0).sqrt()) / i0b
        })
        .collect();
    for p in 0..up {
        let sum: f64 = h.iter().skip(p).step_by(up).sum();
        if sum.abs() > 1e-300 {
            h.iter_mut().skip(p).step_by(up).for_each(|v| *v /= sum);
        }
    }
    Ok(h)
}
