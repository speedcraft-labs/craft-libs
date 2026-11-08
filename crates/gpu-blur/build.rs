fn main() {
    println!("cargo:rerun-if-changed=shader/src/lib.rs");
    println!("cargo:rerun-if-changed=shader/src/box_scan.wgsl");
    #[cfg(feature = "spirv")]
    {
        let shader_dir = format!("{}/shader", std::env::var("CARGO_MANIFEST_DIR").expect("manifest dir"));
        let mut builder = spirv_builder::SpirvBuilder::new(&shader_dir, "spirv-unknown-vulkan1.2");
        builder.build_script.defaults = true;
        builder.build_script.env_shader_spv_path = Some(true);
        builder.build_script.forward_rustc_warnings = Some(true);
        let result = builder.build().expect("compile box blur shader to SPIR-V");
        let bytes = std::fs::read(result.module.unwrap_single()).expect("read compiled SPIR-V");
        let module = naga::front::spv::parse_u8_slice(&bytes, &naga::front::spv::Options::default()).expect("parse rust-gpu SPIR-V with Naga");
        let info = naga::valid::Validator::new(naga::valid::ValidationFlags::all(), naga::valid::Capabilities::all())
            .validate(&module)
            .expect("validate rust-gpu SPIR-V");
        let wgsl = naga::back::wgsl::write_string(&module, &info, naga::back::wgsl::WriterFlags::empty()).expect("translate SPIR-V to WGSL");
        let round_trip = naga::front::wgsl::parse_str(&wgsl).expect("parse translated WGSL");
        naga::valid::Validator::new(naga::valid::ValidationFlags::all(), naga::valid::Capabilities::all())
            .validate(&round_trip)
            .expect("validate translated WGSL");
        let comparison = std::fs::read_to_string(format!("{shader_dir}/src/box_scan.wgsl")).expect("read WGSL reference");
        let wgsl_module = naga::front::wgsl::parse_str(&comparison).expect("parse WGSL reference");
        naga::valid::Validator::new(naga::valid::ValidationFlags::all(), naga::valid::Capabilities::all())
            .validate(&wgsl_module)
            .expect("validate WGSL reference");
        let wgsl_path = std::path::PathBuf::from(std::env::var_os("OUT_DIR").expect("output dir")).join("box_blur_spirv.wgsl");
        std::fs::write(&wgsl_path, wgsl).expect("write Naga-translated WGSL");
        println!("cargo:rustc-env=CRAFT_GPU_BLUR_WGSL={}", wgsl_path.display());
    }
}
