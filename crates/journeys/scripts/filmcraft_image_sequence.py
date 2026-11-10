#!/usr/bin/env python3
"""Open a generated 60-second 1080p still sequence, play/scrub it, and export a selected cut."""

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
run_dir = target / "filmcraft-image-sequence"
frames_dir = run_dir / "sequence"
frames_dir.mkdir(parents=True, exist_ok=True)
music = Path(os.environ.get("ARTCRAFT_CORPUS", "/jobs/work/speedcraft-labs/hyper/corpus")) / "real-av-media-2026" / "monplaisir-free-to-use-3.ogg"
first = frames_dir / "iss_000001.jpg"
last = frames_dir / "iss_001798.jpg"
ffmpeg = shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe")
if not ffmpeg or not ffprobe:
    raise SystemExit("ffmpeg and ffprobe are required for the deterministic image-sequence payload")
music_sha256 = "e179f2c23bda0bb6dcec90bda9d856959724f75335951ca4d2228aff24aa44ea"
if not music.is_file() or hashlib.sha256(music.read_bytes()).hexdigest() != music_sha256:
    raise SystemExit("the pinned CC0 music source is missing or has the wrong SHA-256")

if not first.is_file() or not last.is_file() or len(list(frames_dir.glob("iss_*.jpg"))) != 1798:
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-v", "error", "-y", "-i", str(source), "-t", "60",
            "-vf", "fps=30000/1001", "-frames:v", "1798", "-start_number", "1", "-q:v", "3",
            str(frames_dir / "iss_%06d.jpg"),
        ],
        check=True,
    )
if len(list(frames_dir.glob("iss_*.jpg"))) != 1798:
    raise SystemExit("the one-minute 29.97 fps source did not produce 1,798 numbered images")

bench = target / "release" / "examples" / "bench"
bench_export = target / "release" / "examples" / "bench_export"
exported = run_dir / "selected-cut.mp4"
report_dir = run_dir / "reports"
report_dir.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update(
    {
        "FILMCRAFT_SEQUENCE_MEDIA": str(first),
        "FILMCRAFT_TIMELINE_MEDIA": str(first),
        "FILMCRAFT_TIMELINE_AUDIO": str(music),
        "FILMCRAFT_TIMELINE_IMAGE_SEQUENCE": "1",
        "FILMCRAFT_EXPORT_AUDIO": str(music),
        "FILMCRAFT_EXPORT_IMAGE_SEQUENCE": "1",
    }
)


def stream_signature(path: Path) -> tuple[dict, str]:
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,avg_frame_rate,nb_frames,duration,sample_rate,channels", "-show_entries", "format=duration", "-of", "json", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    metadata = json.loads(probe.stdout)
    video = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise SystemExit("the image-sequence cut export must contain video and soundtrack")
    if video.get("codec_name") != "h264" or (video.get("width"), video.get("height")) != (1920, 1080):
        raise SystemExit("image-sequence export is not 1080p H.264")
    if audio.get("codec_name") != "aac" or (audio.get("sample_rate"), audio.get("channels")) != ("48000", 2):
        raise SystemExit("image-sequence export is not stereo 48 kHz AAC")
    decoded = {}
    for kind in ("v:0", "a:0"):
        frames = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(path), "-map", f"0:{kind}", "-f", "framemd5", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        ).stdout
        decoded[kind] = hashlib.sha256(frames).hexdigest()
    return {"streams": metadata.get("streams", []), "format_duration": metadata.get("format", {}).get("duration"), "decoded_video_framemd5_sha256": decoded["v:0"], "decoded_audio_framemd5_sha256": decoded["a:0"]}, decoded["v:0"] + decoded["a:0"]


started = time.perf_counter_ns()
run = subprocess.run(
    [str(bench), "--sections", "playback,scrub,timeline", "--only", "image-sequence", "--quick", "--cpu", "--hw", "off", "--out", str(report_dir)],
    env=env,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=True,
)
if "playback image-sequence full" not in run.stderr or "scrub image-sequence" not in run.stderr:
    raise SystemExit("FilmCraft did not play and scrub the numbered still sequence")
subprocess.run(
    [str(bench_export), "--source", str(first), "--secs", "5", "--runs", "1", "--format", "h264", "--keep", str(exported)],
    env=env,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=True,
)
if not exported.is_file() or exported.stat().st_size == 0:
    raise SystemExit("FilmCraft did not export the selected five-second cut")

report = report_dir / "bench-latest.json"
if not report.is_file():
    raise SystemExit("FilmCraft image-sequence benchmark report is missing")
data = json.loads(report.read_text())
sections = data.get("sections", [])
playback_rows = [row for section in sections if section.get("section") == "playback" for row in section.get("rows", [])]
scrub_rows = [row for section in sections if section.get("section") == "scrub" for row in section.get("rows", [])]
timeline_rows = [row for section in sections if section.get("section") == "timeline" for row in section.get("rows", [])]
if len(playback_rows) != 1 or len(scrub_rows) != 1 or len(timeline_rows) != 2:
    raise SystemExit("FilmCraft image-sequence play/scrub/timeline rows are incomplete")
if any(row.get("scenario") != "image-sequence" for row in playback_rows + scrub_rows):
    raise SystemExit("FilmCraft did not route playback and scrub through the numbered-image source")
if any(row.get("clips") != 16 or row.get("waveform_streams", 0) < 1 or row.get("waveform_buckets", 0) < 1 for row in timeline_rows):
    raise SystemExit("FilmCraft timeline did not retain the eight video/audio regions and soundtrack waveform")
media, decoded_hashes = stream_signature(exported)
timeline_identity = [{key: row[key] for key in ("view", "clips", "frames", "waveform_streams", "waveform_buckets", "shapes", "vertices")} for row in timeline_rows]
identity_payload = {"timeline": timeline_identity, "export": media}
identity = hashlib.sha256(json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
elapsed = time.perf_counter_ns() - started
print(f"CRAFT_JOURNEY_NS={elapsed}")
print(f"CRAFT_OUTPUT_SHA256={identity}")
print(f"duration_seconds=60 image_frames=1798 image_bytes={sum(p.stat().st_size for p in frames_dir.glob('iss_*.jpg'))} playback_rows=1 scrub_rows=1 timeline_rows=2 selected_export_seconds=5 decoded_stream_framemd5_sha256={decoded_hashes} soundtrack_sha256={music_sha256}")
