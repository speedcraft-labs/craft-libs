#!/usr/bin/env python3
"""One EffectCraft desktop session per #291 stage; emits craft-journeys markers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def rpc(stream, method: str, params: dict, request_id: int) -> dict:
    stream.write((json.dumps({"id": request_id, "method": method, "params": params}) + "\n").encode())
    stream.flush()
    line = stream.readline()
    if not line:
        raise RuntimeError(f"control channel closed before replying to {method}")
    reply = json.loads(line)
    if reply.get("id") != request_id or reply.get("ok") is False:
        raise RuntimeError(f"control request {method} failed: {reply}")
    return reply


def connect(port: int, process: subprocess.Popen, deadline: float):
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"EffectCraft exited early with status {process.returncode}")
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.25)
            sock.settimeout(max(1.0, deadline - time.monotonic()))
            return sock.makefile("rwb", buffering=0)
        except OSError:
            time.sleep(0.02)
    raise TimeoutError("EffectCraft control channel did not start")


def start(binary: Path, profile: Path, input_path: Path | None = None, timeout_s: float = 60.0):
    profile.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "HOME": str(profile),
        "XDG_CONFIG_HOME": str(profile / ".config"),
        "XDG_DATA_HOME": str(profile / ".local/share"),
        "XDG_CACHE_HOME": str(profile / ".cache"),
    })
    port = free_port()
    command = [str(binary)]
    command.append(str(input_path.resolve()) if input_path is not None else "--empty")
    command.extend(["--control", str(port)])
    started = time.perf_counter_ns()
    process = subprocess.Popen(command, cwd=profile, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stream = connect(port, process, time.monotonic() + timeout_s)
    frame = profile / "startup.png"
    reply = rpc(stream, "ui.screenshot", {"path": str(frame)}, 1)
    result = reply.get("result")
    path = Path(result["path"]) if isinstance(result, dict) and isinstance(result.get("path"), str) else frame
    if not path.is_file() or not path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("EffectCraft did not produce its first interactive frame")
    startup_ns = time.perf_counter_ns() - started
    return process, stream, startup_ns


def frame(stream, profile: Path, t: float, request_id: int) -> str:
    path = profile / f"frame-{request_id}.png"
    reply = rpc(stream, "render.frame", {"time": t, "path": str(path)}, request_id)
    if not isinstance(reply.get("result"), dict) or not path.is_file():
        raise RuntimeError(f"render.frame produced no PNG at {path}")
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("render.frame output is not a PNG")
    return hashlib.sha256(data).hexdigest()


def opened_project_identity(stream) -> str:
    reply = rpc(stream, "engine.execute", {"command": "project.summary", "params": {}}, 30)
    summary = reply.get("result")
    if not isinstance(summary, dict):
        raise RuntimeError("project.summary returned no project")
    comp = next((item for item in summary.get("items", []) if item.get("name") == "Typical 1080p"), None)
    if comp is None or comp.get("layers") != 30 or comp.get("size") != [1920, 1080]:
        raise RuntimeError(f"opened project did not match the pinned 1080p fixture: {comp}")
    identity = {key: comp.get(key) for key in ("name", "type", "size", "duration", "layers", "frameRate")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def export_identity(path: Path) -> str:
    result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "framemd5", "-"],
                            check=True, capture_output=True, text=True)
    return hashlib.sha256(result.stdout.encode()).hexdigest()


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: effectcraft_real_app.py BINARY PROJECT STAGE PROFILE_ROOT", file=sys.stderr)
        return 2
    binary, project, stage, profile_root = map(Path, (sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
    if stage.name not in {"cold-start", "open", "first-frame", "scrub", "export"}:
        return 2
    stage = stage.name
    if not binary.is_file() or not project.is_file():
        raise FileNotFoundError(f"missing EffectCraft binary or project: {binary}, {project}")
    profile = profile_root / f"effectcraft-{stage}-{os.getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    display = None
    if not os.environ.get("DISPLAY") and sys.platform == "linux":
        from desktop_startup import ensure_display
        display = ensure_display()
    process = stream = None
    try:
        if stage == "first-frame":
            process, stream, duration_ns = start(binary.resolve(), profile, project, timeout_s=120)
            opened_identity = opened_project_identity(stream)
            if not opened_identity:
                raise RuntimeError("project did not open before the first visible frame")
            identity = frame(stream, profile, 0.0, 31)
        elif stage == "cold-start":
            process, stream, startup_ns = start(binary.resolve(), profile, timeout_s=60)
            duration_ns = startup_ns
            identity = hashlib.sha256(b"effectcraft-first-interactive-frame").hexdigest()
        else:
            process, stream, _startup_ns = start(binary.resolve(), profile, timeout_s=60)
            opened = time.perf_counter_ns()
            rpc(stream, "engine.execute", {"command": "file.open", "params": {"path": str(project.resolve())}}, 2)
            open_ns = time.perf_counter_ns() - opened
            opened_identity = opened_project_identity(stream)
            if stage == "open":
                duration_ns = open_ns
                identity = opened_identity
            elif stage == "scrub":
                t0 = time.perf_counter_ns()
                hashes = []
                for i, at in enumerate((0.2, 0.4, 0.6, 0.8, 1.0), 3):
                    rpc(stream, "engine.execute", {"command": "time.set", "params": {"time": at}}, i)
                    hashes.append(frame(stream, profile, at, i + 10))
                duration_ns = time.perf_counter_ns() - t0
                identity = hashlib.sha256("|".join(hashes).encode()).hexdigest()
            else:
                output = profile / "typical-short.mp4"
                t0 = time.perf_counter_ns()
                rpc(stream, "engine.execute", {"command": "renderQueue.add", "params": {
                    "comp": "Typical 1080p", "format": "h264", "output": str(output),
                    "timeSpan": "custom", "start": 0.0, "end": 1.0, "frameRate": 15, "audio": "off",
                }}, 3)
                rpc(stream, "engine.execute", {"command": "renderQueue.render", "params": {"wait": True}}, 4)
                duration_ns = time.perf_counter_ns() - t0
                identity = export_identity(output)
        print(f"CRAFT_JOURNEY_NS={duration_ns}")
        print(f"CRAFT_OUTPUT_SHA256={identity}")
        return 0
    finally:
        if stream is not None:
            stream.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if display is not None:
            display.terminate()
            display.wait(timeout=2)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"EffectCraft typical journey failed: {error}", file=sys.stderr)
        raise SystemExit(1)
