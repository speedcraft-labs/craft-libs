# craft-gpu-blur rust-gpu pilot

This crate isolates the lightcraft horizontal box-blur pilot. The shader crate emits a 256-lane
Blelloch exclusive scan over a clamped halo; it uses 512 shared values through radius 128 and
1024 through radius 255. `box_blur_pixel` is the per-pixel kernel shared by the GPU entry point
and the CPU oracle. The CPU oracle emulates the same clamped tiled scan serially; corpus inputs
are also checked against a direct f64 sum.

Build the CPU oracle on stable with `cargo test -p craft-gpu-blur`. Build the SPIR-V module with
`cargo +nightly-2026-08-15 test -p craft-gpu-blur --features spirv`. rust-gpu's backend check
requires that nightly plus `rust-src`, `rustc-dev`, and `llvm-tools`. The host remains on stable;
only shader compilation selects the pinned nightly. The optional feature keeps the backend out of
normal builds. The first clean build also compiles bundled SPIR-V Tools and the Rust-GPU codegen
backend; CI isolates this as one nightly-only job.

The backend's setup diagnostics were actionable: a wrong nightly reports the required toolchain
revision/date and components, while a `spirv-std`/codegen version mismatch says the versions must
match. Rust source errors retain file and line locations. Naga parse and validation failures are
labelled by compilation phase, though the build script currently reports them through `expect`.

The native runner loads the SPIR-V bytes through wgpu's Naga SPIR-V input path. The build script
also translates the module to WGSL for browser WebGPU, which only accepts WGSL source. The matching
WGSL path remains in lightcraft's `crates/gpu/src/wgsl/blur.wgsl`. GPU comparisons
use a maximum absolute error bound of `1e-5 * (1 + radius / 10)` against its f32 CPU running-sum
reference, and also check a direct f64 sum. This is a numerical bound, not bitwise parity.
