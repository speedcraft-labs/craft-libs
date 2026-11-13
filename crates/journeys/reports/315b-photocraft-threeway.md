# PhotoCraft 315b: brush latency validity and three-build comparison

## Validity

The upstream recorder's 8–10 ms point values measured cursor/UI frames before the brush pixels arrived. In both documents, the selected upstream 30 px and 500 px move frames changed zero pixels in the stroke region; the brush pixels appeared by release. The merge-base and fork-tip selected frames already matched the completed stroke. All three builds used equal dab counts and produced identical settled stroke-region RGB hashes. The canvas-width upstream frame contained only part of its stroke.

The corrected latency runs from the first accepted brush input through the release-frame GPU fence, with the release frame checked against settled pixels.

## Preliminary typical document, 12 MP

Ten paired, interleaved comparisons; values are warm stroke-total median/p95 in milliseconds. `A/B` is merge-base divided by fork-tip; `A/C` is merge-base divided by upstream tip, so values above 1 mean upstream completed faster.

| Brush action | A: merge-base | B: fork tip | C: upstream tip | A/B ratio (95% CI) | A/C ratio (95% CI) |
|---|---:|---:|---:|---:|---:|
| 30 px | 124.09 / 128.53 | 124.30 / 128.24 | 111.31 / 118.55 | 0.999 (0.989–1.019) | 1.119 (1.084–1.133) |
| 500 px soft | 223.62 / 231.34 | 219.37 / 235.21 | 197.65 / 210.56 | 1.017 (0.999–1.034) | 1.140 (1.105–1.161) |
| Canvas-width soft | 2114.24 / 2154.91 | 2107.08 / 2182.72 | 1748.95 / 1780.83 | 1.000 (0.989–1.006) | 1.204 (1.193–1.219) |

The previous typical A/A gate cannot validate these contrasts. Its 20 reports used fork-tip binary SHA `11d56a76…` and driver SHA `98f1feeb…`; the typical three-build reports used B binary SHA `59284ea9…` and driver SHA `ff8429f2…`. Treat these rows and ratios as descriptive only. Current rebuilt pins are A `9e127556…`, B `19aab350…`, C `fe08d44f…`; the exact-pin typical A/A gate and three-build matrix must be rerun before drawing a gated conclusion.

## Pixel evidence at the selected move frame

Counts are changed pixels versus the pre-stroke region / pixels differing from the settled stroke. The settled RGB hashes match across A, B, and C for each action and document.

| Document | Action | Dabs | A and B | C |
|---|---|---:|---:|---:|
| Typical 12 MP | 30 px | 763 | 5,207 / 0 | 0 / 5,207 |
| Typical 12 MP | 500 px soft | 46 | 79,895 / 0 | 0 / 79,895 |
| Typical 12 MP | Canvas-width soft | 6 | 79,992 / 0 | 78,573 / 72,868 |
| Heavy 24 MP | 30 px | 1,220 | 3,489 / 0 | 0 / 3,489 |
| Heavy 24 MP | 500 px soft | 74 | 50,681 / 0 | 0 / 50,681 |
| Heavy 24 MP | Canvas-width soft | 8 | 98,803 / 0 | 97,022 / 95,936 |

## Heavy document and cause

The earlier 17/20 heavy A/A count mixed two executable hashes after the target directory was rebuilt, so those 14 old-hash pairs are retained but excluded. The current hash-matched gate has 4/20 pairs (0, 14, 15, 16); 16 remain. Heavy three-build runs and the cause checkpoint are pending. Upstream #10013 moves live painting to a worker while the cursor advances, consistent with the cursor frame preceding brush pixels. A pre-#10013 control is built to isolate that scheduling change from earlier paint-path changes. That historical checkpoint needed only a compile-only duplicate-TIFF-constant removal on `wip/315b-photocraft-pre10013` (`ffc413ca8`); no brush code changed.

## Reproduction pins

- A merge-base: `316e00a97eab730e60584df578c295b5c2539d95`, recorder `wip/315b-photocraft-threeway` at `a521eca822887a0810d0061f5887cb5ae5fafedb`.
- B fork tip: `f07b6b895331287cde377dbffe61abfbdc2a6d5d`, recorder `wip/315b-photocraft-tip` at `a3400633146644766afd996a0502f8702078ff10`.
- C upstream tip: `eee667f1d92e34db6c438ddd20f3e4f5339cf8a7`, recorder hooks committed on `wip/315b-photocraft-upstream-recorder` at `604a2c766827f1354667e6774dd6933be91d1f0c`.
- Current build SHA-256 values: A `9e127556cf8826f3e944ec72c4cb7fdb9196ddb332a766fc1ce2781ff676c52a`; B `19aab350144684e655c529f4472917f788694895b7349d9a648d29c13bec28f1`; C `fe08d44fa693968b6deba4448d06a8aa743a006739a20a69cad842d59aedef6b`.
- Recorder script SHA-256: `ff8429f223ff214f2217986bd5ff9c94872f60dccd8cd4ca228800e55358f47c`.
