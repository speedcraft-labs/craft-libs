#![no_std]
use spirv_std::spirv;

/// Per-pixel kernel shared by the GPU entry point and the CPU execution path.
#[inline]
pub fn box_blur_pixel(prefix_lo: f32, prefix_hi: f32, endpoint: f32, width: u32) -> f32 {
    (prefix_hi + endpoint - prefix_lo) / width as f32
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Params {
    pub width: u32,
    pub height: u32,
    pub channels: u32,
    pub radius: u32,
}

/// Tiled exclusive prefix scan over a horizontal box window, including clamped halo values.
/// `size` is selected by the host: 512 for radius <= 128 and 1024 otherwise.
#[spirv(compute(threads(256)))]
pub fn box_h_scan(
    #[spirv(workgroup_id)] group_id: spirv_std::glam::UVec3,
    #[spirv(local_invocation_index)] lane: u32,
    #[spirv(uniform, descriptor_set = 0, binding = 0)] params: &Params,
    #[spirv(storage_buffer, descriptor_set = 0, binding = 1)] src: &[f32],
    #[spirv(storage_buffer, descriptor_set = 0, binding = 2)] dst: &mut [f32],
    #[spirv(workgroup)] scan: &mut [f32; 3072],
) {
    let w = params.width;
    let nc = params.channels;
    let r = params.radius;
    let size = if r <= 128 { 512u32 } else { 1024u32 };
    let start = (group_id.x * 256) as i32 - r as i32;
    let row = group_id.y * w;
    let last = w as i32 - 1;

    let mut item = lane;
    while item < size {
        let x = (start + item as i32).clamp(0, last) as u32;
        let pixel = (row + x) * nc;
        let mut channel = 0;
        while channel < 3 {
            scan[(item * 3 + channel) as usize] = if channel < nc { src[(pixel + channel) as usize] } else { 0.0 };
            channel += 1;
        }
        item += 256;
    }
    spirv_std::arch::workgroup_memory_barrier_with_group_sync();

    let mut stride = 1u32;
    while stride < size {
        let count = size / (2 * stride);
        let mut i = lane;
        while i < count {
            let right = (i + 1) * 2 * stride - 1;
            let left = right - stride;
            let mut channel = 0;
            while channel < 3 {
                let a = (right * 3 + channel) as usize;
                let b = (left * 3 + channel) as usize;
                scan[a] += scan[b];
                channel += 1;
            }
            i += 256;
        }
        spirv_std::arch::workgroup_memory_barrier_with_group_sync();
        stride *= 2;
    }
    if lane == 0 {
        let mut channel = 0;
        while channel < 3 {
            scan[((size - 1) * 3 + channel) as usize] = 0.0;
            channel += 1;
        }
    }
    spirv_std::arch::workgroup_memory_barrier_with_group_sync();

    stride = size / 2;
    loop {
        let count = size / (2 * stride);
        let mut i = lane;
        while i < count {
            let right = (i + 1) * 2 * stride - 1;
            let left = right - stride;
            let mut channel = 0;
            while channel < 3 {
                let a = (left * 3 + channel) as usize;
                let b = (right * 3 + channel) as usize;
                let value = scan[a];
                scan[a] = scan[b];
                scan[b] += value;
                channel += 1;
            }
            i += 256;
        }
        spirv_std::arch::workgroup_memory_barrier_with_group_sync();
        if stride == 1 {
            break;
        }
        stride /= 2;
    }

    let x = group_id.x * 256 + lane;
    if x < w {
        let lo = lane;
        let hi = lane + 2 * r;
        let endpoint_x = (start + hi as i32).clamp(0, last) as u32;
        let endpoint_pixel = (row + endpoint_x) * nc;
        let out_pixel = (row + x) * nc;
        let mut channel = 0;
        while channel < nc {
            let prefix_lo = scan[(lo * 3 + channel) as usize];
            let prefix_hi = scan[(hi * 3 + channel) as usize];
            let endpoint = src[(endpoint_pixel + channel) as usize];
            dst[(out_pixel + channel) as usize] = box_blur_pixel(prefix_lo, prefix_hi, endpoint, 2 * r + 1);
            channel += 1;
        }
    }
}
