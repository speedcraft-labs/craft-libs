//! Rank-preserving median primitives shared by app-specific spatial adapters.

use std::cmp::Ordering;

/// Spatial border behavior for a ranked square window.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MedianEdge {
    /// Repeat the nearest sample independently on each axis.
    Clamp,
    /// Omit samples outside the plane; border windows can contain an even number of samples.
    Truncate,
}

/// Invalid rank-plane input to [`median_ranked_square`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MedianError {
    InvalidBinCount,
    ShapeMismatch,
    RadiusOverflow,
    BinOutOfRange,
}

impl std::fmt::Display for MedianError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "median: {self:?}")
    }
}

impl std::error::Error for MedianError {}

/// Select `rank` using the caller's exact total order, returning the selected original value.
///
/// This is the shared tiny-window path used where direct selection is cheaper than building a
/// sliding histogram. `None` means the slice is empty or `rank` is out of range.
pub fn select_nth<T: Copy>(values: &mut [T], rank: usize, compare: impl FnMut(&T, &T) -> Ordering) -> Option<T> {
    if rank >= values.len() {
        return None;
    }
    let (_, selected, _) = values.select_nth_unstable_by(rank, compare);
    Some(*selected)
}

/// A sliding rank histogram with a retained median cursor.
///
/// `add` and `remove` accept ranks in `0..bins`. Invalid adds and removals of absent values are
/// ignored, so adapters can use this primitive without unwinding across worker boundaries. The
/// caller must preserve the window's sample count and bin range. Once initialized, updates take
/// constant time and `median` advances only as far as the changed ranks require.
#[derive(Clone, Debug)]
pub struct MedianHistogram {
    counts: Vec<usize>,
    total: usize,
    median: usize,
    below: usize,
    initialized: bool,
}

impl MedianHistogram {
    pub fn new(bins: usize) -> Self {
        Self { counts: vec![0; bins], total: 0, median: 0, below: 0, initialized: false }
    }

    pub fn bins(&self) -> usize {
        self.counts.len()
    }

    pub fn len(&self) -> usize {
        self.total
    }

    pub fn is_empty(&self) -> bool {
        self.total == 0
    }

    pub fn add(&mut self, rank: usize) {
        let Some(count) = self.counts.get_mut(rank) else {
            return;
        };
        *count = count.saturating_add(1);
        self.total = self.total.saturating_add(1);
        if self.initialized && rank < self.median {
            self.below = self.below.saturating_add(1);
        }
    }

    pub fn remove(&mut self, rank: usize) {
        let Some(count) = self.counts.get_mut(rank) else {
            return;
        };
        if *count == 0 || self.total == 0 {
            return;
        }
        *count -= 1;
        self.total -= 1;
        if self.initialized && rank < self.median {
            self.below -= 1;
        }
        if self.total == 0 {
            self.median = 0;
            self.below = 0;
            self.initialized = false;
        }
    }

    /// Return the upper middle rank (`len / 2`), or `None` for an empty histogram.
    pub fn median(&mut self) -> Option<usize> {
        if self.total == 0 || self.counts.is_empty() {
            return None;
        }
        if !self.initialized {
            self.median = 0;
            self.below = 0;
            self.initialized = true;
        }
        let target = self.total / 2;
        while self.below > target {
            self.median -= 1;
            self.below -= self.counts[self.median];
        }
        while self.below + self.counts[self.median] <= target {
            self.below += self.counts[self.median];
            self.median += 1;
        }
        Some(self.median)
    }
}

/// Median ranks for one packed `width × height` rank plane and a square footprint.
///
/// The selected rank is the upper middle (`sample_count / 2`), matching Rust's
/// `select_nth_unstable` convention. The input values must be rank IDs in `0..bins`;
/// app adapters map their original sample order to and from these IDs.
pub fn median_ranked_square(
    source: &[u32],
    width: usize,
    height: usize,
    radius: usize,
    bins: usize,
    edge: MedianEdge,
) -> Result<Vec<u32>, MedianError> {
    let pixels = width.checked_mul(height).ok_or(MedianError::ShapeMismatch)?;
    if pixels != source.len() {
        return Err(MedianError::ShapeMismatch);
    }
    if bins == 0 {
        return Err(MedianError::InvalidBinCount);
    }
    if source.iter().any(|&rank| rank as usize >= bins) {
        return Err(MedianError::BinOutOfRange);
    }
    if pixels == 0 {
        return Ok(Vec::new());
    }
    let radius = i64::try_from(radius).map_err(|_| MedianError::RadiusOverflow)? as i128;
    let w = width as i128;
    let plane = RankPlane { source, width, height, radius, edge };
    let mut out = vec![0; pixels];
    let mut hist = MedianHistogram::new(bins);

    for dy in -radius..=radius {
        for dx in -radius..=radius {
            if let Some(index) = plane.sample(dx, dy) {
                hist.add(source[index] as usize);
            }
        }
    }

    for y in 0..height {
        let y_i = y as i128;
        if y % 2 == 0 {
            for x in 0..width {
                let x_i = x as i128;
                let rank = hist.median().ok_or(MedianError::InvalidBinCount)?;
                out[y * width + x] = rank as u32;
                if x + 1 < width {
                    plane.adjust_column(&mut hist, x_i - radius, y_i, false);
                    plane.adjust_column(&mut hist, x_i + radius + 1, y_i, true);
                }
            }
        } else {
            for x in (0..width).rev() {
                let x_i = x as i128;
                let rank = hist.median().ok_or(MedianError::InvalidBinCount)?;
                out[y * width + x] = rank as u32;
                if x > 0 {
                    plane.adjust_column(&mut hist, x_i + radius, y_i, false);
                    plane.adjust_column(&mut hist, x_i - radius - 1, y_i, true);
                }
            }
        }
        if y + 1 < height {
            let x_i = if y % 2 == 0 { w - 1 } else { 0 };
            plane.adjust_row(&mut hist, x_i, y_i - radius, false);
            plane.adjust_row(&mut hist, x_i, y_i + radius + 1, true);
        }
    }
    Ok(out)
}

struct RankPlane<'a> {
    source: &'a [u32],
    width: usize,
    height: usize,
    radius: i128,
    edge: MedianEdge,
}

impl RankPlane<'_> {
    fn sample(&self, x: i128, y: i128) -> Option<usize> {
        sample_index(x, y, self.width as i128, self.height as i128, self.edge)
    }

    fn adjust_column(&self, hist: &mut MedianHistogram, x: i128, center_y: i128, add: bool) {
        for dy in -self.radius..=self.radius {
            if let Some(index) = self.sample(x, center_y + dy) {
                if add {
                    hist.add(self.source[index] as usize);
                } else {
                    hist.remove(self.source[index] as usize);
                }
            }
        }
    }

    fn adjust_row(&self, hist: &mut MedianHistogram, center_x: i128, y: i128, add: bool) {
        for dx in -self.radius..=self.radius {
            if let Some(index) = self.sample(center_x + dx, y) {
                if add {
                    hist.add(self.source[index] as usize);
                } else {
                    hist.remove(self.source[index] as usize);
                }
            }
        }
    }
}

fn sample_index(x: i128, y: i128, width: i128, height: i128, edge: MedianEdge) -> Option<usize> {
    match edge {
        MedianEdge::Clamp => {
            let x = x.clamp(0, width - 1) as usize;
            let y = y.clamp(0, height - 1) as usize;
            Some(y * width as usize + x)
        }
        MedianEdge::Truncate if x >= 0 && x < width && y >= 0 && y < height => Some(y as usize * width as usize + x as usize),
        MedianEdge::Truncate => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn brute(source: &[u32], width: usize, height: usize, radius: usize, edge: MedianEdge) -> Vec<u32> {
        let mut out = vec![0; source.len()];
        for y in 0..height {
            for x in 0..width {
                let mut values = Vec::new();
                for dy in -(radius as i64)..=radius as i64 {
                    for dx in -(radius as i64)..=radius as i64 {
                        if let Some(i) = sample_index(x as i128 + dx as i128, y as i128 + dy as i128, width as i128, height as i128, edge) {
                            values.push(source[i]);
                        }
                    }
                }
                let rank = values.len() / 2;
                out[y * width + x] = select_nth(&mut values, rank, u32::cmp).unwrap_or_default();
            }
        }
        out
    }

    #[test]
    fn sliding_square_matches_selection_for_both_edge_contracts_and_bit_depths() {
        for &(width, height) in &[(1, 1), (2, 5), (7, 4), (11, 9)] {
            for &(bits, bins) in &[(8, 256), (16, 65_536)] {
                let mut seed = 0x9e37_79b9u32;
                let source: Vec<u32> = (0..width * height)
                    .map(|i| {
                        seed ^= seed << 13;
                        seed ^= seed >> 17;
                        seed ^= seed << 5;
                        if i % 3 == 0 {
                            seed % 7
                        } else if bits == 8 {
                            seed & 255
                        } else {
                            seed & 65_535
                        }
                    })
                    .collect();
                for edge in [MedianEdge::Clamp, MedianEdge::Truncate] {
                    for radius in [0, 1, 2, 5] {
                        let expected = brute(&source, width, height, radius, edge);
                        let actual = median_ranked_square(&source, width, height, radius, bins, edge);
                        assert_eq!(actual.ok(), Some(expected), "{bits}-bit {width}x{height} r={radius} {edge:?}");
                    }
                }
            }
        }
    }

    #[test]
    fn histogram_cursor_tracks_insertions_and_removals() {
        let mut hist = MedianHistogram::new(65_536);
        let mut samples = Vec::new();
        let mut seed = 0xa341_316cu32;
        for i in 0..4_000 {
            seed = seed.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            let value = if i % 2 == 0 { seed & 255 } else { seed & 65_535 };
            samples.push(value);
            hist.add(value as usize);
            if i % 17 == 0 {
                let mut sorted = samples.clone();
                sorted.sort_unstable();
                assert_eq!(hist.median(), Some(sorted[sorted.len() / 2] as usize));
            }
        }
        for _ in 0..samples.len() {
            let value = samples.remove(0);
            hist.remove(value as usize);
            if !samples.is_empty() {
                let mut sorted = samples.clone();
                sorted.sort_unstable();
                assert_eq!(hist.median(), Some(sorted[sorted.len() / 2] as usize));
            }
        }
        assert_eq!(hist.median(), None);
    }
}
