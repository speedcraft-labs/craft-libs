# Rejected shared-target builds (313b)

After a fork-point build, a later main build reused incompatible path-workspace
artifacts and failed on missing bm3d/crystal/GrainModel APIs; upstream engine
reported 80 analogous errors. No performance observation used these artifacts.
The earlier 313 build notes already documented this Cargo behavior.

Correction: serialize the whole preparation transaction, clean only selected
LightCraft workspace packages in release, rebuild and copy before unlocking.
Keep one target and reuse third-party dependencies. Require workspace_clean=true
in provenance, plus an unchanged common recorder patch throughout the build.
Raw logs: keep/313b-inapp-timing/release-{point,upstream,aa-a-validated}.log.
