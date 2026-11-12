# Failed approach: apply the base patch to the already-instrumented fork

An early harness `prepare` invocation selected the fork recorder commit `a718ead5733ec85fca4951bdd2c52e79ce0225de` as the base and asked `app_base_patch` to apply the same recorder a second time. The reverse/check stage correctly rejected that setup before compilation. It did not produce a measured binary or dataset.

The working preparation uses fork tip directly and applies the common `photocraft-session-latency.patch` only to upstream `eee667f1d92e34db6c438ddd20f3e4f5339cf8a7`, exactly through the journey catalog’s `app_base_patch`.

This branch preserves the rejected preparation diagnosis only; no app source change is included.
