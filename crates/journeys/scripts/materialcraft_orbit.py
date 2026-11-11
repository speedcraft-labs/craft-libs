#!/usr/bin/env python3
"""Orbit Poly Haven's CC0 camera model in MaterialCraft and emit frame timings."""

import base64
import hashlib
import json
import math
import os
import pathlib
import signal
import socket
import statistics
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid


def fail(message):
    raise RuntimeError(message)


def pack_gltf(gltf_path):
    source = json.loads(gltf_path.read_text())
    if len(source.get("buffers", [])) != 1:
        fail("Camera_01 fixture must contain one external glTF buffer")
    uri = source["buffers"][0].get("uri")
    if not uri or "://" in uri:
        fail("Camera_01 fixture has an unexpected buffer URI")
    binary = (gltf_path.parent / uri).read_bytes()
    source["buffers"] = [{"byteLength": len(binary)}]
    source.pop("images", None)
    source.pop("textures", None)
    source.pop("samplers", None)
    source.pop("materials", None)
    for mesh in source.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            primitive.pop("material", None)
    document = json.dumps(source, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    document += b" " * ((-len(document)) % 4)
    binary += b"\0" * ((-len(binary)) % 4)
    chunks = struct.pack("<I4s", len(document), b"JSON") + document
    chunks += struct.pack("<I4s", len(binary), b"BIN\0") + binary
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunks)) + chunks


class Control:
    def __init__(self, stream, token):
        self.stream = stream
        self.reader = stream.makefile("r", encoding="utf-8")
        self.ident = 0
        self.call("auth", {"token": token})

    def call(self, method, params=None):
        self.ident += 1
        request = {"id": self.ident, "method": method, "params": params or {}}
        self.stream.sendall((json.dumps(request, separators=(",", ":")) + "\n").encode())
        line = self.reader.readline()
        if not line:
            fail(f"MaterialCraft control closed during {method}")
        reply = json.loads(line)
        if not reply.get("ok"):
            fail(f"MaterialCraft {method}: {reply.get('error', 'request failed')}")
        return reply.get("result")


def inspect(control):
    return control.call("ui.inspect")


def view_center(state):
    rect = state.get("view3dRect")
    if rect and len(rect) == 4 and rect[2] > 100 and rect[3] > 100:
        return rect[0] + rect[2] / 2, rect[1] + rect[3] / 2, rect[2], rect[3]
    # Older MaterialCraft builds don't expose the 3D panel rect. The default dock places it in
    # the lower-left half of the center column directly below graphView.
    graph = state.get("graphView")
    if graph and len(graph) == 4 and graph[2] > 200:
        return graph[0] + graph[2] * 0.25, graph[1] + graph[3] * 1.52, graph[2] * 0.5, graph[3] * 0.9
    fail("could not locate the 3D preview panel")


def terminate(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def main():
    input_path = pathlib.Path(sys.argv[1]).resolve()
    binary_path = pathlib.Path(os.environ["CARGO_TARGET_DIR"]) / "release" / "materialcraft"
    if not binary_path.is_file():
        fail(f"MaterialCraft binary is missing: {binary_path}")
    source_gltf = input_path.read_bytes()
    binary_buffer = (input_path.parent / "Camera_01.bin").read_bytes()
    hdr_path = os.environ.get("MATERIALCRAFT_PREVIEW_HDRI")
    hdr_bytes = pathlib.Path(hdr_path).read_bytes() if hdr_path else b"built-in-studio"
    model_hash = hashlib.sha256(source_gltf + binary_buffer).hexdigest()
    fixture_hash = hashlib.sha256((model_hash + "|camera01|wood|orbit-v1").encode()).hexdigest()
    token = uuid.uuid4().hex + uuid.uuid4().hex

    with tempfile.TemporaryDirectory(prefix="materialcraft-orbit-") as temp_dir:
        temp = pathlib.Path(temp_dir)
        glb_path = temp / "Camera_01.glb"
        glb_path.write_bytes(pack_gltf(input_path))
        reservation = socket.socket()
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
        reservation.close()

        child_env = os.environ.copy()
        child_env.update({
            "MATERIALCRAFT_CONTROL_TOKEN": token,
            "MATERIALCRAFT_NO_PREFS": "1",
            # Xvfb's GLX probe otherwise loads NVIDIA EGL/GBM alongside swrast and aborts.
            # MaterialCraft uses Vulkan; restricting EGL vendor discovery leaves Vulkan intact.
            "__EGL_VENDOR_LIBRARY_FILENAMES": "/usr/share/glvnd/egl_vendor.d/50_mesa.json",
        })
        command = [
            "xvfb-run", "-a", "--server-args", "-screen 0 1600x960x24",
            str(binary_path), "--control", str(port),
        ]
        process = subprocess.Popen(
            command, env=child_env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True,
        )
        stderr_lines = []

        def collect_stderr():
            for line in process.stderr:
                stderr_lines.append(line.decode("utf-8", errors="replace").rstrip())

        reader_thread = threading.Thread(target=collect_stderr, daemon=True)
        reader_thread.start()
        control = None
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    fail("MaterialCraft exited during startup: " + " | ".join(stderr_lines[-12:]))
                try:
                    stream = socket.create_connection(("127.0.0.1", port), timeout=1)
                    stream.settimeout(30)
                    control = Control(stream, token)
                    break
                except OSError:
                    time.sleep(0.1)
            if control is None:
                fail("MaterialCraft control socket did not start")

            control.call("ui.resize", {"width": 1600, "height": 960})
            control.call("command.run", {"id": "file.new", "params": {"name": "Orbit wood", "template": "wood", "size": 512}})
            loaded_mesh = control.call("command.run", {"id": "view.3d.loadMesh", "params": {"path": str(glb_path)}})
            model_triangles = loaded_mesh.get("triangles", 0) if isinstance(loaded_mesh, dict) else 0
            if model_triangles <= 0:
                fail("the Poly Haven model loaded without any triangles")
            control.call("command.run", {"id": "view.3d", "params": {"scene": "custom", "yaw": 35, "pitch": 22, "distance": 3.2, "target": [0, 0, 0]}})

            state = None
            rect = None
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                state = inspect(control)
                if state.get("cooking") is False and time.monotonic() + 19 < deadline:
                    # Let the asynchronous cook finish before beginning the orbit.
                    time.sleep(0.25)
                    state = inspect(control)
                if state.get("cooking") is True:
                    time.sleep(0.05)
                    continue
                if state.get("gpuAdapter") is not None and state.get("view3dRect"):
                    rect = view_center(state)
                    break
                if state.get("graphView"):
                    rect = view_center(state)
                    break
                time.sleep(0.05)
            if state is None or rect is None:
                fail("MaterialCraft did not lay out the 3D preview")
            material_session = control.call("session.inspect")
            material_graph = material_session.get("graph") or {}
            graph_nodes = material_graph.get("nodes") or []
            if not graph_nodes or material_session.get("dirty"):
                fail("the wood material graph did not finish cooking")

            cx, cy, width, height = rect
            start_x, end_x = cx - min(width * 0.22, 150), cx + min(width * 0.22, 150)
            control.call("ui.input", {"events": [{"type": "down", "pos": [start_x, cy]}]})
            cpu_samples = []
            gpu_samples = []
            gpu_preview_frames = 0
            interaction_frames = 36
            for index in range(1, interaction_frames + 1):
                fraction = index / interaction_frames
                point = [start_x + (end_x - start_x) * fraction, cy + math.sin(fraction * math.pi) * height * 0.055]
                control.call("ui.input", {"events": [{"type": "move", "pos": point}]})
                time.sleep(1 / 60)
                state = inspect(control)
                if state.get("gpuPreviewActive"):
                    gpu_preview_frames += 1
                cpu_ms = state.get("render3dMs")
                if isinstance(cpu_ms, (int, float)) and cpu_ms > 0:
                    cpu_samples.append(float(cpu_ms))
                gpu_ms = state.get("gpuFrameMs")
                if isinstance(gpu_ms, (int, float)) and gpu_ms > 0:
                    gpu_samples.append(float(gpu_ms))
            control.call("ui.input", {"events": [{"type": "up", "pos": [end_x, cy]}]})
            # The worker-rendered CPU fallback can block the UI for longer than one scripted
            # pointer interval. Snap both revisions to the same corpus camera before hashing the
            # settled image, while keeping the recorded samples from the actual orbit above.
            control.call("command.run", {"id": "view.3d", "params": {"scene": "custom", "yaw": 53.5, "pitch": 22, "distance": 3.2, "target": [0, 0, 0]}})

            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                time.sleep(0.15)
                state = inspect(control)
                # Read the next stats sample after orbit has ended so the current query resolves.
                gpu_ms = state.get("gpuFrameMs")
                if isinstance(gpu_ms, (int, float)) and gpu_ms > 0:
                    gpu_samples.append(float(gpu_ms))
                if state.get("gpuReferencePass") is not None:
                    break
                if not os.environ.get("MATERIALCRAFT_GPU_DIFF_CHECK") and state.get("render3dMs", 0) > 0:
                    break

            image = control.call("view.screenshot", {"view": "3d"})
            if not image or not image.get("png"):
                fail("MaterialCraft did not produce a settled 3D frame")
            screenshot_sha256 = hashlib.sha256(base64.b64decode(image["png"], validate=True)).hexdigest()
            gpu_timing_source = state.get("gpuFrameTiming") if state else None
            is_gpu_preview = bool(state and state.get("gpuPreviewActive"))
            head_check = "MATERIALCRAFT_GPU_DIFF_CHECK" in os.environ
            if head_check and state.get("gpuReferencePass") is not True:
                fail("GPU preview failed the settled ray-traced image comparison: " + json.dumps(state, sort_keys=True))
            adapter = state.get("gpuAdapter") if state else None
            if os.environ.get("MATERIALCRAFT_FORCE_SOFTWARE") == "1" and (not adapter or "llvmpipe" not in adapter.lower()):
                fail(f"software fallback requested but adapter was {adapter!r}")
            if head_check and os.environ.get("MATERIALCRAFT_FORCE_SOFTWARE") != "1" and (
                not adapter or "nvidia" not in adapter.lower() or "2080" not in adapter
            ):
                fail(f"expected the NVIDIA RTX 2080 Ti Vulkan adapter, got {adapter!r}")
            if head_check and gpu_preview_frames == 0:
                fail("the orbit did not render any interactive GPU preview frames")
            if head_check and not gpu_samples:
                fail("no Vulkan GPU frame timestamp was reported")
            samples = gpu_samples if gpu_samples else cpu_samples
            if not samples:
                fail("no interactive frame timings were reported")
            median_ms = statistics.median(samples)
            if gpu_samples and gpu_timing_source != "Vulkan timestamp query":
                fail(f"unexpected GPU frame timing source: {gpu_timing_source!r}")
            metadata = {
                "journey": "materialcraft.orbit-material-preview",
                "model": "Poly Haven Camera_01 (CC0-1.0)",
                "hdri": "Poly Haven Brown Photostudio 02 (CC0-1.0)" if hdr_path else "MaterialCraft built-in studio (baseline)",
                "asset_sha256": fixture_hash,
                "model_sha256": model_hash,
                "hdri_sha256": hashlib.sha256(hdr_bytes).hexdigest() if hdr_path else None,
                "material_graph_nodes": len(graph_nodes),
                "model_triangles": model_triangles,
                "adapter": adapter,
                "adapter_requested": "llvmpipe" if os.environ.get("MATERIALCRAFT_FORCE_SOFTWARE") == "1" else "hardware Vulkan",
                "gpu_timing_source": gpu_timing_source,
                "gpu_frame_ms_samples": gpu_samples,
                "gpu_frame_ms_p50": statistics.median(gpu_samples) if gpu_samples else None,
                "gpu_frame_ms_p95": sorted(gpu_samples)[max(0, math.ceil(len(gpu_samples) * 0.95) - 1)] if gpu_samples else None,
                "cpu_preview_ms_samples": cpu_samples,
                "cpu_preview_ms_p50": statistics.median(cpu_samples) if cpu_samples else None,
                "measured_frame_ms_p50": median_ms,
                "interactive_frames": interaction_frames,
                "interactive_gpu_preview_frames": gpu_preview_frames,
                "target_frame_ms": 16.7,
                "target_met": median_ms <= 16.7,
                "gpu_reference_mae": state.get("gpuReferenceMae") if state else None,
                "gpu_reference_pass": state.get("gpuReferencePass") if state else None,
                "settled_raytrace_png_sha256": screenshot_sha256,
                "settled_frame_size": [image.get("width"), image.get("height")],
            }
            metadata_dir = pathlib.Path(os.environ.get("MATERIALCRAFT_JOURNEY_METADATA_DIR", tempfile.gettempdir()))
            metadata_dir.mkdir(parents=True, exist_ok=True)
            app_rev = os.environ.get("CRAFT_JOURNEY_APP_REV", "unknown").replace("/", "_")[:16]
            adapter_slug = "unknown" if not adapter else "".join(ch.lower() if ch.isalnum() else "-" for ch in adapter).strip("-")[:48]
            metadata_path = metadata_dir / f"materialcraft-orbit-{app_rev}-{adapter_slug}.json"
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            print(f"CRAFT_JOURNEY_NS={int(median_ms * 1_000_000)}")
            print(f"CRAFT_OUTPUT_SHA256={screenshot_sha256}")
            print(f"MATERIALCRAFT_ADAPTER={adapter or 'not-reported'}")
            print(f"MATERIALCRAFT_GPU_FRAME_MS={metadata['gpu_frame_ms_p50']}")
            print(f"MATERIALCRAFT_GPU_REFERENCE_MAE={metadata['gpu_reference_mae']}")
        finally:
            if control is not None:
                try:
                    control.reader.close()
                    control.stream.close()
                except OSError:
                    pass
            terminate(process)
            reader_thread.join(timeout=1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"materialcraft orbit journey: {error}", file=sys.stderr)
        sys.exit(1)
