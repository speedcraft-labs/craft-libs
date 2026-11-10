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
ffprobe = shutil.which("ffprobe")
if not ffmpeg:
    raise SystemExit("ffmpeg is required to prepare the 60-second source segment")
if not ffprobe:
    raise SystemExit("ffprobe is required to validate the exported media")
if not music.is_file() or hashlib.sha256(music.read_bytes()).hexdigest() != music_sha256:
    raise SystemExit("the pinned CC0 music source is missing or has the wrong SHA-256")


def export_signature(path: Path) -> tuple[dict, str]:
    probed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,profile,width,height,avg_frame_rate,nb_frames,duration,sample_rate,channels",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    metadata = json.loads(probed.stdout)
    video = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise SystemExit("FilmCraft export must contain both video and audio")
    if video.get("codec_name") != "h264" or (video.get("width"), video.get("height")) != (1920, 1080):
        raise SystemExit("FilmCraft export is not 1080p H.264")
    if audio.get("codec_name") != "aac" or (audio.get("sample_rate"), audio.get("channels")) != ("48000", 2):
        raise SystemExit("FilmCraft export is not stereo 48 kHz AAC")

    audio_frames = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "framemd5", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    video_signature = {
        key: video[key]
        for key in ("codec_name", "profile", "width", "height", "avg_frame_rate", "nb_frames", "duration")
        if key in video
    }
    audio_signature = {
        key: audio[key]
        for key in ("codec_name", "profile", "sample_rate", "channels", "nb_frames", "duration")
        if key in audio
    }
    signature = {
        "video": video_signature,
        "audio": audio_signature,
        "format_duration": metadata.get("format", {}).get("duration"),
        "decoded_audio_framemd5_sha256": hashlib.sha256(audio_frames).hexdigest(),
        "video_equivalence_bound": "pairwise H.264 PSNR mean >=50 dB and every frame >=45 dB",
    }
    return signature, hashlib.sha256(audio_frames).hexdigest()

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
timeline_identity = [
    {key: row[key] for key in ("view", "clips", "frames", "waveform_streams", "waveform_buckets", "shapes", "vertices")}
    for row in timeline_rows
]
media_signature, audio_identity = export_signature(exported)
identity_payload = {"timeline": timeline_identity, "export": media_signature}
identity = hashlib.sha256(json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
print(f"CRAFT_JOURNEY_NS={elapsed}")
print(f"CRAFT_OUTPUT_SHA256={identity}")
print(
    f"duration_seconds=60 playback_scrub_timeline_rows={len(scenarios)} cut_regions=16 "
    f"waveform_buckets={timeline_rows[0]['waveform_buckets']} export_bytes={exported.stat().st_size} "
    f"decoded_audio_framemd5_sha256={audio_identity} music_sha256={music_sha256}"
)
