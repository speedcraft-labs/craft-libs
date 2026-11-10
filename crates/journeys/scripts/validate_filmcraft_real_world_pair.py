#!/usr/bin/env python3
"""Validate decoded FilmCraft export equivalence after a paired real-world journey."""

import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
from pathlib import Path


report_path = Path(sys.argv[1])
target_root = Path(os.environ["CRAFT_JOURNEYS_TARGET_DIR"])
hyper_root = Path(os.environ["ARTCRAFT_HYPER_ROOT"])
app_repo = hyper_root / "repos" / "apps" / "filmcraft"
ffmpeg = shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe")
if not ffmpeg or not ffprobe:
    raise SystemExit("ffmpeg and ffprobe are required for FilmCraft output equivalence")


def revision(ref: str) -> str:
    result = subprocess.run(["git", "-C", str(app_repo), "rev-parse", ref], text=True, capture_output=True, check=True)
    return result.stdout.strip()


def export_path(app_revision: str) -> Path:
    key = f"app-locked:{app_revision}"
    target_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
    return target_root / "filmcraft" / target_hash / "filmcraft-real-world" / "iss-export.mp4"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stream_signature(path: Path) -> tuple[dict, dict, str]:
    result = subprocess.run(
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
        capture_output=True,
        check=True,
    )
    metadata = json.loads(result.stdout)
    video = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise RuntimeError(f"missing video or audio stream in {path}")
    video_fields = ("codec_name", "profile", "width", "height", "avg_frame_rate", "nb_frames", "duration")
    audio_fields = ("codec_name", "profile", "sample_rate", "channels", "nb_frames", "duration")
    video_signature = {key: video[key] for key in video_fields if key in video}
    audio_signature = {key: audio[key] for key in audio_fields if key in audio}
    frames = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "framemd5", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return video_signature, audio_signature, hashlib.sha256(frames).hexdigest()


base_revision = revision(os.environ["CRAFT_JOURNEYS_APP_BASE_REV"])
head_revision = revision(os.environ["CRAFT_JOURNEYS_APP_HEAD_REV"])
base = export_path(base_revision)
head = export_path(head_revision)
if not base.is_file() or not head.is_file():
    raise SystemExit(f"missing paired export: {base} or {head}")

base_video, base_audio, base_audio_hash = stream_signature(base)
head_video, head_audio, head_audio_hash = stream_signature(head)
metadata_equal = base_video == head_video and base_audio == head_audio
audio_equal = base_audio_hash == head_audio_hash

stats_path = report_path.with_name("filmcraft-video-psnr-per-frame.log")
stats_path.unlink(missing_ok=True)
subprocess.run(
    [
        ffmpeg,
        "-v",
        "error",
        "-threads",
        "2",
        "-i",
        str(base),
        "-i",
        str(head),
        "-filter_complex",
        f"[0:v:0][1:v:0]psnr=stats_file={stats_path}",
        "-f",
        "null",
        "-",
    ],
    capture_output=True,
    check=True,
)
psnr_values = []
for line in stats_path.read_text().splitlines():
    match = re.search(r"psnr_avg:([0-9.]+|inf)", line)
    if match:
        psnr_values.append(float("inf") if match.group(1) == "inf" else float(match.group(1)))
finite_psnr = [value for value in psnr_values if math.isfinite(value)]
exact_frames = len(psnr_values) - len(finite_psnr)
mean_finite_psnr = statistics.mean(finite_psnr) if finite_psnr else None
min_finite_psnr = min(finite_psnr) if finite_psnr else None
expected_frames = int(base_video.get("nb_frames", "0"))
complete_frame_check = len(psnr_values) == expected_frames
psnr_pass = complete_frame_check and (not finite_psnr or (mean_finite_psnr >= 50.0 and min_finite_psnr >= 45.0))
passed = metadata_equal and audio_equal and psnr_pass

equivalence = {
    "metric": "decoded H.264 pairwise PSNR; exact decoded audio and stream metadata",
    "bound": "finite-frame mean PSNR >=50 dB and every finite frame >=45 dB; exact frames are counted separately",
    "passed": passed,
    "video": {
        "base": base_video,
        "head": head_video,
        "metadata_equal": base_video == head_video,
        "compared_frames": len(psnr_values),
        "exact_frames": exact_frames,
        "finite_frame_mean_psnr_db": mean_finite_psnr,
        "minimum_finite_frame_psnr_db": min_finite_psnr,
        "maximum_finite_frame_psnr_db": max(finite_psnr) if finite_psnr else None,
        "finite_frame_threshold_db": 45.0,
        "mean_threshold_db": 50.0,
        "stats_file": str(stats_path),
    },
    "audio": {
        "base": base_audio,
        "head": head_audio,
        "base_decoded_framemd5_sha256": base_audio_hash,
        "head_decoded_framemd5_sha256": head_audio_hash,
        "decoded_samples_equal": audio_equal,
    },
    "raw_file_sha256": {"base": file_sha256(base), "head": file_sha256(head)},
}

report = json.loads(report_path.read_text())
report["output_equivalence"] = equivalence
if not passed:
    report["publishable"] = False
    problems = report.setdefault("publish_problems", [])
    problems.append("FilmCraft real-world output equivalence failed its exact-audio/stream/PSNR bound")
temporary = report_path.with_suffix(report_path.suffix + ".tmp")
temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
temporary.replace(report_path)
report_path.with_name("filmcraft-output-equivalence.json").write_text(json.dumps(equivalence, indent=2, sort_keys=True) + "\n")

mean_text = "all exact" if mean_finite_psnr is None else f"{mean_finite_psnr:.2f}"
min_text = "all exact" if min_finite_psnr is None else f"{min_finite_psnr:.2f}"
print(
    f"output equivalence: {'pass' if passed else 'FAIL'}; audio_exact={audio_equal}; "
    f"stream_metadata_equal={metadata_equal}; video_frames={len(psnr_values)}; "
    f"exact_frames={exact_frames}; finite_mean_psnr_db={mean_text}; "
    f"min_finite_frame_psnr_db={min_text}"
)
if not passed:
    raise SystemExit(1)
