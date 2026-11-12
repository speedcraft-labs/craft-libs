#!/usr/bin/env python3
"""Run one paired, persistent-process PhotoCraft latency acquisition."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Any


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fnv1a64(data: bytes) -> str:
    value = 0xCBF29CE484222325
    for byte in data:
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def capture_canvas(path: Path, ui: dict[str, Any], control: Control) -> dict[str, Any]:
    """Capture PhotoCraft's next rendered screenshot and crop the same canvas region."""
    control.rpc("ui.screenshot", {"path": str(path), "focus": False})
    from PIL import Image
    image = Image.open(path).convert("RGB")
    x, y, w, h = (int(v) for v in ui["canvas"])
    window = ui["window"]
    scale_x = image.width / float(window["width"])
    scale_y = image.height / float(window["height"])
    x, y, w, h = (round(v * scale) for v, scale in ((x, scale_x), (y, scale_y), (w, scale_x), (h, scale_y)))
    # The stroke path crosses the centre. Keep this crop away from the brush cursor at its end.
    cx, cy = x + w // 2, y + h // 2
    radius = min(180, w // 2, h // 2)
    crop = image.crop((cx - radius, cy - radius, cx + radius, cy + radius))
    return {"image": image, "crop": crop, "crop_box": [cx - radius, cy - radius, cx + radius, cy + radius],
            "crop_sha256": hashlib.sha256(crop.tobytes()).hexdigest(), "crop_fnv1a64": fnv1a64(crop.tobytes()), "path": str(path)}


def pixel_proof(before: dict[str, Any], immediate: dict[str, Any], settled: dict[str, Any], recorded_frame_hash: str | None = None) -> dict[str, Any]:
    from PIL import ImageChops
    base = before["crop"].getdata()
    now = immediate["crop"].getdata()
    later = settled["crop"].getdata()
    changed_now = sum(any(abs(a - b) > 2 for a, b in zip(p, q)) for p, q in zip(base, now))
    changed_later = sum(any(abs(a - b) > 2 for a, b in zip(p, q)) for p, q in zip(base, later))
    settled_diff = ImageChops.difference(immediate["crop"], settled["crop"])
    stable_pixels = sum(max(p) <= 2 for p in settled_diff.getdata())
    total = immediate["crop"].width * immediate["crop"].height
    return {
        "roi": immediate["crop_box"],
        "before_sha256": before["crop_sha256"],
        "immediate_sha256": immediate["crop_sha256"],
        "settled_sha256": settled["crop_sha256"],
        "recorded_frame_hash": recorded_frame_hash,
        "recorded_frame_matches_immediate": recorded_frame_hash == immediate["crop_fnv1a64"] if recorded_frame_hash else None,
        "recorded_frame_matches_settled": recorded_frame_hash == settled["crop_fnv1a64"] if recorded_frame_hash else None,
        "changed_pixels_immediate": changed_now,
        "changed_pixels_settled": changed_later,
        "immediate_settled_mae": sum(sum(p) for p in settled_diff.getdata()) / (total * 3),
        "immediate_settled_stable_pct": 100 * stable_pixels / total,
        "pixel_capture_boundary": "viewport screenshot callback requested in the same UI pass as the latency endpoint; follow-up app screenshots checked after completion and 1000ms later",
    }


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Control:
    def __init__(self, sock: socket.socket, token: str):
        self.sock = sock
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(610)
        self.reader = sock.makefile("rb")
        self.token = token
        self.ident = 0
        self.rpc("auth", {}, auth=True)

    def rpc(self, method: str, params: dict[str, Any] | None = None, *, auth: bool = False) -> Any:
        self.ident += 1
        request: dict[str, Any] = {"id": self.ident, "method": method, "params": params or {}}
        if auth:
            request["params"] = {"token": self.token}
        self.sock.sendall((json.dumps(request, separators=(",", ":")) + "\n").encode())
        line = self.reader.readline()
        if not line:
            raise RuntimeError(f"PhotoCraft control closed during {method}")
        reply = json.loads(line)
        if reply.get("id") != self.ident:
            raise RuntimeError(f"control id mismatch during {method}: {reply}")
        if not reply.get("ok"):
            raise RuntimeError(f"PhotoCraft {method}: {reply.get('error', reply)}")
        return reply.get("result")

    def arm(self, action: str, ident: str) -> None:
        self.rpc("ui.latency.arm", {"action": action, "id": ident})

    def input(self, events: list[dict[str, Any]], *, complete: bool = True) -> None:
        self.rpc("ui.latency.input", {"events": events, "complete": complete})

    def result(self, ident: str) -> dict[str, Any]:
        return self.rpc("ui.latency.wait", {"id": ident})


class GpuWatch:
    def __init__(self, own_pid: int):
        self.own_pid = own_pid
        self.samples: list[dict[str, Any]] = []
        self.failed: str | None = None
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._poll, name="photocraft-gpu-watch", daemon=True)

    def snapshot(self) -> dict[str, Any]:
        query = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_gpu_memory", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=False,
        )
        if query.returncode:
            raise RuntimeError(f"nvidia-smi query failed: {query.stderr.strip()}")
        processes = []
        for line in query.stdout.splitlines():
            columns = [column.strip() for column in line.split(",", 2)]
            if len(columns) != 3 or columns[0] in {"", "-"}:
                continue
            processes.append({"pid": int(columns[0]), "name": columns[1], "used_gpu_memory_mib": columns[2]})
        clocks = subprocess.run(
            ["nvidia-smi", "--query-gpu=clocks.gr,clocks.mem", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=False,
        )
        if clocks.returncode:
            raise RuntimeError(f"nvidia-smi clock query failed: {clocks.stderr.strip()}")
        clock_values = [x.strip() for x in clocks.stdout.splitlines()[0].split(",")]
        return {
            "observed_ns": time.time_ns(),
            "processes": processes,
            "graphics_mhz": float(clock_values[0]),
            "memory_mhz": float(clock_values[1]),
        }

    def _poll(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.samples.append(self.snapshot())
            except Exception as error:  # retained in the report; never silently ignore a failed probe
                self.failed = str(error)
            self.stop_event.wait(2.0)

    def start(self) -> None:
        self.thread.start()

    def finish(self) -> dict[str, Any]:
        self.stop_event.set()
        self.thread.join(timeout=5)
        foreign = []
        for sample in self.samples:
            for process in sample["processes"]:
                if process["pid"] != self.own_pid and process["name"].rsplit("/", 1)[-1] not in {"Xorg", "X", "Xwayland"}:
                    foreign.append(process)
        return {"samples": self.samples, "foreign_processes": foreign, "probe_error": self.failed}


def check_ok(reply: Any, method: str) -> Any:
    if isinstance(reply, dict) and reply.get("error"):
        raise RuntimeError(f"{method}: {reply['error']}")
    return reply


def spawn_side(side: dict[str, Any], work: dict[str, Any], config: dict[str, Any], out: Path) -> dict[str, Any]:
    binary = Path(side["binary"]).resolve()
    payload = Path(config["payload"]["path"]).resolve()
    if digest(binary) != side["binary_sha256"]:
        raise ValueError(f"binary hash mismatch for {side['name']}")
    if digest(payload) != config["payload"]["sha256"]:
        raise ValueError(f"payload hash mismatch for {config['tier']}")

    profile = out / side["name"] / "profile"
    shutil.rmtree(profile.parent, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    session_input = profile / payload.name
    shutil.copyfile(payload, session_input)
    port = free_port()
    token = secrets.token_hex(32)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(profile),
            "XDG_CONFIG_HOME": str(profile / ".config"),
            "XDG_DATA_HOME": str(profile / ".local/share"),
            "XDG_CACHE_HOME": str(profile / ".cache"),
            "PHOTOCRAFT_LATENCY_RECORDER": "1",
            "WGPU_BACKEND": config.get("wgpu_backend", "vulkan"),
            "LANG": "C.UTF-8",
        }
    )
    for key in ("PHOTOCRAFT_LATENCY_SLOW_ACTION", "PHOTOCRAFT_LATENCY_SLOW_MS"):
        if key in side:
            env[key] = str(side[key])
        else:
            env.pop(key, None)
    if config.get("pixel_proof"):
        env["PHOTOCRAFT_LATENCY_FRAME_CAPTURE"] = "1"
    else:
        env.pop("PHOTOCRAFT_LATENCY_FRAME_CAPTURE", None)
    log_path = out / side["name"] / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log:
        gpu_before = GpuWatch(-1).snapshot()
        process = subprocess.Popen(
            [
                str(binary),
                "--control",
                str(port),
                "--control-token",
                token,
                "--automation-read-root",
                str(profile),
                "--automation-write-root",
                str(profile),
            ],
            cwd=profile,
            env=env,
            stdout=log,
            stderr=log,
        )
    watch = GpuWatch(process.pid)
    watch.start()
    control = None
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"PhotoCraft exited during startup ({process.returncode}); see {log_path}")
        try:
            control = Control(socket.create_connection(("127.0.0.1", port), timeout=0.25), token)
            break
        except OSError:
            time.sleep(0.02)
    if control is None:
        process.terminate()
        process.wait(timeout=5)
        raise TimeoutError("PhotoCraft control channel did not start")

    records: list[dict[str, Any]] = []
    saved_files: dict[str, dict[str, Any]] = {}
    clock_observations: list[dict[str, Any]] = []
    sequence = 0
    identity = {
        "tier": config["tier"],
        "payload_sha256": config["payload"]["sha256"],
        "revision": side["revision"],
        "side": side["name"],
        "side_role": side["role"],
        "slow_delay_ms": int(side.get("PHOTOCRAFT_LATENCY_SLOW_MS", 0)),
    }

    def arm(action: str, label: str, phase: str) -> str:
        nonlocal sequence
        clock = watch.snapshot()
        clock["phase"] = f"before-{label}-{phase}"
        clock_observations.append(clock)
        sequence += 1
        ident = f"{config['acquisition']}-{config['pair']}-{side['name']}-{label}-{sequence}"
        control.arm(action, ident)
        return ident

    def record(action: str, label: str, phase: str, ident: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        raw = control.result(ident)
        result = {"action": action, "label": label, "phase": phase, "id": ident, **raw}
        if extra:
            result.update(extra)
        records.append(result)
        return result

    def send(events: list[dict[str, Any]], *, complete: bool = True) -> None:
        # Preserve the event order in one ordinary app input-queue batch. A real desktop can
        # deliver many pointer events together while a slow frame is being prepared; PhotoCraft
        # records each event's UI-thread acceptance time and the first frame that reflects the
        # batch. This keeps the full stroke on the normal widget/canvas/brush path without waiting
        # for an extra GPU composite after every synthetic point.
        control.input(events, complete=complete)

    def measure_command(action: str, label: str, phase: str, method: str, params: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
        ident = arm(action, label, phase)
        control.rpc(method, params)
        return record(action, label, phase, ident, extra)

    try:
        check_ok(control.rpc("ui.resize", config["ui"]["window"]), "ui.resize")
        startup = control.rpc("ui.inspect", {})
        if isinstance(startup, dict) and startup.get("updatesOpen"):
            if config.get("capture_update_notice"):
                capture_path = profile / "update-notice.png"
                control.rpc("ui.screenshot", {"path": str(capture_path), "focus": False})
                archived = out / "update-notice.png"
                shutil.copyfile(capture_path, archived)
                identity["update_notice_capture"] = str(archived)
                capture_path.unlink()
            later_x, later_y = config["ui"].get("update_later", [818, 551])
            control.rpc("ui.click", {"x": later_x, "y": later_y})
            startup = control.rpc("ui.inspect", {})
            if isinstance(startup, dict) and startup.get("updatesOpen"):
                raise RuntimeError("PhotoCraft update notice remained open after dismissing it")
        open_samples = []
        for repetition in range(1 if config.get("smoke") else 4):
            if repetition:
                control.rpc("ui.key", {"key": "W", "ctrl": True})
            phase = "cold" if repetition == 0 else "warm"
            open_samples.append(measure_command("open", "open-first-composite", phase, "app.open", {"path": session_input.name}))
            if repetition == 0:
                first_state = control.rpc("ui.inspect", {})
                identity["first_document_inspect"] = first_state
                if not isinstance(first_state, dict) or not first_state.get("document"):
                    raise RuntimeError("PhotoCraft did not open the pinned layered payload")
                identity["update_notice_after_open"] = bool(first_state.get("updatesOpen"))
                if first_state.get("updatesOpen"):
                    if config.get("capture_update_notice"):
                        capture_path = profile / "update-notice-after-open.png"
                        control.rpc("ui.screenshot", {"path": str(capture_path), "focus": False})
                        archived = out / "update-notice-after-open.png"
                        shutil.copyfile(capture_path, archived)
                        identity["update_notice_capture"] = str(archived)
                        capture_path.unlink()
                    later_x, later_y = config["ui"].get("update_later", [818, 551])
                    for _ in range(3):
                        control.rpc("ui.click", {"x": later_x, "y": later_y})
                        first_state = control.rpc("ui.inspect", {})
                        if not first_state.get("updatesOpen"):
                            break
                    if first_state.get("updatesOpen"):
                        raise RuntimeError("PhotoCraft update notice remained open after three dismiss clicks")
                selected = [layer for layer in first_state["document"].get("layers", []) if layer.get("selected")]
                width, height = config["payload"]["dimensions"]
                if len(selected) != 1 or selected[0].get("bounds", [0, 0, 0, 0])[2:] != [width, height]:
                    raise RuntimeError("PhotoCraft did not select the full-canvas layer used for brush and move actions")
        if config.get("smoke"):
            smoke_image = None
            if config.get("smoke_capture"):
                screenshot = profile / "smoke.png"
                control.rpc("ui.screenshot", {"path": str(screenshot)})
                header = screenshot.read_bytes()[:24]
                if len(header) != 24 or not header.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise RuntimeError("PhotoCraft smoke capture is not a PNG")
                smoke_image = {"dimensions": [int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")], "sha256": digest(screenshot)}
                if config.get("smoke_capture_copy"):
                    shutil.copyfile(screenshot, Path(config["smoke_capture_copy"]))
                screenshot.unlink()
            blend_menu_image = None
            if config.get("smoke_menu_capture_copy"):
                blend_x, blend_y = config["ui"]["blend_dropdown"]
                control.rpc("ui.click", {"x": blend_x, "y": blend_y})
                menu_screenshot = profile / "blend-menu.png"
                control.rpc("ui.screenshot", {"path": str(menu_screenshot)})
                header = menu_screenshot.read_bytes()[:24]
                if len(header) != 24 or not header.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise RuntimeError("PhotoCraft blend-menu smoke capture is not a PNG")
                blend_menu_image = {"dimensions": [int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")], "sha256": digest(menu_screenshot)}
                shutil.copyfile(menu_screenshot, Path(config["smoke_menu_capture_copy"]))
                menu_screenshot.unlink()
            state = control.rpc("ui.inspect", {})
            identity["gpu"] = state.get("perf") if isinstance(state, dict) else None
            identity["document"] = state.get("document") if isinstance(state, dict) else None
            identity["window"] = state.get("window") if isinstance(state, dict) else None
            quit_request_ns = time.time_ns()
            try:
                control.rpc("app.quit", {})
            except Exception:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
            gpu = watch.finish()
            gpu_after = GpuWatch(-1).snapshot()
            expected_clock = config.get("gpu_state", {})
            clocks = [gpu_before, *clock_observations, *gpu["samples"], gpu_after]
            clocks_passed = not expected_clock or all(
                abs(sample["graphics_mhz"] - float(expected_clock["graphics_mhz"])) <= 15
                and abs(sample["memory_mhz"] - float(expected_clock["memory_mhz"])) <= 5
                for sample in clocks
            )
            foreign = list(gpu["foreign_processes"])
            for sample in [gpu_before, *clock_observations, gpu_after]:
                foreign.extend(
                    process_info
                    for process_info in sample["processes"]
                    if process_info["pid"] not in {process.pid, -1}
                    and process_info["name"].rsplit("/", 1)[-1] not in {"Xorg", "X", "Xwayland"}
                )
            gpu["before"] = gpu_before
            gpu["after"] = gpu_after
            gpu["clock_observations"] = clock_observations
            gpu["foreign_processes"] = foreign
            gpu["clock_state_passed"] = clocks_passed
            result = {
                **identity,
                "pair": config["pair"],
                "acquisition": config["acquisition"],
                "process_pid": process.pid,
                "process_exit_code": process.returncode,
                "quit_request_ns": quit_request_ns,
                "gpu_watch": gpu,
                "gpu_process_checks_passed": not gpu["foreign_processes"] and not gpu["probe_error"],
                "gpu_state_passed": clocks_passed,
                "samples": records,
                "profile_removed": True,
                "log": str(log_path),
                "open_samples": open_samples,
                "smoke_capture": smoke_image,
                "smoke_blend_menu_capture": blend_menu_image,
                "document_opened": bool(state.get("document")) if isinstance(state, dict) else False,
            }
            shutil.rmtree(profile, ignore_errors=True)
            return result
        opened = control.rpc("ui.inspect", {})
        identity["document"] = opened.get("document") if isinstance(opened, dict) else None
        identity["window"] = opened.get("window") if isinstance(opened, dict) else None
        identity["gpu"] = opened.get("perf") if isinstance(opened, dict) else None
        ui = config["ui"]
        canvas = ui["canvas"]
        center_x = canvas[0] + canvas[2] * 0.50
        center_y = canvas[1] + canvas[3] * 0.50

        def selected_target(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            document = state.get("document") or {}
            targets = [layer for layer in document.get("layers", []) if layer.get("name", "").startswith("Large move target")]
            if len(targets) != 1 or not targets[0].get("selected"):
                raise RuntimeError("the full-canvas NASA layer is not the unique selected target")
            return document, targets[0]

        # The currently selected top raster layer is the full-canvas move/brush target.
        control.rpc("ui.set", {"tool": "brush"})
        small_brush = int(ui.get("small_brush_px", 30))
        large_brush = int(ui.get("large_brush_px", 500))
        canvas_brush = min(int(config["payload"]["dimensions"][0]), 5000)
        for label, size in (("brush-30px", small_brush), ("brush-500px-soft", large_brush), ("brush-canvas-width-soft", canvas_brush)):
            control.rpc("engine.execute", {"command": "tools.setBrush", "params": {"brush": {"size": size, "hardness": 0.12, "opacity": 1.0, "smoothing": {"amount": 0.0}}}})
            npoints = 200
            path = [
                (
                    canvas[0] + canvas[2] * (0.25 + 0.50 * i / (npoints - 1)),
                    center_y + math.sin(i / (npoints - 1) * 2 * math.pi) * min(canvas[3] * 0.18, 70),
                )
                for i in range(npoints)
            ]
            send([{"kind": "move", "x": path[0][0], "y": path[0][1]}])
            for repetition in range(4):
                phase = "cold" if repetition == 0 else "warm"
                before_state = control.rpc("ui.inspect", {})
                before_document, _ = selected_target(before_state)
                before_history_count = len(before_document.get("history", []))
                pixels_before = None
                if config.get("pixel_proof") and repetition == 0:
                    capture_path = profile / f"{label}-before.png"
                    pixels_before = capture_canvas(capture_path, ui, control)
                    archived = out / capture_path.name
                    shutil.copyfile(capture_path, archived)
                    pixels_before["path"] = str(archived)
                ident = arm("brush", label, phase)
                send([{"kind": "down", "x": path[0][0], "y": path[0][1]}])
                send([{"kind": "move", "x": x, "y": y} for x, y in path[1:]])
                send([{"kind": "up", "x": path[-1][0], "y": path[-1][1]}])
                raw = control.result(ident)
                if config.get("pixel_proof"):
                    capture_deadline = time.monotonic() + 2.0
                    while raw.get("frame_pixel_hash") is None and time.monotonic() < capture_deadline:
                        time.sleep(0.01)
                        raw = control.result(ident)
                    if raw.get("frame_pixel_hash") is None:
                        raise RuntimeError(f"{label} latency frame screenshot did not complete")
                proof = None
                if pixels_before is not None:
                    capture_path = profile / f"{label}-immediate.png"
                    pixels_now = capture_canvas(capture_path, ui, control)
                    archived = out / capture_path.name
                    shutil.copyfile(capture_path, archived)
                    pixels_now["path"] = str(archived)
                    time.sleep(1.0)
                    capture_path = profile / f"{label}-settled.png"
                    pixels_settled = capture_canvas(capture_path, ui, control)
                    archived = out / capture_path.name
                    shutil.copyfile(capture_path, archived)
                    pixels_settled["path"] = str(archived)
                    proof = pixel_proof(pixels_before, pixels_now, pixels_settled, raw.get("frame_pixel_hash"))
                    proof["files"] = [pixels_before["path"], pixels_now["path"], pixels_settled["path"]]
                point_latencies = [sample["duration_ns"] for sample in raw["input_samples"] if sample["kind"] in {"down", "move"}]
                if len(point_latencies) != npoints:
                    raise RuntimeError(f"{label} recorded {len(point_latencies)} accepted points, expected {npoints}")
                records.append({"action": "brush", "label": label, "phase": phase, "id": ident, **raw,
                                "point_count": npoints, "brush_size_px": size, "point_latencies_ns": point_latencies,
                                "pixel_proof": proof})
                after_document, _ = selected_target(control.rpc("ui.inspect", {}))
                if len(after_document.get("history", [])) <= before_history_count:
                    raise RuntimeError(f"{label} input was timed but did not commit a brush stroke")

        if not config.get("brush_only"):
                # Layer eye and blend coordinates are calibrated once for the fixed 1600×1000 layout.
            eye_x, eye_y = ui["visibility_eye"]
            blend_x, blend_y = ui["blend_dropdown"]
            mode_points = ui["blend_options"]
            for repetition in range(4):
                phase = "cold" if repetition == 0 else "warm"
                send([{"kind": "move", "x": eye_x, "y": eye_y}])
                _, before_layer = selected_target(control.rpc("ui.inspect", {}))
                expected_visibility = not before_layer["visible"]
                ident = arm("visibility", "large-layer-visibility", phase)
                send([{"kind": "down", "x": eye_x, "y": eye_y}, {"kind": "up", "x": eye_x, "y": eye_y}])
                record("visibility", "large-layer-visibility", phase, ident)
                _, after_layer = selected_target(control.rpc("ui.inspect", {}))
                if after_layer["visible"] is not expected_visibility:
                    raise RuntimeError("PhotoCraft did not toggle the selected layer visibility")

            for repetition in range(4):
                phase = "cold" if repetition == 0 else "warm"
                send([{"kind": "move", "x": blend_x, "y": blend_y}])
                ident = arm("blend", "large-layer-blend-mode", phase)
                send([{"kind": "down", "x": blend_x, "y": blend_y}, {"kind": "up", "x": blend_x, "y": blend_y}], complete=False)
                option = "multiply" if repetition % 2 == 0 else "normal"
                option_x, option_y = mode_points[option]
                send([
                    {"kind": "move", "x": option_x, "y": option_y},
                    {"kind": "down", "x": option_x, "y": option_y},
                    {"kind": "up", "x": option_x, "y": option_y},
                ], complete=True)
                record("blend", "large-layer-blend-mode", phase, ident, {"selected_mode": option})
                _, after_layer = selected_target(control.rpc("ui.inspect", {}))
                if after_layer["blend"] != ("Multiply" if option == "multiply" else "Normal"):
                    raise RuntimeError(f"PhotoCraft did not apply the {option} blend mode")

            move_tool = ui.get("move_tool_name", "Move")
            control.rpc("ui.set", {"tool": move_tool})
            move_state = control.rpc("ui.inspect", {})
            if move_state.get("toolOptions", {}).get("move_auto_select", False):
                auto_x, auto_y = ui["move_auto_select"]
                control.rpc("ui.click", {"x": auto_x, "y": auto_y})
                move_state = control.rpc("ui.inspect", {})
            if move_state.get("toolOptions", {}).get("move_auto_select") is not False:
                raise RuntimeError("PhotoCraft Move Auto-Select could not be disabled for the selected large-layer drag")
            identity["move_auto_select_disabled"] = True
            for action, button, label in (("move", "left", "large-layer-move-60-step"), ("pan", "middle", "canvas-pan-60-step")):
                for repetition in range(4):
                    phase = "cold" if repetition == 0 else "warm"
                    direction = 1 if repetition % 2 == 0 else -1
                    start = (center_x - direction * 90, center_y)
                    path = [(start[0] + direction * 180 * i / 60, start[1] + math.sin(i / 60 * math.pi) * 24) for i in range(61)]
                    send([{"kind": "move", "x": start[0], "y": start[1]}])
                    before_state = control.rpc("ui.inspect", {})
                    before_document, before_layer = selected_target(before_state)
                    before_bounds = before_layer["bounds"]
                    before_view = before_state.get("views", [{}])[0]
                    ident = arm(action, label, phase)
                    send([{"kind": "down", "x": path[0][0], "y": path[0][1], "button": button}])
                    send([{"kind": "move", "x": x, "y": y} for x, y in path[1:]])
                    send([{"kind": "up", "x": path[-1][0], "y": path[-1][1], "button": button}])
                    raw = control.result(ident)
                    records.append({"action": action, "label": label, "phase": phase, "id": ident, **raw,
                                    "step_count": 60, "step_latencies_ns": [s["duration_ns"] for s in raw["input_samples"] if s["kind"] == "move"]})
                    after_state = control.rpc("ui.inspect", {})
                    after_document, after_layer = selected_target(after_state)
                    if action == "move" and after_layer["bounds"] == before_bounds:
                        raise RuntimeError("PhotoCraft Move tool did not move the selected large layer")
                    if action == "pan":
                        after_view = after_state.get("views", [{}])[0]
                        old_center = before_view.get("center", [0.0, 0.0])
                        new_center = after_view.get("center", [0.0, 0.0])
                        if math.dist(old_center, new_center) < 50:
                            raise RuntimeError("PhotoCraft canvas pan did not change the view center")

            for repetition in range(20):
                phase = "cold" if repetition == 0 else "warm"
                ident = arm("zoom", "canvas-zoom-wheel-step", phase)
                send([{"kind": "wheel", "deltaY": 120 if repetition % 2 == 0 else -120}])
                record("zoom", "canvas-zoom-wheel-step", phase, ident, {"step_count": 1})

            for repetition in range(4):
                output_name = f"save-output-{repetition + 1}"
                phase = "cold" if repetition == 0 else "warm"
                measure_command("save", "save-psd", phase, "app.save", {"path": f"{output_name}.psd"}, {"save_output": output_name})
                output_path = profile / f"{output_name}.psd"
                if not output_path.is_file() or output_path.stat().st_size == 0:
                    raise RuntimeError(f"PhotoCraft save did not produce {output_path.name}")
                saved_files[output_path.name] = {"sha256": digest(output_path), "bytes": output_path.stat().st_size}
                output_path.unlink()

        state_after = control.rpc("ui.inspect", {})
        identity["final_document_inspect"] = state_after
        quit_request_ns = time.time_ns()
        try:
            control.rpc("app.quit", {})
        except Exception:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        gpu = watch.finish()
        gpu_after = GpuWatch(-1).snapshot()
        expected_clock = config.get("gpu_state", {})
        relevant_clocks = [gpu_before, *clock_observations, *gpu["samples"], gpu_after]
        clocks_passed = not expected_clock or all(
            abs(sample["graphics_mhz"] - float(expected_clock["graphics_mhz"])) <= 15
            and abs(sample["memory_mhz"] - float(expected_clock["memory_mhz"])) <= 5
            for sample in relevant_clocks
        )
        foreign = list(gpu["foreign_processes"])
        for sample in [gpu_before, *clock_observations, gpu_after]:
            foreign.extend(
                process_info
                for process_info in sample["processes"]
                if process_info["pid"] not in {process.pid, -1}
                and process_info["name"].rsplit("/", 1)[-1] not in {"Xorg", "X", "Xwayland"}
            )
        gpu["before"] = gpu_before
        gpu["after"] = gpu_after
        gpu["clock_observations"] = clock_observations
        gpu["foreign_processes"] = foreign
        gpu["clock_state_passed"] = clocks_passed
        result = {
            **identity,
            "pair": config["pair"],
            "acquisition": config["acquisition"],
            "process_pid": process.pid,
            "process_exit_code": process.returncode,
            "quit_request_ns": quit_request_ns,
            "gpu_watch": gpu,
            "gpu_process_checks_passed": not gpu["foreign_processes"] and not gpu["probe_error"],
            "gpu_state_passed": clocks_passed,
            "samples": records,
            "profile_removed": True,
            "log": str(log_path),
            "open_samples": open_samples,
            "saved_files": saved_files,
        }
        shutil.rmtree(profile, ignore_errors=True)
        return result
    except Exception:
        try:
            control.rpc("app.quit", {})
        except Exception:
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        watch.finish()
        raise


def run(config_path: Path, out: Path) -> int:
    if out.exists():
        raise FileExistsError(f"report directory already exists: {out}")
    config = json.loads(config_path.read_text())
    side_count = len(config.get("sides", []))
    if config.get("app") != "photocraft" or side_count not in ({1, 2} if config.get("smoke") or config.get("single_side") else {2}):
        raise ValueError("PhotoCraft config requires app=photocraft and two sides (a one-side smoke or paired-side acquisition is also allowed)")
    if config.get("planned_pairs", 0) < 1:
        raise ValueError("planned_pairs must be positive")
    out.mkdir(parents=True)
    result = {
        "config": config,
        "pair": config["pair"],
        "tier": config["tier"],
        "driver_sha256": digest(Path(__file__).resolve()),
        "session_complete": False,
        "gpu_process_checks_passed": False,
        "sessions": [],
    }
    try:
        for side in config["sides"]:
            result["sessions"].append(spawn_side(side, {}, config, out))
        result["gpu_process_checks_passed"] = all(session["gpu_process_checks_passed"] for session in result["sessions"])
        result["gpu_state_passed"] = all(session["gpu_state_passed"] for session in result["sessions"])
        expected_samples = 1 if config.get("smoke") else (12 if config.get("brush_only") else 56)
        result["session_complete"] = all(session["process_exit_code"] == 0 and len(session["samples"]) == expected_samples for session in result["sessions"])
        result["comparison_complete"] = result["session_complete"] and len(result["sessions"]) == 2
        result["prior_acquisitions_passed"] = True
        result["output_checked"] = all(session.get("document_opened") if config.get("smoke") else (session.get("first_document_inspect") if config.get("brush_only") else session["saved_files"]) for session in result["sessions"])
        result["gpu_adapters"] = sorted({str(session.get("gpu", {}).get("gpuInfo", {}).get("adapter", "")) for session in result["sessions"]})
    except Exception as error:
        result["error"] = str(error)
        result["session_complete"] = False
    report_path = out / "report.json"
    report_path.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return 0 if result["session_complete"] and result["gpu_process_checks_passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", choices=("session",))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if args.probe:
        print("CRAFT_JOURNEY_NS=0")
        print("CRAFT_OUTPUT_SHA256=" + digest(Path(__file__).resolve()))
        return 0
    if args.mode != "session" or args.config is None or args.out is None:
        parser.error("session requires --config and --out")
    return run(args.config, args.out)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PhotoCraft session failed: {error}", file=sys.stderr)
        raise SystemExit(1)
