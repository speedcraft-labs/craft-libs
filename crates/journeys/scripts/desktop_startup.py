#!/usr/bin/env python3
"""Measure desktop startup to the first mapped window and validate its frame afterward."""

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


MAP_ONLY_APPS = {"figcraft", "materialcraft", "designcraft", "soundcraft", "filmcraft"}


X11_STARTUP_TITLES = {
    "cadcraft": "CADCraft",
    "deckcraft": "DeckCraft",
    "gridcraft": "GridCraft,Book1",
    "pdfcraft": "PdfCraft",
    "photocraft": "PhotoCraft",
    "vectorcraft": "VectorCraft",
    "effectcraft": "EffectCraft",
    "lightcraft": "LightCraft",
    "wordcraft": "WordCraft",
    "figcraft": "FigCraft",
    "materialcraft": "MaterialCraft",
    "designcraft": "DesignCraft",
    "soundcraft": "SoundCraft",
    "filmcraft": "FilmCraft",
}


def mac_window_watch_binary() -> Path:
    binary = Path("/private/tmp/craft-mapnotify-window-watch")
    source = Path(__file__).with_name("mac_window_watch.swift")
    if not binary.is_file() or binary.stat().st_mtime_ns < source.stat().st_mtime_ns:
        result = subprocess.run(["swiftc", "-O", str(source), "-o", str(binary)], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"could not build the Cocoa window observer: {result.stderr.strip()}")
    return binary



def vectorcraft_adapter(profile: Path) -> str | None:
    log = profile / "vectorcraft-config" / "logs" / "vectorcraft.log"
    if not log.is_file():
        return None
    for line in reversed(log.read_text(errors="replace").splitlines()):
        marker = " rendering with "
        if marker in line:
            return line.split(marker, 1)[1].split(" (", 1)[0].strip() or None
    return None

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


def rpc(stream, method: str, params: dict, request_id: int, token: str | None = None, token_field: str = "token") -> dict:
    request = {"id": request_id, "method": method, "params": params}
    if token is not None:
        request[token_field] = token
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


def write_timing_diagnostic(profile: Path, **markers: int | None) -> None:
    diagnostics = profile.parent / f"{profile.name}.timing.jsonl"
    with diagnostics.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(markers, sort_keys=True) + "\n")


def launch(
    app: str,
    binary: Path,
    profile: Path,
    timeout_s: float = 45.0,
    *,
    input_path: Path | None = None,
    library_path: Path | None = None,
) -> int:
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
    if app == "wordcraft":
        env["WORDCRAFT_PROFILE_DIR"] = str(profile)
    if app == "lightcraft":
        env["LIGHTCRAFT_CONFIG_DIR"] = str(profile / "lightcraft-config")
    for key in ("PHOTOCRAFT_NO_PREFS", "PDFCRAFT_NO_PREFS", "GRIDCRAFT_NO_PREFS", "WORDCRAFT_NO_PREFS"):
        env.pop(key, None)
    control_file = profile / "control.json"
    control_file.unlink(missing_ok=True)
    token = secrets.token_hex(32)
    if app == "pdfcraft":
        command = [str(binary), "--control", str(control_file)]
        port = None
    elif app == "lightcraft":
        if library_path is None:
            raise RuntimeError("LightCraft startup requires a prepared library path")
        port = free_port()
        command = [str(binary), "--library", str(library_path), "--no-demo", "--control", str(port)]
        if input_path is not None:
            command.append(str(input_path))
    elif app == "wordcraft":
        port = free_port()
        command = [str(binary), "--control", str(port)]
        token_file = profile / f"control-key.local-{port}"
    elif app == "cadcraft":
        port = free_port()
        command = [str(binary), "--control", str(port)]
        token_file = profile / ".runtime" / f"cadcraft-control-{port}.token"
    elif app == "vectorcraft":
        port = free_port()
        command = [str(binary), "--control", str(port), "--new-instance"]
    elif app in MAP_ONLY_APPS:
        port = free_port()
        command = [str(binary), "--control", str(port)]
        if app in {"materialcraft", "filmcraft"}:
            command.append("--empty")
    elif app == "effectcraft":
        if input_path is None:
            raise RuntimeError("EffectCraft startup requires a project path")
        port = free_port()
        command = [str(binary), str(input_path), "--control", str(port)]
    elif app == "deckcraft":
        port = free_port()
        command = [str(binary), "--control", str(port)]
    else:
        port = free_port()
        command = [str(binary), "--control", str(port), "--control-token", token]

    # Attach before launch so the mark is the window's map event, not the later screenshot RPC.
    map_watch = None
    mapped_at_path = profile / "window-mapped.monotonic-ns"
    mac_pid_path = profile / "mac-window-pid"
    if app in X11_STARTUP_TITLES and sys.platform == "darwin":
        ready_path = profile / "mac-window-watch.ready"
        ready_path.unlink(missing_ok=True)
        mapped_at_path.unlink(missing_ok=True)
        mac_pid_path.unlink(missing_ok=True)
        map_watch = subprocess.Popen(
            [str(mac_window_watch_binary()), str(ready_path), str(mac_pid_path), str(mapped_at_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ready_deadline = time.monotonic() + 10
        while not ready_path.is_file() and map_watch.poll() is None and time.monotonic() < ready_deadline:
            time.sleep(0.001)
        if not ready_path.is_file():
            map_watch.terminate()
            map_watch.wait(timeout=2)
            raise RuntimeError("Cocoa window observer did not attach before app launch")
    elif app in X11_STARTUP_TITLES and sys.platform == "linux" and os.environ.get("DISPLAY"):
        ready_path = profile / "x11-map-watch.ready"
        ready_path.unlink(missing_ok=True)
        mapped_at_path.unlink(missing_ok=True)
        map_watch = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).with_name("x11_map_watch.py")),
                X11_STARTUP_TITLES[app],
                str(ready_path),
                str(mapped_at_path),
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ready_deadline = time.monotonic() + 2
        while not ready_path.is_file() and map_watch.poll() is None and time.monotonic() < ready_deadline:
            time.sleep(0.001)
        if not ready_path.is_file():
            map_watch.terminate()
            map_watch.wait(timeout=2)
            raise RuntimeError(f"X11 map observer did not attach before {app} launch")
    started = time.perf_counter_ns()
    # Cocoa and X11 watchers timestamp CLOCK_MONOTONIC; use that same clock domain for map deltas.
    mapped_started = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    debug_log = (profile / "startup-app.log").open("wb") if os.environ.get("CRAFT_STARTUP_DEBUG") == "1" else None
    proc = subprocess.Popen(command, cwd=profile, env=env, stdout=debug_log or subprocess.DEVNULL, stderr=debug_log or subprocess.DEVNULL)
    if sys.platform == "darwin" and map_watch is not None:
        mac_pid_path.write_text(f"{proc.pid}\n")
    try:
        deadline = time.monotonic() + timeout_s
        if app in MAP_ONLY_APPS:
            while time.monotonic() < deadline and not mapped_at_path.is_file():
                if proc.poll() is not None:
                    raise RuntimeError(f"{app} exited before its window mapped (status {proc.returncode})")
                time.sleep(0.001)
            if not mapped_at_path.is_file():
                raise TimeoutError(f"{app} window did not map")
            elapsed = int(mapped_at_path.read_text().strip()) - mapped_started
            print(f"CRAFT_WINDOW_MAPPED_NS={elapsed}", flush=True)
            write_timing_diagnostic(
                profile,
                window_mapped_ns=elapsed,
                library_ready_ns=None,
                screenshot_complete_ns=None,
                screenshot_rpc_ns=None,
            )
            return elapsed
        if app == "pdfcraft":
            while time.monotonic() < deadline and not control_file.exists():
                if proc.poll() is not None:
                    raise RuntimeError(f"{app} exited before publishing its control endpoint (status {proc.returncode})")
                time.sleep(0.01)
            endpoint = json.loads(control_file.read_text())
            port, token = int(endpoint["port"]), str(endpoint["token"])
        elif app == "wordcraft":
            token_deadline = min(deadline, time.monotonic() + 5)
            while time.monotonic() < token_deadline and not token_file.is_file():
                if proc.poll() is not None:
                    raise RuntimeError(f"{app} exited before publishing its control key (status {proc.returncode})")
                time.sleep(0.01)
            if not token_file.is_file():
                raise TimeoutError(f"{app} did not publish its control key")
            token = token_file.read_text().strip()
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
                if app == "wordcraft":
                    rpc(candidate, "auth", {}, 0, token, "key")
                elif app not in {"cadcraft", "deckcraft", "lightcraft", "vectorcraft", "effectcraft"}:
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
            if app == "lightcraft":
                # The selected photo is the first useful content in this app: wait until the
                # image imported from the representative payload is visible before starting the
                # first-frame clock. This is still a UI-thread request, like the screenshot below.
                ready = False
                while time.monotonic() < deadline:
                    try:
                        photo = rpc(stream, "engine.execute", {"command": "photo.inspect"}, 1)
                    except RuntimeError as error:
                        # Launch imports are asynchronous after the first frame. Until the
                        # selected photo is indexed, photo.inspect reports "no photo"; keep
                        # polling instead of rejecting an otherwise successful startup.
                        if "photo.inspect" not in str(error) or "no photo" not in str(error):
                            raise
                        time.sleep(0.02)
                        continue
                    result = photo.get("result")
                    if isinstance(result, dict) and result.get("id") is not None:
                        ready = True
                        break
                    time.sleep(0.02)
                if not ready:
                    raise TimeoutError("LightCraft did not activate the imported photo")
                elapsed = time.perf_counter_ns() - started
                frame_path = profile / "first-frame.png"
                frame_path.unlink(missing_ok=True)
                capture_started = time.perf_counter_ns()
                frame = rpc(stream, "ui.screenshot", {"path": str(frame_path)}, 2)
                screenshot_rpc_elapsed = time.perf_counter_ns() - capture_started
                screenshot_elapsed = time.perf_counter_ns() - started
                if not screenshot_ok(frame, frame_path):
                    raise RuntimeError("LightCraft screenshot reply did not contain a rendered PNG")
                if map_watch is not None:
                    map_deadline = time.monotonic() + 1
                    while not mapped_at_path.is_file() and map_watch.poll() is None and time.monotonic() < map_deadline:
                        time.sleep(0.001)
                    if not mapped_at_path.is_file():
                        raise RuntimeError("LightCraft returned a screenshot before its X11 window was mapped")
                    mapped_ns = int(mapped_at_path.read_text().strip())
                    mapped_elapsed = mapped_ns - mapped_started
                    print(f"CRAFT_WINDOW_MAPPED_NS={mapped_elapsed}", flush=True)
                    print(f"CRAFT_CONTENT_READY_NS={elapsed}", flush=True)
                    print(f"CRAFT_SCREENSHOT_NS={screenshot_elapsed}", flush=True)
                    print(f"CRAFT_SCREENSHOT_RPC_NS={screenshot_rpc_elapsed}", flush=True)
                    write_timing_diagnostic(
                        profile,
                        **{
                            "window_mapped_ns": mapped_elapsed,
                            "library_ready_ns": elapsed,
                            "screenshot_complete_ns": screenshot_elapsed,
                            "screenshot_rpc_ns": screenshot_rpc_elapsed,
                        },
                    )
                    elapsed = mapped_elapsed
                rpc(stream, "ui.inspect", {}, 3)
                try:
                    rpc(stream, "engine.execute", {"command": "app.quit"}, 4)
                except Exception:
                    pass
                return elapsed
            secret_field = "key" if app == "wordcraft" else "token"
            secret = token if app in {"cadcraft", "wordcraft"} else None
            content_ready_elapsed = None
            if app == "effectcraft":
                project_ready = False
                while time.monotonic() < deadline:
                    try:
                        summary = rpc(stream, "engine.execute", {"command": "project.summary", "params": {}}, 1).get("result")
                    except RuntimeError:
                        time.sleep(0.02)
                        continue
                    items = summary.get("items", []) if isinstance(summary, dict) else []
                    project_ready = any(
                        item.get("name") == "Typical 1080p" and item.get("layers") == 30 and item.get("size") == [1920, 1080]
                        for item in items if isinstance(item, dict)
                    )
                    if project_ready:
                        content_ready_elapsed = time.perf_counter_ns() - started
                        break
                    time.sleep(0.02)
                if not project_ready:
                    raise TimeoutError("EffectCraft did not load the pinned 1080p project")
            screenshot_path = profile / "first-frame.png" if app in {"vectorcraft", "effectcraft"} else None
            capture_started = time.perf_counter_ns()
            if screenshot_path is not None:
                screenshot_path.unlink(missing_ok=True)
                request_id = 2 if app == "effectcraft" else 1
                while True:
                    try:
                        frame = rpc(stream, "ui.screenshot", {"path": str(screenshot_path)}, request_id, secret, secret_field)
                    except RuntimeError as error:
                        if app != "effectcraft" or not any(
                            message in str(error) for message in ("window geometry is not known yet", "no frame was presented")
                        ):
                            raise
                        screenshot_error = str(error)
                    else:
                        if screenshot_ok(frame, screenshot_path):
                            break
                        raise RuntimeError(f"{app} screenshot reply did not contain a rendered PNG")
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"EffectCraft did not produce its first frame: {screenshot_error}")
                    request_id += 1
                    time.sleep(0.02)
            else:
                frame = rpc(stream, "ui.screenshot", {}, 1, secret, secret_field)
            screenshot_rpc_elapsed = time.perf_counter_ns() - capture_started
            screenshot_elapsed = time.perf_counter_ns() - started
            print(f"CRAFT_SCREENSHOT_RPC_NS={screenshot_rpc_elapsed}", flush=True)
            if content_ready_elapsed is not None:
                print(f"CRAFT_CONTENT_READY_NS={content_ready_elapsed}", flush=True)
            if screenshot_path is None and not screenshot_ok(frame, None):
                raise RuntimeError(f"{app} screenshot reply did not contain a rendered PNG")
            elapsed = screenshot_elapsed
            if map_watch is not None:
                map_deadline = time.monotonic() + 1
                while not mapped_at_path.is_file() and map_watch.poll() is None and time.monotonic() < map_deadline:
                    time.sleep(0.001)
                if not mapped_at_path.is_file():
                    raise RuntimeError(f"{app} returned a screenshot before its X11 window was mapped")
                mapped_ns = int(mapped_at_path.read_text().strip())
                elapsed = mapped_ns - mapped_started
                print(f"CRAFT_WINDOW_MAPPED_NS={elapsed}", flush=True)
                print(f"CRAFT_SCREENSHOT_NS={screenshot_elapsed}", flush=True)
            write_timing_diagnostic(
                profile,
                window_mapped_ns=elapsed if map_watch is not None else None,
                library_ready_ns=content_ready_elapsed,
                screenshot_complete_ns=screenshot_elapsed,
                screenshot_rpc_ns=screenshot_rpc_elapsed,
            )
            # The frame capture runs on the UI thread; a subsequent inspection confirms the
            # window is accepting control requests. Its latency is deliberately outside the mark.
            inspect_id = request_id + 1 if screenshot_path is not None else 2
            rpc(stream, "ui.inspect" if app != "pdfcraft" else "ui.state", {}, inspect_id, secret, secret_field)
            quit_id = inspect_id + 1
            try:
                rpc(stream, "app.quit" if app != "pdfcraft" else "ui.quit", {}, quit_id, secret, secret_field)
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
        if map_watch is not None:
            if map_watch.poll() is None:
                map_watch.terminate()
            map_watch.wait(timeout=2)


def main() -> int:
    if len(sys.argv) not in {5, 6}:
        print("usage: desktop_startup.py APP BINARY cold|warm PROFILE [INPUT]", file=sys.stderr)
        return 2
    app, binary_text, mode, profile_text = sys.argv[1:5]
    input_path = Path(sys.argv[5]).resolve() if len(sys.argv) == 6 else None
    if app not in {"photocraft", "pdfcraft", "gridcraft", "cadcraft", "wordcraft", "deckcraft", "lightcraft", "vectorcraft", "effectcraft", "figcraft", "materialcraft", "designcraft", "soundcraft", "filmcraft"} or mode not in {"cold", "warm"}:
        print("invalid app or mode", file=sys.stderr)
        return 2
    binary, profile = Path(binary_text).resolve(), Path(profile_text).resolve()
    if not binary.is_file():
        print(f"app binary not found: {binary}", file=sys.stderr)
        return 2
    display = ensure_display()
    try:
        library_path = None
        if app == "lightcraft":
            if input_path is None or not input_path.is_file():
                raise RuntimeError("LightCraft startup requires an existing photo payload")
            library_path = profile.parent / "lightcraft-library"
            ready_marker = profile.parent / "lightcraft-library.ready"
            if not ready_marker.exists():
                seed_profile = profile.parent / "lightcraft-seed-profile"
                shutil.rmtree(seed_profile, ignore_errors=True)
                launch(app, binary, seed_profile, input_path=input_path, library_path=library_path)
                ready_marker.touch()
        if mode == "cold":
            shutil.rmtree(profile, ignore_errors=True)
        elif not (profile / ".startup-seeded").exists():
            launch(app, binary, profile, input_path=input_path, library_path=library_path)
            (profile / ".startup-seeded").touch()
        elapsed = launch(app, binary, profile, input_path=input_path, library_path=library_path)
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
