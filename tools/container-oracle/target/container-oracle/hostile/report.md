| scenario | app | files | Identical | WithinTolerance | ExpectedDifference | Regression | BothFail | OnlyOldFails | OnlyNewFails | Timeout | Panic |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pdfcraft-write.hostile | pdfcraft | 986 | 1 | 0 | 778 | 0 | 207 | 0 | 0 | 0 | 0 |
| effectcraft-write.hostile | effectcraft | 986 | 1 | 0 | 778 | 0 | 207 | 0 | 0 | 0 | 0 |
| vectorcraft-write-store.hostile | vectorcraft | 986 | 1 | 1 | 777 | 0 | 207 | 0 | 0 | 0 | 0 |
| vectorcraft-write-deflate.hostile | vectorcraft | 986 | 1 | 1 | 777 | 0 | 207 | 0 | 0 | 0 | 0 |
| vectorcraft-read.hostile | vectorcraft | 986 | 681 | 134 | 171 | 0 | 0 | 0 | 0 | 0 | 0 |
| effectcraft-read.hostile | effectcraft | 986 | 53 | 0 | 933 | 0 | 0 | 0 | 0 | 0 | 0 |
| vectorcraft-read-legacy-store.hostile | vectorcraft | 986 | 735 | 0 | 43 | 0 | 208 | 0 | 0 | 0 | 0 |
| vectorcraft-read-legacy-deflate.hostile | vectorcraft | 986 | 735 | 0 | 43 | 0 | 208 | 0 | 0 | 0 | 0 |
| effectcraft-read-legacy-store.hostile | effectcraft | 986 | 734 | 0 | 45 | 0 | 207 | 0 | 0 | 0 | 0 |
| craftdoc-raw.hostile | craft-doc | 986 | 984 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| craftdoc-pcraft.hostile | craft-doc | 2792 | 748 | 1859 | 183 | 0 | 0 | 0 | 0 | 2 | 0 |
| gridcraft-sniff.hostile | gridcraft | 11594 | 11588 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| gridcraft-is-xls.hostile | gridcraft | 11594 | 10036 | 0 | 1558 | 0 | 0 | 0 | 0 | 0 | 0 |
| gridcraft-streams.hostile | gridcraft | 11594 | 5212 | 4019 | 2363 | 0 | 0 | 0 | 0 | 0 | 0 |
| deckcraft-sniff.hostile | deckcraft | 11594 | 11588 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| wordcraft-sniff.hostile | wordcraft | 11594 | 8875 | 0 | 2719 | 0 | 0 | 0 | 0 | 0 | 0 |
| wordcraft-streams.hostile | wordcraft | 11594 | 4816 | 2787 | 3991 | 0 | 0 | 0 | 0 | 0 | 0 |
| filmcraft-tree.hostile | filmcraft | 11594 | 0 | 642 | 10952 | 0 | 0 | 0 | 0 | 0 | 0 |
| reference-vs-craft-cfb.hostile | reference | 11594 | 4821 | 2782 | 3991 | 0 | 0 | 0 | 0 | 0 | 0 |

| scenario | expected-difference id | files |
|---|---|---:|
| craftdoc-pcraft.hostile | craftdoc-pcraft.hostile:info-err-variant-outline-err-variant-renditions-err-variant-sniff-err-variant | 23 |
| craftdoc-pcraft.hostile | craftdoc-pcraft.hostile:info-old-err-new-ok-outline-old-err-new-ok | 32 |
| craftdoc-pcraft.hostile | craftdoc-pcraft.hostile:info-old-err-new-ok-outline-old-err-new-ok-renditions-err-variant-sniff-err-variant | 48 |
| craftdoc-pcraft.hostile | craftdoc-pcraft.hostile:info-old-err-new-ok-outline-old-err-new-ok-renditions-old-err-new-ok | 29 |
| craftdoc-pcraft.hostile | craftdoc-pcraft.hostile:info-old-err-new-ok-outline-old-err-new-ok-renditions-old-err-new-ok-sniff-err-variant | 8 |
| craftdoc-pcraft.hostile | craftdoc-pcraft.hostile:info-old-ok-new-err-outline-old-ok-new-err | 27 |
| craftdoc-pcraft.hostile | craftdoc-pcraft.hostile:info-old-ok-new-err-outline-old-ok-new-err-renditions-old-ok-new-err | 16 |
| deckcraft-sniff.hostile | deckcraft-sniff.hostile:sniff | 6 |
| effectcraft-read-legacy-store.hostile | effectcraft-read-legacy-store.hostile:new-rejects-archive | 45 |
| effectcraft-read.hostile | effectcraft-read.hostile:bytes-new-adds-entries | 7 |
| effectcraft-read.hostile | effectcraft-read.hostile:new-adds-entries | 368 |
| effectcraft-read.hostile | effectcraft-read.hostile:new-adds-entries-old-entries-lost | 17 |
| effectcraft-read.hostile | effectcraft-read.hostile:new-rejects-archive | 539 |
| effectcraft-read.hostile | effectcraft-read.hostile:old-entries-lost | 2 |
| effectcraft-write.hostile | effectcraft-write.hostile:new-rejects-store-returned-an-empty-archive | 43 |
| effectcraft-write.hostile | effectcraft-write.hostile:utf8-flag | 735 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:index-order | 1805 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-accepts-bad-sector-xfffffffc-in-a-chain | 1 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-accepts-bad-sector-xfffffffd-in-a-chain | 1 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-accepts-bad-sector-xffffffff-in-a-chain | 1 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-accepts-sector-is-outside-the-file | 19 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-accepts-stream-is-truncated | 10 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-difat-chain-loops-or-ends-early | 7 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-directory-loop-or-invalid-entry | 19 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-duplicate-fat-difat-sector | 1 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-fat-difat-count-exceeds-file | 46 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-inconsistent-difat-chain-or-fat-count | 4134 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-invalid-directory-name-length | 32 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-invalid-fat-sector-marker | 972 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-mini-fat-exceeds-file | 40 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-sector-chain-loops-or-uses-marker | 3 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-sector-outside-file | 1 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-stream-has-children | 17 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-unsupported-cfb-version-or-sector-size | 48 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:new-rejects-unsupported-mini-stream-cutoff | 62 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:old-err-new-ok-unreachable-entries-dropped | 22 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:old-ok-new-err | 12 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:old-ok-new-err-unreachable-entries-dropped | 11 |
| filmcraft-tree.hostile | filmcraft-tree.hostile:unreachable-entries-dropped | 3688 |
| gridcraft-is-xls.hostile | gridcraft-is-xls.hostile:sniff | 1558 |
| gridcraft-sniff.hostile | gridcraft-sniff.hostile:sniff | 6 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-difat-chain-loops-or-ends-early | 7 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-directory-index-out-of-range | 17 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-directory-loop-or-invalid-entry | 43 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-duplicate-fat-difat-sector | 1 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-fat-difat-count-exceeds-file | 88 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-inconsistent-difat-chain-or-fat-count | 987 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-invalid-directory-name-length | 32 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-invalid-fat-sector-marker | 972 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-mini-fat-exceeds-file | 40 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-sector-chain-loops-or-uses-marker | 6 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-stream-has-children | 17 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-unsupported-byte-order | 30 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-unsupported-cfb-version-or-sector-size | 48 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:new-rejects-unsupported-mini-stream-cutoff | 62 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:old-err-new-ok | 8 |
| gridcraft-streams.hostile | gridcraft-streams.hostile:old-ok-new-err | 5 |
| pdfcraft-write.hostile | pdfcraft-write.hostile:new-rejects-invalid-zip-entry-name | 43 |
| pdfcraft-write.hostile | pdfcraft-write.hostile:utf8-flag | 735 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-found-reference-to-sector-but-fat-has-only-entries | 3 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-directory-entry-invalid-color | 1 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-directory-entry-name-length-too-large | 4 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-directory-entry-odd-name-length | 3 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-directory-left-sibling-index-is-but-directory-entry-count-is | 2 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-directory-name-ordering-root-entry-vs-root-entry | 6 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-directory-right-sibling-index-is-but-directory-entry-count-is | 1 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-directory-root-stream-len-is-but-should-be-multiple-of | 3 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors | 313 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-fat-sector-pointed-to-twice | 54 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to | 7 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-rejects-difat-chain-loops-or-ends-early | 7 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-rejects-fat-difat-count-exceeds-file | 88 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-rejects-inconsistent-difat-chain-or-fat-count | 2438 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-rejects-invalid-directory-name-length | 4 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-rejects-invalid-fat-sector-marker | 963 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-rejects-mini-fat-exceeds-file | 40 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:new-rejects-sector-missing-from-fat | 12 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:ref-err-craft-cfb-ok | 40 |
| reference-vs-craft-cfb.hostile | reference-vs-craft-cfb.hostile:ref-ok-craft-cfb-err | 2 |
| vectorcraft-read-legacy-deflate.hostile | vectorcraft-read-legacy-deflate.hostile:new-rejects-damaged | 43 |
| vectorcraft-read-legacy-store.hostile | vectorcraft-read-legacy-store.hostile:new-rejects-damaged | 43 |
| vectorcraft-read.hostile | vectorcraft-read.hostile:bytes-contains | 46 |
| vectorcraft-read.hostile | vectorcraft-read.hostile:contains-old-err-new-ok | 5 |
| vectorcraft-read.hostile | vectorcraft-read.hostile:err-variant | 25 |
| vectorcraft-read.hostile | vectorcraft-read.hostile:new-accepts-damaged | 5 |
| vectorcraft-read.hostile | vectorcraft-read.hostile:new-accepts-zip | 1 |
| vectorcraft-read.hostile | vectorcraft-read.hostile:new-rejects-damaged | 74 |
| vectorcraft-read.hostile | vectorcraft-read.hostile:new-rejects-toolarge | 6 |
| vectorcraft-read.hostile | vectorcraft-read.hostile:old-err-new-ok | 9 |
| vectorcraft-write-deflate.hostile | vectorcraft-write-deflate.hostile:new-rejects-invalid-zip-entry-name | 43 |
| vectorcraft-write-deflate.hostile | vectorcraft-write-deflate.hostile:utf8-flag | 734 |
| vectorcraft-write-store.hostile | vectorcraft-write-store.hostile:new-rejects-invalid-zip-entry-name | 43 |
| vectorcraft-write-store.hostile | vectorcraft-write-store.hostile:utf8-flag | 734 |
| wordcraft-sniff.hostile | wordcraft-sniff.hostile:sniff | 2719 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-found-reference-to-sector-but-fat-has-only-entries | 3 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-directory-entry-invalid-color | 1 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-directory-entry-name-length-too-large | 4 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-directory-entry-odd-name-length | 3 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-directory-left-sibling-index-is-but-directory-entry-count-is | 2 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-directory-name-ordering-root-entry-vs-root-entry | 6 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-directory-right-sibling-index-is-but-directory-entry-count-is | 1 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-directory-root-stream-len-is-but-should-be-multiple-of | 3 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors | 313 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-fat-sector-pointed-to-twice | 54 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to | 7 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-rejects-difat-chain-loops-or-ends-early | 7 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-rejects-fat-difat-count-exceeds-file | 88 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-rejects-inconsistent-difat-chain-or-fat-count | 2438 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-rejects-invalid-directory-name-length | 4 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-rejects-invalid-fat-sector-marker | 963 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-rejects-mini-fat-exceeds-file | 40 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:new-rejects-sector-missing-from-fat | 12 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:old-err-new-ok | 40 |
| wordcraft-streams.hostile | wordcraft-streams.hostile:old-ok-new-err | 2 |

stale registry entries: craftdoc-wrapped:info-old-ok-new-err-outline-old-ok-new-err-renditions-old-ok-new-err:tdf131575-xlsx, craftdoc-wrapped:info-old-ok-new-err-outline-old-ok-new-err-renditions-old-ok-new-err:tdf76115-xlsx, craftdoc-wrapped:info-old-ok-new-err-outline-old-ok-new-err-renditions-old-ok-new-err:49609-xlsx, effectcraft-read:new-adds-entries, effectcraft-read:new-rejects-archive:forcepoint107-xlsx, effectcraft-read:new-rejects-archive:ofz35597-1-pptx, effectcraft-read:new-rejects-archive:libreoffice-dbdazaec-docx, effectcraft-read:new-rejects-archive:divino-revelado-pptx, effectcraft-read:new-rejects-archive:rde-imf-ru-sites-default-files-rde-documents-vodootvedenie-2020-xlsb-xls, effectcraft-read-legacy-store:new-rejects-archive:tdf131575-xlsx, effectcraft-read-legacy-store:new-rejects-archive:tdf76115-xlsx, effectcraft-read-legacy-store:new-rejects-archive:fdo76316-docx, effectcraft-read-legacy-store:new-rejects-archive:49609-xlsx, effectcraft-write:new-rejects-store-returned-an-empty-archive:tdf131575-xlsx, effectcraft-write:new-rejects-store-returned-an-empty-archive:tdf76115-xlsx, effectcraft-write:new-rejects-store-returned-an-empty-archive:49609-xlsx, effectcraft-write:utf8-flag, filmcraft-tree:index-order, filmcraft-tree:new-accepts-sector-is-outside-the-file:ofz21531-1-ppt, filmcraft-tree:new-accepts-sector-is-outside-the-file:hang-1-doc, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-11-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-15-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-17-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-19-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-3-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-4-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-5-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-6-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-8-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-9-ppt, filmcraft-tree:new-rejects-inconsistent-difat-chain-or-fat-count:hang-2-doc, filmcraft-tree:old-err-new-ok-unreachable-entries-dropped:47245-test-xls, filmcraft-tree:old-err-new-ok-unreachable-entries-dropped:47251-xls, filmcraft-tree:old-err-new-ok-unreachable-entries-dropped:50426-xls, filmcraft-tree:old-err-new-ok-unreachable-entries-dropped:53984-xls, filmcraft-tree:old-err-new-ok-unreachable-entries-dropped:ex45698-22488-xls, filmcraft-tree:old-ok-new-err-unreachable-entries-dropped:hang-2-doc, filmcraft-tree:unreachable-entries-dropped, gridcraft-streams:new-rejects-sector-outside-file:hang-13-ppt, gridcraft-streams:new-rejects-sector-outside-file:ofz14989-1-ppt, gridcraft-streams:new-rejects-sector-outside-file:ofz57592-1-doc, gridcraft-streams:new-rejects-sector-outside-file:cf5f6fde99a8b3ea5a4946c258b7abad6f30b0c5-ppt, pdfcraft-write:new-rejects-invalid-zip-entry-name:tdf131575-xlsx, pdfcraft-write:new-rejects-invalid-zip-entry-name:tdf76115-xlsx, pdfcraft-write:new-rejects-invalid-zip-entry-name:49609-xlsx, pdfcraft-write:utf8-flag, reference-vs-craft-cfb:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:ofz21531-1-ppt, reference-vs-craft-cfb:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:hang-1-doc, reference-vs-craft-cfb:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:hang-2-doc, reference-vs-craft-cfb:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:hang-4-doc, reference-vs-craft-cfb:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:forcepoint92-doc, reference-vs-craft-cfb:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:47950-lower-doc, reference-vs-craft-cfb:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:47950-normal-doc, reference-vs-craft-cfb:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:47950-upper-doc, reference-vs-craft-cfb:new-accepts-malformed-fat-sector-pointed-to-twice:forcepoint50-grfanchor-1-doc, reference-vs-craft-cfb:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to:hang-12-ppt, reference-vs-craft-cfb:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to:hang-14-ppt, reference-vs-craft-cfb:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to:hang-2-ppt, reference-vs-craft-cfb:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to:hang-3-doc, reference-vs-craft-cfb:new-accepts-malformed-minifat-mini-sector-pointed-to-twice:hang-1-doc, reference-vs-craft-cfb:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:tdf166030-ppt, reference-vs-craft-cfb:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:encrypted-mso2010-abc-docx, reference-vs-craft-cfb:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:encrypted-mso2013-abc-docx, reference-vs-craft-cfb:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:encrypted-pptx-pptx, reference-vs-craft-cfb:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:bug53475-password-is-pass-docx, vectorcraft-read:bytes:unicode-path-docx, vectorcraft-read:contains-old-err-new-ok:ofz4825-1-docx, vectorcraft-read:new-rejects-damaged:tdf131575-xlsx, vectorcraft-read:new-rejects-damaged:tdf76115-xlsx, vectorcraft-read:new-rejects-damaged:ofz9934-1-docx, vectorcraft-read:new-rejects-damaged:49609-xlsx, vectorcraft-read:new-rejects-damaged:duplicate-filename-xlsx, vectorcraft-read:old-err-new-ok:tdf82984-zip64xlsximport-xlsx, vectorcraft-read-legacy-deflate:new-rejects-damaged:tdf131575-xlsx, vectorcraft-read-legacy-deflate:new-rejects-damaged:tdf76115-xlsx, vectorcraft-read-legacy-deflate:new-rejects-damaged:49609-xlsx, vectorcraft-read-legacy-store:new-rejects-damaged:tdf131575-xlsx, vectorcraft-read-legacy-store:new-rejects-damaged:tdf76115-xlsx, vectorcraft-read-legacy-store:new-rejects-damaged:49609-xlsx, vectorcraft-write-deflate:new-rejects-invalid-zip-entry-name:tdf131575-xlsx, vectorcraft-write-deflate:new-rejects-invalid-zip-entry-name:tdf76115-xlsx, vectorcraft-write-deflate:new-rejects-invalid-zip-entry-name:49609-xlsx, vectorcraft-write-deflate:utf8-flag, vectorcraft-write-store:new-rejects-invalid-zip-entry-name:tdf131575-xlsx, vectorcraft-write-store:new-rejects-invalid-zip-entry-name:tdf76115-xlsx, vectorcraft-write-store:new-rejects-invalid-zip-entry-name:49609-xlsx, vectorcraft-write-store:utf8-flag, wordcraft-sniff:sniff:encrypted-mso2010-abc-docx, wordcraft-sniff:sniff:encrypted-mso2013-abc-docx, wordcraft-sniff:sniff:encrypted-pptx-pptx, wordcraft-sniff:sniff:bug53475-password-is-pass-docx, wordcraft-streams:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:ofz21531-1-ppt, wordcraft-streams:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:hang-1-doc, wordcraft-streams:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:hang-2-doc, wordcraft-streams:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:hang-4-doc, wordcraft-streams:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:forcepoint92-doc, wordcraft-streams:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:47950-lower-doc, wordcraft-streams:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:47950-normal-doc, wordcraft-streams:new-accepts-malformed-fat-fat-has-entries-but-file-has-only-sectors:47950-upper-doc, wordcraft-streams:new-accepts-malformed-fat-sector-pointed-to-twice:forcepoint50-grfanchor-1-doc, wordcraft-streams:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to:hang-12-ppt, wordcraft-streams:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to:hang-14-ppt, wordcraft-streams:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to:hang-2-ppt, wordcraft-streams:new-accepts-malformed-minifat-minifat-has-entries-but-mini-sector-points-to:hang-3-doc, wordcraft-streams:new-accepts-malformed-minifat-mini-sector-pointed-to-twice:hang-1-doc, wordcraft-streams:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:tdf166030-ppt, wordcraft-streams:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:encrypted-mso2010-abc-docx, wordcraft-streams:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:encrypted-mso2013-abc-docx, wordcraft-streams:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:encrypted-pptx-pptx, wordcraft-streams:new-accepts-the-difat-lists-fat-sectors-in-a-file-of-sectors:bug53475-password-is-pass-docx

failures (Regression, OnlyNewFails, Panic): 4
