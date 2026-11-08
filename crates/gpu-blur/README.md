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

## Pilot results

On the RTX 2080 Ti, the publishable 10-run paired report compares this WGSL tiled scan (old) with
the Rust-GPU shader (new). The geometric-mean new/old ratio is `0.971` with a 95% bootstrap
interval of `[0.855, 1.154]`; the 24 MP case is `0.903 [0.653, 1.248]`. The point estimates favor
Rust-GPU, but every confidence interval includes `1.0`, so this run does not establish a speed
advantage. Corpus and 24 MP correctness checks had exact WGSL/Rust-GPU pair equality; the maximum
GPU/CPU error was `3.576e-6`, below the radius-128 bound `1.38e-4`. See
[`reports/rustgpu-box-blur-rtx2080ti.md`](../../reports/rustgpu-box-blur-rtx2080ti.md) for the
full report.

The pilot does not support adopting Rust-GPU for new shaders. The Linux Vulkan path is correct and
its benchmark is statistically tied with WGSL, but the Mac M6/Metal run fails correctness both
when wgpu consumes the SPIR-V directly and when Naga converts it to WGSL. The generated WGSL's
maximum error was `8257.728` against the `1.38e-4` bound; Lightcraft's static WGSL passes on Metal.
The wasm32 build succeeds and validates the SPIR-V-to-WGSL translation, but a browser runtime test
was not run.

The shader requires `nightly-2026-08-15` with `rust-src`, `rustc-dev`, and `llvm-tools`. Build times
observed: `47.91 s` for the Linux release runner after dependency compilation, `15m 29s` for the
clean wasm32 toolchain build (including the native SPIR-V Tools build), and `79.77 s` for the
pinned Mac shader build. The Mac incremental SPIR-V runner build took `17.60 s`. The CI workflow
change is 14 added lines for a nightly-only shader/test/wasm job. A wrong nightly reports the
required revision and components; a backend/`spirv-std` version mismatch says those versions must
match. Rust source diagnostics include file and line; Naga failures are phase-labelled, though the
build script still reports them through `expect`.
