#!/usr/bin/env python3
"""Measure a desktop app from external launch to its first captured interactive frame."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def ensure_display() -> subprocess.Popen | None:
    if sys.platform != "linux" or os.environ.get("DISPLAY"):
        return None
    executable = shutil.which("Xvfb")
    if executable is None:
        raise RuntimeError("DISPLAY is unset and Xvfb is unavailable")
    probe = shutil.which("xdpyinfo")
    if probe is None:
        raise RuntimeError("DISPLAY is unset and xdpyinfo is unavailable")
    for number in range(90, 200):
        endpoint = Path(f"/tmp/.X11-unix/X{number}")
        if endpoint.exists():
            continue
        display = f":{number}"
        process = subprocess.Popen(
            [executable, display, "-screen", "0", "1280x800x24", "-nolisten", "tcp", "-extension", "GLX"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and process.poll() is None:
            ready = endpoint.exists() and subprocess.run(
                [probe, "-display", display],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode == 0
            if ready:
                os.environ["DISPLAY"] = display
                return process
            time.sleep(0.02)
        process.terminate()
        process.wait(timeout=2)
    raise RuntimeError("could not start a private Xvfb display")


def recv_line(stream) -> dict:
    line = stream.readline()
    if not line:
        raise RuntimeError("control channel closed before replying")
    value = json.loads(line)
    if value.get("error") or value.get("ok") is False:
        raise RuntimeError(f"control request failed: {value.get('error', value)}")
    return value


def rpc(stream, method: str, params: dict, request_id: int, token: str | None = None) -> dict:
    request = {"id": request_id, "method": method, "params": params}
    if token is not None:
        request["token"] = token
    stream.write((json.dumps(request) + "\n").encode())
    stream.flush()
    try:
        reply = recv_line(stream)
    except Exception as error:
        raise RuntimeError(f"control RPC {method} failed: {error}") from error
    if reply.get("id") != request_id:
        raise RuntimeError(f"control reply id mismatch: expected {request_id}, got {reply.get('id')}")
    return reply


def screenshot_ok(reply: dict, path: Path | None) -> bool:
    result = reply.get("result")
    if path is not None and path.is_file():
        return path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    if isinstance(result, dict) and isinstance(result.get("path"), str):
        screenshot_path = Path(result["path"])
        if screenshot_path.is_file() and screenshot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            return True
    candidates = []
    if isinstance(result, str):
        candidates.append(result)
    if isinstance(result, dict):
        candidates.extend(v for v in result.values() if isinstance(v, str))
    for candidate in candidates:
        try:
            if base64.b64decode(candidate, validate=True).startswith(b"\x89PNG\r\n\x1a\n"):
                return True
        except (ValueError, base64.binascii.Error):
            pass
    return False


def launch(app: str, binary: Path, profile: Path, timeout_s: float = 45.0) -> int:
    profile.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "HOME": str(profile),
        "XDG_CONFIG_HOME": str(profile / ".config"),
        "XDG_DATA_HOME": str(profile / ".local/share"),
        "XDG_CACHE_HOME": str(profile / ".cache"),
    })
    if app == "cadcraft":
        runtime_dir = profile / ".runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        runtime_dir.chmod(0o700)
        env["XDG_RUNTIME_DIR"] = str(runtime_dir)
        env["CADCRAFT_CONFIG_DIR"] = str(profile / ".config" / "cadcraft")
    for key in ("PHOTOCRAFT_NO_PREFS", "PDFCRAFT_NO_PREFS", "GRIDCRAFT_NO_PREFS"):
        env.pop(key, None)
    control_file = profile / "control.json"
    control_file.unlink(missing_ok=True)
    token = secrets.token_hex(32)
    if app == "pdfcraft":
        command = [str(binary), "--control", str(control_file)]
        port = None
    elif app == "cadcraft":
        port = free_port()
        command = [str(binary), "--control", str(port)]
        token_file = profile / ".runtime" / f"cadcraft-control-{port}.token"
    else:
        port = free_port()
        command = [str(binary), "--control", str(port), "--control-token", token]

    started = time.perf_counter_ns()
    debug_log = (profile / "startup-app.log").open("wb") if os.environ.get("CRAFT_STARTUP_DEBUG") == "1" else None
    proc = subprocess.Popen(command, cwd=profile, env=env, stdout=debug_log or subprocess.DEVNULL, stderr=debug_log or subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + timeout_s
        if app == "pdfcraft":
            while time.monotonic() < deadline and not control_file.exists():
                if proc.poll() is not None:
                    raise RuntimeError(f"{app} exited before publishing its control endpoint (status {proc.returncode})")
                time.sleep(0.01)
            endpoint = json.loads(control_file.read_text())
            port, token = int(endpoint["port"]), str(endpoint["token"])
        elif app == "cadcraft":
            token_deadline = min(deadline, time.monotonic() + 5)
            while time.monotonic() < token_deadline and not token_file.is_file():
                if proc.poll() is not None:
                    raise RuntimeError(f"{app} exited before publishing its control token (status {proc.returncode})")
                time.sleep(0.01)
            if not token_file.is_file():
                raise TimeoutError(f"{app} did not publish its control token")
            token = token_file.read_text().strip()
        stream = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"{app} exited before its first frame (status {proc.returncode})")
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=0.25)
                sock.settimeout(max(1.0, deadline - time.monotonic()))
                candidate = sock.makefile("rwb", buffering=0)
            except OSError:
                time.sleep(0.01)
                continue
            try:
                # The listener is bound before the window starts; a TCP connect can therefore
                # reach its backlog before the UI callback starts the control server thread.
                if app != "cadcraft":
                    rpc(candidate, "auth", {"token": token}, 0)
                stream = candidate
                break
            except RuntimeError as error:
                candidate.close()
                cause = error.__cause__
                if isinstance(cause, OSError) or (isinstance(cause, RuntimeError) and str(cause) == "control channel closed before replying"):
                    time.sleep(0.01)
                    continue
                raise
        if stream is None:
            raise TimeoutError(f"{app} control channel did not become available")
        try:
            frame = rpc(stream, "ui.screenshot", {}, 1, token if app == "cadcraft" else None)
            elapsed = time.perf_counter_ns() - started
            if not screenshot_ok(frame, None):
                raise RuntimeError(f"{app} screenshot reply did not contain a rendered PNG")
            # The frame capture runs on the UI thread; a subsequent inspection confirms the
            # window is accepting control requests. Its latency is deliberately outside the mark.
            rpc(stream, "ui.inspect" if app != "pdfcraft" else "ui.state", {}, 2, token if app == "cadcraft" else None)
            try:
                rpc(stream, "app.quit" if app != "pdfcraft" else "ui.quit", {}, 3, token if app == "cadcraft" else None)
            except Exception:
                pass
            return elapsed
        finally:
            stream.close()
    except Exception as error:
        status = proc.poll()
        if status is not None:
            raise RuntimeError(f"{app} exited with status {status} during startup: {error}") from error
        raise
    finally:
        if proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        if debug_log is not None:
            debug_log.close()


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: desktop_startup.py APP BINARY cold|warm PROFILE", file=sys.stderr)
        return 2
    app, binary_text, mode, profile_text = sys.argv[1:]
    if app not in {"photocraft", "pdfcraft", "gridcraft", "cadcraft"} or mode not in {"cold", "warm"}:
        print("invalid app or mode", file=sys.stderr)
        return 2
    binary, profile = Path(binary_text).resolve(), Path(profile_text).resolve()
    if not binary.is_file():
        print(f"app binary not found: {binary}", file=sys.stderr)
        return 2
    display = ensure_display()
    try:
        if mode == "cold":
            shutil.rmtree(profile, ignore_errors=True)
        elif not (profile / ".startup-seeded").exists():
            launch(app, binary, profile)
            (profile / ".startup-seeded").touch()
        elapsed = launch(app, binary, profile)
        digest = hashlib.sha256(f"{app}|{mode}|first-interactive-frame".encode()).hexdigest()
        print(f"CRAFT_JOURNEY_NS={elapsed}")
        print(f"CRAFT_OUTPUT_SHA256={digest}")
        return 0
    finally:
        if display is not None:
            display.terminate()
            display.wait(timeout=2)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"startup benchmark failed: {error}", file=sys.stderr)
        raise SystemExit(1)
