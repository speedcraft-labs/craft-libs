//! rust-gpu box-blur pilot. The pure arithmetic helper is shared with the shader crate.

pub use craft_gpu_blur_shader::{Vec4, box_blur_pixel};

/// CPU oracle for the tiled prefix-scan box kernel, with clamp edge handling.
pub fn box_blur_cpu(src: &[f32], width: usize, height: usize, channels: usize, radius: usize) -> Vec<f32> {
    assert!((1..=3).contains(&channels));
    assert_eq!(src.len(), width * height * channels);
    assert!(radius <= 255, "the tiled kernel supports radii up to 255");
    let window = (2 * radius + 1) as u32;
    let tile_size = if radius <= 128 { 512 } else { 1024 };
    let mut dst = vec![0.0; src.len()];
    for y in 0..height {
        let row = y * width * channels;
        for group in 0..width.div_ceil(256) {
            let start = (group * 256) as isize - radius as isize;
            let mut scan = vec![Vec4::ZERO; tile_size];
            let mut sums = [0.0f32; 3];
            for item in 0..tile_size {
                let x = (start + item as isize).clamp(0, width as isize - 1) as usize;
                scan[item] = Vec4::new(sums[0], sums[1], sums[2], 0.0);
                for channel in 0..channels {
                    sums[channel] += src[row + x * channels + channel];
                }
            }
            for lane in 0..256 {
                let x = group * 256 + lane;
                if x >= width {
                    continue;
                }
                let lo = scan[lane];
                let hi = scan[lane + 2 * radius];
                let endpoint_x = (start + lane as isize + 2 * radius as isize).clamp(0, width as isize - 1) as usize;
                let endpoint_at = row + endpoint_x * channels;
                let mut endpoint = Vec4::ZERO;
                if channels > 0 {
                    endpoint.x = src[endpoint_at];
                }
                if channels > 1 {
                    endpoint.y = src[endpoint_at + 1];
                }
                if channels > 2 {
                    endpoint.z = src[endpoint_at + 2];
                }
                let output = box_blur_pixel(lo, hi, endpoint, window);
                let out_at = row + x * channels;
                dst[out_at] = output.x;
                if channels > 1 {
                    dst[out_at + 1] = output.y;
                }
                if channels > 2 {
                    dst[out_at + 2] = output.z;
                }
            }
        }
    }
    dst
}

#[cfg(feature = "spirv")]
pub const BOX_H_SCAN_SPIRV: &[u8] = include_bytes!(env!("craft_gpu_blur_shader.spv"));
#[cfg(feature = "spirv")]
pub const RUSTGPU_WGSL: &str = include_str!(env!("CRAFT_GPU_BLUR_WGSL"));
#[cfg(feature = "spirv")]
pub const WGSL_SCAN: &str = include_str!("../shader/src/box_scan.wgsl");

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cpu_oracle_clamps_and_averages() {
        let input = [1.0, 2.0, 3.0, 4.0];
        assert_eq!(box_blur_cpu(&input, 4, 1, 1, 1), vec![4.0 / 3.0, 2.0, 3.0, 11.0 / 3.0]);
    }
}
