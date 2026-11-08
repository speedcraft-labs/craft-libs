use bytemuck::{Pod, Zeroable};
use craft_bench::{Config, Paired, report::Revs};
use craft_gpu_blur::{RUSTGPU_WGSL, WGSL_SCAN, box_blur_cpu};
use std::{io::BufReader, path::PathBuf, time::Instant};
use wgpu::util::DeviceExt;

const BOUND_FACTOR: f32 = 1.0e-5;

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable)]
struct Params {
    width: u32,
    height: u32,
    channels: u32,
    radius: u32,
}
struct Side {
    pipeline: wgpu::ComputePipeline,
    bind_group: wgpu::BindGroup,
    output: wgpu::Buffer,
    staging: wgpu::Buffer,
}
struct Case {
    name: String,
    width: usize,
    height: usize,
    channels: usize,
    radius: usize,
    source: Vec<f32>,
    oracle: Vec<f32>,
    wgsl: Side,
    rustgpu: Side,
    validated: bool,
}
struct Sample {
    gpu_ns: u64,
    validated: bool,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor::new_without_display_handle());
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default()))?;
    let info = adapter.get_info();
    let desc = wgpu::DeviceDescriptor { required_limits: adapter.limits(), ..Default::default() };
    let (device, queue) = pollster::block_on(adapter.request_device(&desc))?;

    let wgsl_module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
        label: Some("WGSL tiled box scan"),
        source: wgpu::ShaderSource::Wgsl(WGSL_SCAN.into()),
    });
    let rustgpu_module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
        label: Some("rust-gpu SPIR-V translated by Naga"),
        source: wgpu::ShaderSource::Wgsl(RUSTGPU_WGSL.into()),
    });
    let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
        label: Some("box blur layout"),
        entries: &[
            wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::COMPUTE,
                ty: wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Uniform, has_dynamic_offset: false, min_binding_size: None },
                count: None,
            },
            storage_layout(1, true),
            storage_layout(2, false),
        ],
    });
    let pl = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
        label: Some("box blur"),
        bind_group_layouts: &[Some(&layout)],
        immediate_size: 0,
    });
    let pipeline = |module: &wgpu::ShaderModule, label| {
        device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some(label),
            layout: Some(&pl),
            module,
            entry_point: Some("box_h_scan"),
            compilation_options: Default::default(),
            cache: None,
        })
    };
    let wgsl_pipeline = pipeline(&wgsl_module, "WGSL box scan");
    let rustgpu_pipeline = pipeline(&rustgpu_module, "rust-gpu box scan");

    let mut inputs = Vec::new();
    let root = corpus_root();
    for rel in ["pngsuite/basn6a08.png", "pngsuite/basn2c16.png", "pngsuite/basn0g08.png", "pngsuite/basn4a08.png"] {
        let path = root.join(rel);
        if path.is_file() {
            let (width, height, input) = read_png(&path)?;
            inputs.push((rel.to_string(), width, height, 3usize, input, 128usize));
        }
    }
    if std::env::var_os("RUSTGPU_VALIDATE_ONLY").is_none() || std::env::var_os("RUSTGPU_VALIDATE_24MP").is_some() {
        let (width, height) = (6000usize, 4000usize);
        let synthetic = (0..width * height * 3)
            .map(|i| {
                let x = (i as u32).wrapping_mul(747_796_405).wrapping_add(2_891_336_453);
                (x >> 8) as f32 / 16_777_215.0
            })
            .collect();
        inputs.push(("synthetic-24mp-r128".to_string(), width, height, 3, synthetic, 128));
    }

    let mut cases = Vec::new();
    for (name, width, height, channels, input, radius) in inputs {
        let params = Params { width: width as u32, height: height as u32, channels: channels as u32, radius: radius as u32 };
        let oracle = box_blur_cpu(&input, width, height, channels, radius);
        let wgsl = create_side(&device, &layout, &wgsl_pipeline, &params, &input);
        let rustgpu = create_side(&device, &layout, &rustgpu_pipeline, &params, &input);
        cases.push(Case { name, width, height, channels, radius, source: input, oracle, wgsl, rustgpu, validated: false });
    }

    for c in &mut cases {
        let a = readback(&device, &queue, &c.wgsl, c.width, c.height, c.channels);
        let b = readback(&device, &queue, &c.rustgpu, c.width, c.height, c.channels);
        let bound = BOUND_FACTOR * (1.0 + c.radius as f32 / 10.0);
        let (ea, eb, ep) = (max_error(&a, &c.oracle), max_error(&b, &c.oracle), max_error(&a, &b));
        assert!(ea <= bound && eb <= bound && ep <= bound, "{}: WGSL {ea}, rust-gpu {eb}, pair {ep}, bound {bound}", c.name);
        if !c.name.starts_with("synthetic-") {
            let exact = box_blur_f64(&c.source, c.width, c.height, c.channels, c.radius);
            let exact_error = max_error(&b, &exact);
            assert!(exact_error <= bound, "{} rust-gpu/f64 max error {exact_error} > {bound}", c.name);
        }
        c.validated = true;
        eprintln!("{} {}x{} r={}: WGSL/CPU {ea:.3e}, rust-gpu/CPU {eb:.3e}, pair {ep:.3e}, bound {bound:.3e}", c.name, c.width, c.height, c.radius);
    }

    if std::env::var_os("RUSTGPU_VALIDATE_ONLY").is_some() {
        eprintln!("validation-only run completed on {} ({:?})", info.name, info.backend);
        return Ok(());
    }
    let report = Paired::new(format!("lightcraft box blur r=128 on {info:?}"))
        .old(|c: &Case| Sample { gpu_ns: dispatch(&device, &queue, &c.wgsl, c.width, c.height) as u64, validated: c.validated })
        .new(|c: &Case| Sample { gpu_ns: dispatch(&device, &queue, &c.rustgpu, c.width, c.height) as u64, validated: c.validated })
        .inputs(cases.into_iter().map(|c| (c.name.clone(), c)))
        .check(|a, b| a.validated && b.validated && a.gpu_ns > 0 && b.gpu_ns > 0)
        .wall_meter(|sample| sample.gpu_ns)
        .run(&Config {
            revs: Revs {
                old: Some(std::env::var("LIGHTCRAFT_WGSL_REV").unwrap_or_else(|_| "lightcraft-working-tree".into())),
                new: Some(std::env::var("CRAFT_GPU_BLUR_REV").unwrap_or_else(|_| "craft-libs-working-tree".into())),
            },
            ..Config::default()
        })?;
    std::fs::create_dir_all("reports")?;
    let path = PathBuf::from("reports/rustgpu-box-blur-rtx2080ti.json");
    std::fs::write(&path, report.to_json())?;
    let markdown_path = PathBuf::from("reports/rustgpu-box-blur-rtx2080ti.md");
    std::fs::write(&markdown_path, report.to_markdown())?;
    println!("{}", report.to_markdown());
    println!("raw report: {}", path.display());
    report.require_publishable()?;
    Ok(())
}

fn storage_layout(binding: u32, read_only: bool) -> wgpu::BindGroupLayoutEntry {
    wgpu::BindGroupLayoutEntry {
        binding,
        visibility: wgpu::ShaderStages::COMPUTE,
        ty: wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Storage { read_only }, has_dynamic_offset: false, min_binding_size: None },
        count: None,
    }
}
fn create_side(d: &wgpu::Device, layout: &wgpu::BindGroupLayout, pipeline: &wgpu::ComputePipeline, p: &Params, input: &[f32]) -> Side {
    let params = d.create_buffer_init(&wgpu::util::BufferInitDescriptor {
        label: Some("params"),
        contents: bytemuck::bytes_of(p),
        usage: wgpu::BufferUsages::UNIFORM,
    });
    let src = d.create_buffer_init(&wgpu::util::BufferInitDescriptor {
        label: Some("input"),
        contents: bytemuck::cast_slice(input),
        usage: wgpu::BufferUsages::STORAGE,
    });
    let size = (input.len() * 4) as u64;
    let output = d.create_buffer(&wgpu::BufferDescriptor {
        label: Some("output"),
        size,
        usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC,
        mapped_at_creation: false,
    });
    let staging = d.create_buffer(&wgpu::BufferDescriptor {
        label: Some("staging"),
        size,
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });
    let bind_group = d.create_bind_group(&wgpu::BindGroupDescriptor {
        label: Some("blur buffers"),
        layout,
        entries: &[
            wgpu::BindGroupEntry { binding: 0, resource: params.as_entire_binding() },
            wgpu::BindGroupEntry { binding: 1, resource: src.as_entire_binding() },
            wgpu::BindGroupEntry { binding: 2, resource: output.as_entire_binding() },
        ],
    });
    let _ = (params, src);
    Side { pipeline: pipeline.clone(), bind_group, output, staging }
}
fn dispatch(d: &wgpu::Device, q: &wgpu::Queue, side: &Side, w: usize, h: usize) -> u128 {
    let start = Instant::now();
    let mut enc = d.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: Some("blur dispatch") });
    {
        let mut pass = enc.begin_compute_pass(&wgpu::ComputePassDescriptor { label: Some("blur"), timestamp_writes: None });
        pass.set_pipeline(&side.pipeline);
        pass.set_bind_group(0, &side.bind_group, &[]);
        pass.dispatch_workgroups(w.div_ceil(256) as u32, h as u32, 1);
    }
    q.submit([enc.finish()]);
    let _ = d.poll(wgpu::PollType::wait_indefinitely());
    start.elapsed().as_nanos()
}
fn readback(d: &wgpu::Device, q: &wgpu::Queue, side: &Side, w: usize, h: usize, nc: usize) -> Vec<f32> {
    dispatch(d, q, side, w, h);
    let mut enc = d.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: Some("blur copy") });
    enc.copy_buffer_to_buffer(&side.output, 0, &side.staging, 0, (w * h * nc * 4) as u64);
    q.submit([enc.finish()]);
    let slice = side.staging.slice(..);
    let (tx, rx) = std::sync::mpsc::channel();
    slice.map_async(wgpu::MapMode::Read, move |result| {
        let _ = tx.send(result);
    });
    let _ = d.poll(wgpu::PollType::wait_indefinitely());
    rx.recv().expect("map callback").expect("map readback");
    let result = bytemuck::cast_slice::<u8, f32>(&slice.get_mapped_range().expect("mapped view")).to_vec();
    side.staging.unmap();
    result
}
fn box_blur_f64(src: &[f32], width: usize, height: usize, channels: usize, radius: usize) -> Vec<f32> {
    let mut out = vec![0.0; src.len()];
    for y in 0..height {
        for x in 0..width {
            for c in 0..channels {
                let sum = (0..=2 * radius)
                    .map(|tap| {
                        let sx = (x as isize + tap as isize - radius as isize).clamp(0, width as isize - 1) as usize;
                        f64::from(src[(y * width + sx) * channels + c])
                    })
                    .sum::<f64>();
                out[(y * width + x) * channels + c] = (sum / (2 * radius + 1) as f64) as f32;
            }
        }
    }
    out
}
fn max_error(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b).map(|(x, y)| (x - y).abs()).fold(0.0, f32::max)
}
fn corpus_root() -> PathBuf {
    std::env::var_os("ARTCRAFT_CORPUS").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("../../corpus"))
}
fn read_png(path: &std::path::Path) -> Result<(usize, usize, Vec<f32>), Box<dyn std::error::Error>> {
    let mut decoder = png::Decoder::new(BufReader::new(std::fs::File::open(path)?));
    decoder.set_transformations(png::Transformations::EXPAND | png::Transformations::STRIP_16);
    let mut reader = decoder.read_info()?;
    let mut bytes = vec![0; reader.output_buffer_size().expect("PNG frame size")];
    let info = reader.next_frame(&mut bytes)?;
    bytes.truncate(info.buffer_size());
    let (channels, colors) = match info.color_type {
        png::ColorType::Grayscale => (1, 1),
        png::ColorType::GrayscaleAlpha => (2, 1),
        png::ColorType::Rgb => (3, 3),
        png::ColorType::Rgba => (4, 3),
        png::ColorType::Indexed => return Err("indexed PNG was not expanded".into()),
    };
    let mut rgb = Vec::with_capacity(info.width as usize * info.height as usize * 3);
    for px in bytes.chunks_exact(channels) {
        if colors == 1 {
            let value = f32::from(px[0]) / 255.0;
            rgb.extend([value; 3]);
        } else {
            rgb.extend(px[..3].iter().map(|&c| f32::from(c) / 255.0));
        }
    }
    Ok((info.width as usize, info.height as usize, rgb))
}
