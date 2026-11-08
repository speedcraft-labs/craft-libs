#![no_std]
use spirv_std::{
    glam::{UVec3, Vec4},
    spirv,
};

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
    #[spirv(workgroup_id)] group_id: UVec3,
    #[spirv(local_invocation_index)] lane: u32,
    #[spirv(uniform, descriptor_set = 0, binding = 0)] params: &Params,
    #[spirv(storage_buffer, descriptor_set = 0, binding = 1)] src: &[f32],
    #[spirv(storage_buffer, descriptor_set = 0, binding = 2)] dst: &mut [f32],
    #[spirv(workgroup)] scan: &mut [Vec4; 1024],
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
        let mut value = Vec4::ZERO;
        let mut channel = 0;
        while channel < nc {
            let sample = src[(pixel + channel) as usize];
            if channel == 0 {
                value.x = sample;
            }
            if channel == 1 {
                value.y = sample;
            }
            if channel == 2 {
                value.z = sample;
            }
            channel += 1;
        }
        scan[item as usize] = value;
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
            scan[right as usize] = scan[right as usize] + scan[left as usize];
            i += 256;
        }
        spirv_std::arch::workgroup_memory_barrier_with_group_sync();
        stride *= 2;
    }
    if lane == 0 {
        scan[(size - 1) as usize] = Vec4::ZERO;
    }
    spirv_std::arch::workgroup_memory_barrier_with_group_sync();

    stride = size / 2;
    loop {
        let count = size / (2 * stride);
        let mut i = lane;
        while i < count {
            let right = (i + 1) * 2 * stride - 1;
            let left = right - stride;
            let value = scan[left as usize];
            scan[left as usize] = scan[right as usize];
            scan[right as usize] = scan[right as usize] + value;
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
        let prefix_lo = scan[lo as usize];
        let prefix_hi = scan[hi as usize];
        let mut endpoint = Vec4::ZERO;
        let mut channel = 0;
        while channel < nc {
            let sample = src[(endpoint_pixel + channel) as usize];
            if channel == 0 {
                endpoint.x = sample;
            }
            if channel == 1 {
                endpoint.y = sample;
            }
            if channel == 2 {
                endpoint.z = sample;
            }
            channel += 1;
        }
        let window = 2 * r + 1;
        dst[out_pixel as usize] = box_blur_pixel(prefix_lo.x, prefix_hi.x, endpoint.x, window);
        if nc > 1 {
            dst[(out_pixel + 1) as usize] = box_blur_pixel(prefix_lo.y, prefix_hi.y, endpoint.y, window);
        }
        if nc > 2 {
            dst[(out_pixel + 2) as usize] = box_blur_pixel(prefix_lo.z, prefix_hi.z, endpoint.z, window);
        }
    }
}
