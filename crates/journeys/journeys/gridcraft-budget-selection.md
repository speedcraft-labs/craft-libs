# GridCraft budget workbook selection

The AIES workbook used for the initial #291 GridCraft run has no formulas, so it cannot judge formula-path tickets. For a formula-bearing, ordinary financial workbook, I compared the nine public finance-model XLSX downloads on NREL's SAM Financial Models page by compressed file size. The median is 272,699 bytes (`all-equity-flip.xlsx`). The selected workbook is JovialIO's public **Monthly Budget Tracker.xlsx**, 346,412 bytes (1.27× that median).

The tracker is a published monthly cash-flow budget template, not a regression fixture. Its 8 sheets contain 25,524 formulas, including 9,290 `SUMIFS` formula cells (9,582 calls) and 938 `COUNTIFS` cells; it also has 10 formula-based conditional-format ranges and 27 charts. Its shipped example transactions are fictional, as the workbook's README discloses. The template is MIT-licensed.

Pinned source: [JovialIO personal-finance-tracker-excel](https://github.com/jovialio/personal-finance-tracker-excel/tree/f5f1973956f15ab17906b4a51d52776185d5e4ec). The corpus manifest records the source commit, SHA-256, license, and feature tags. The corpus copy is `gridcraft-budget-tracker-2026/monthly-budget-tracker.xlsx`.

Journeys open the Dashboard, change the populated input `Entries!E779` to `99.99` and render the formula-based conditional formats on `Monthly Summary`, jump to `Entries!A779` to measure scrolling, or save a copy as XLSX. Open and save render the Dashboard charts. Each journey renders a 1440×900 UI snapshot and checks its output hash.

The size reference is intentionally narrow: the nine public NREL SAM financial-model downloads, not the raw 993-file compatibility corpus, whose many tiny regression fixtures would make a poor user-workbook median.
