# craft-resample

Rational-ratio polyphase FIR resampler (`L/M`), generic over `f32`/`f64`, plus image reduction
primitives for consumers that need matching coordinate and edge policies. The default feature set
has no runtime dependencies; enable `rayon` to parallelize the image reducers.

## Image reduction

* `resize_nearest` resizes packed pixels or masks with explicit `Corner` or `Center` alignment.
  It never invents values, which makes it suitable for categorical labels. Invalid sizes and
  allocation failures return `None`.
* `resize_bilinear_u8_coverage` resizes an 8-bit continuous coverage mask with center coordinates,
  clamped edges, and the legacy round-to-nearest rule. It may create intermediate coverage values.
* `reduce_box_f32` averages exact integer-ratio footprints of packed `f32` channels. It rejects
  fractional ratios and enlargements so callers can keep their established fallback filter.
* `downsample2_clamped_rgba` builds one level of a clamped 2×2 RGBA pyramid. Odd dimensions round
  up and repeat the final row or column, as in affine minification pyramids.

Property tests check constants, label preservation, and odd-sized pyramid levels. The `rayon`
feature keeps reductions row/pixel-parallel in image consumers.

The `image_bench` example pairs the legacy reducers with these kernels on a corpus PNG, checks
output equality, and writes craft-bench reports. Build it before entering the bench lock, then run
the binary through `scripts/bench-run` while holding `bench.lock`.

* `Polyphase::from_prototype(h, L, M)` splits any prototype FIR into `L` phases; the caller
  designs the filter (or uses `kaiser_prototype`, a Kaiser-windowed sinc normalised so every
  phase sums to 1: DC passes unchanged and the prototype sums to `L`).
* `process(x, first, count)` computes output samples `first .. first+count` with an exact integer
  position accumulator (no floating-point phase, no drift); `process_all` gives the full output.
* `process_from(x, start, count)` places output `n` at upsampled index `start + n*M`; a filter centred on
  the output (taps reaching `lead` input samples ahead) is `start = lead * L`. Same theorem, a start offset.
* `process_from_into` is `process_from` into a caller buffer (no allocation).
* `direct_form` is the literal upsample -> FIR -> downsample reference.

The polyphase form equals the direct form for every input: proved in Lean 4 (`lean/`, see
`lean/TRUST.md`), and checked against exact rational vectors in `tests/lean_vectors.rs`.
This is the shared kernel behind the polyphase paths in soundcraft (`dsp::offline::Polyphase`,
`playback` sinc resampler) and filmcraft (`audio-dsp::oversample`); migrating them is separate work.
