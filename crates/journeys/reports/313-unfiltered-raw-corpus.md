# Rejected 1,262-file import pilot

The guarded Agentbox pilot offered only 1,259 files in the import review and
failed before any accepted action sample. Its retained catalog contains exactly
those 1,259 names. Missing: pixls-747.cr2, pixls-2664.cr2, pixls-2813.cr2.
All three official raw.pixls.us SHA-256 checksums match the downloaded originals.
Their PowerShot payloads lack TIFF/CR2 headers; the source descriptions for 2664
and 2813 explicitly identify CHDK. This is a payload compatibility failure, not
an import performance result or reason to trim a successful latency sample.

Keep the immutable original pins and all failed catalog/control/log/image
artifacts in ticket 313's single NAS keep root. The next diagnostic pilot uses
1,259 distinct importable CC0 originals, excludes these three explicitly, and
starts fresh. Never seed a lone pilot build into contiguous paired calibration.

Raw evidence: sensitivity/heavy-aa-pilot-v5/point/report.json,
heavy-pilot-missing.json, heavy-pilot-source-diagnosis.json. Frozen app commit:
5f816e195b9b23febef83f6c3687e7c049f9c93d; action driver SHA-256:
64e0052ce45cf430c80ef9b79f67ff208702ab7dc42788fd3b0948e048d902c2.
