struct Params {
    width: u32,
    height: u32,
    channels: u32,
    radius: u32,
}

@group(0) @binding(0) var<uniform> params: Params;
@group(0) @binding(1) var<storage, read> src: array<f32>;
@group(0) @binding(2) var<storage, read_write> dst: array<f32>;
var<workgroup> scan: array<vec3<f32>, 1024>;

fn ld(pixel: u32) -> vec3<f32> {
    let at = pixel * params.channels;
    if (params.channels == 1u) { return vec3<f32>(src[at], 0.0, 0.0); }
    if (params.channels == 2u) { return vec3<f32>(src[at], src[at + 1u], 0.0); }
    return vec3<f32>(src[at], src[at + 1u], src[at + 2u]);
}

@compute @workgroup_size(256)
fn box_h_scan(
    @builtin(workgroup_id) group: vec3<u32>,
    @builtin(local_invocation_index) lane: u32,
) {
    let w = params.width;
    let nc = params.channels;
    let r = params.radius;
    let size = select(1024u, 512u, r <= 128u);
    let start = i32(group.x * 256u) - i32(r);
    let row = group.y * w;

    for (var i = lane; i < size; i += 256u) {
        scan[i] = ld(row + u32(clamp(start + i32(i), 0, i32(w) - 1)));
    }
    workgroupBarrier();

    var stride = 1u;
    loop {
        if (stride >= size) { break; }
        for (var i = lane; i < size / (2u * stride); i += 256u) {
            let right = (i + 1u) * 2u * stride - 1u;
            scan[right] += scan[right - stride];
        }
        workgroupBarrier();
        stride *= 2u;
    }
    if (lane == 0u) { scan[size - 1u] = vec3<f32>(0.0); }
    workgroupBarrier();

    loop {
        stride /= 2u;
        for (var i = lane; i < size / (2u * stride); i += 256u) {
            let right = (i + 1u) * 2u * stride - 1u;
            let left = right - stride;
            let value = scan[left];
            scan[left] = scan[right];
            scan[right] += value;
        }
        workgroupBarrier();
        if (stride == 1u) { break; }
    }

    let x = group.x * 256u + lane;
    if (x < w) {
        let right = lane + 2u * r;
        let endpoint = ld(row + u32(clamp(start + i32(right), 0, i32(w) - 1)));
        let lo = scan[lane];
        let hi = scan[right];
        let out_at = (row + x) * nc;
        if (nc > 0u) { dst[out_at] = (hi.x + endpoint.x - lo.x) / f32(2u * r + 1u); }
        if (nc > 1u) { dst[out_at + 1u] = (hi.y + endpoint.y - lo.y) / f32(2u * r + 1u); }
        if (nc > 2u) { dst[out_at + 2u] = (hi.z + endpoint.z - lo.z) / f32(2u * r + 1u); }
    }
}
