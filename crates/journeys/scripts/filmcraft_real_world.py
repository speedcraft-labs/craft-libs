#!/usr/bin/env python3
"""Run a real FilmCraft open/play/scrub/timeline-waveform/export path."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


source = Path(sys.argv[1])
target = Path(sys.argv[2])
bin_dir = target / "release" / "examples"
run_dir = target / "filmcraft-real-world"
fixture_dir = run_dir / "fixtures"
playback_dir = fixture_dir / "playback"
playback_dir.mkdir(parents=True, exist_ok=True)
trimmed = run_dir / "iss-first-60s-with-music.mp4"
exported = run_dir / "iss-export.mp4"
corpus = Path(os.environ.get("ARTCRAFT_CORPUS", "/jobs/work/speedcraft-labs/hyper/corpus"))
music = corpus / "real-av-media-2026" / "monplaisir-free-to-use-3.ogg"
music_sha256 = "e179f2c23bda0bb6dcec90bda9d856959724f75335951ca4d2228aff24aa44ea"
ffmpeg = shutil.which("ffmpeg")
if not ffmpeg:
    raise SystemExit("ffmpeg is required to prepare the 60-second source segment")
if not music.is_file() or hashlib.sha256(music.read_bytes()).hexdigest() != music_sha256:
    raise SystemExit("the pinned CC0 music source is missing or has the wrong SHA-256")

# Keep the NASA video stream untouched and add a pinned CC0 soundtrack, as in a basic edited
# music-video project. Only the audio is encoded, at a fixed setting, to put it in MP4.
subprocess.run(
    [
        ffmpeg,
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-i",
        str(music),
        "-t",
        "60",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-map_metadata",
        "-1",
        "-movflags",
        "+faststart",
        str(trimmed),
    ],
    check=True,
)
if not trimmed.is_file() or trimmed.stat().st_size == 0:
    raise SystemExit("ffmpeg did not produce the 60-second clip")
(playback_dir / "a1080.mp4").unlink(missing_ok=True)
(playback_dir / "a1080.mp4").symlink_to(trimmed)

bench = bin_dir / "bench"
bench_export = bin_dir / "bench_export"
env = os.environ.copy()
env["FILMCRAFT_FIXTURES"] = str(fixture_dir)
env["FILMCRAFT_TIMELINE_MEDIA"] = str(trimmed)
report_dir = run_dir / "reports"
report_dir.mkdir(parents=True, exist_ok=True)

started = time.perf_counter_ns()
play_scrub = subprocess.run(
    [str(bench), "--sections", "playback,scrub,timeline", "--only", "h264-1080", "--quick", "--cpu", "--hw", "off", "--out", str(report_dir)],
    env=env,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=True,
)
if "playback h264-1080" not in play_scrub.stderr or "scrub h264-1080" not in play_scrub.stderr:
    raise SystemExit("FilmCraft did not complete both playback and scrub scenarios")

subprocess.run(
    [str(bench_export), "--source", str(trimmed), "--secs", "60", "--runs", "1", "--format", "h264", "--keep", str(exported)],
    env=env,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=True,
)
if not exported.is_file() or exported.stat().st_size == 0:
    raise SystemExit("FilmCraft did not export the selected clip")

report = report_dir / "bench-latest.json"
if not report.is_file():
    raise SystemExit("FilmCraft playback/scrub report is missing")
report_data = json.loads(report.read_text())
scenarios = [row for section in report_data.get("sections", []) for row in section.get("rows", [])]
timeline_rows = [row for section in report_data.get("sections", []) if section.get("section") == "timeline" for row in section.get("rows", [])]
if len(scenarios) < 4 or len(timeline_rows) < 2:
    raise SystemExit("FilmCraft playback/scrub/timeline results are incomplete")
if any(row.get("clips") != 16 for row in timeline_rows):
    raise SystemExit("FilmCraft timeline did not retain all eight video and eight soundtrack regions")
if any(row.get("waveform_streams", 0) < 1 or row.get("waveform_buckets", 0) < 1 for row in timeline_rows):
    raise SystemExit("FilmCraft timeline did not paint waveform data from the pinned soundtrack")
elapsed = time.perf_counter_ns() - started
identity_hash = hashlib.sha256(exported.read_bytes())
timeline_identity = [
    {key: row[key] for key in ("view", "clips", "frames", "waveform_streams", "waveform_buckets", "shapes", "vertices")}
    for row in timeline_rows
]
identity_hash.update(json.dumps(timeline_identity, sort_keys=True, separators=(",", ":")).encode())
identity = identity_hash.hexdigest()
print(f"CRAFT_JOURNEY_NS={elapsed}")
print(f"CRAFT_OUTPUT_SHA256={identity}")
print(
    f"duration_seconds=60 playback_scrub_timeline_rows={len(scenarios)} cut_regions=16 "
    f"waveform_buckets={timeline_rows[0]['waveform_buckets']} export_bytes={exported.stat().st_size} "
    f"music_sha256={music_sha256}"
)
