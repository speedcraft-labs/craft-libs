#!/usr/bin/env python3
"""Drive a typical LightCraft photo through its real desktop control channel."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from desktop_startup import ensure_display  # noqa: E402


class Control:
    def __init__(self, stream):
        self.stream = stream
        self.reader = stream.makefile("r", encoding="utf-8")
        self.ident = 0

    def call(self, method: str, params: dict | None = None):
        self.ident += 1
        request = {"id": self.ident, "method": method, "params": params or {}}
        encoded = (json.dumps(request, separators=(",", ":")) + "\n").encode()
        self.last_sent_ns = time.perf_counter_ns()
        self.stream.sendall(encoded)
        line = self.reader.readline()
        if not line:
            raise RuntimeError(f"LightCraft control closed during {method}")
        reply = json.loads(line)
        if reply.get("id") != self.ident:
            raise RuntimeError(f"LightCraft control id mismatch during {method}: {reply}")
        if not reply.get("ok"):
            raise RuntimeError(f"LightCraft {method}: {reply.get('error', 'request failed')}")
        return reply.get("result")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def digest_json(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8"):
        raise RuntimeError("LightCraft export is not a JPEG")
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            break
        marker = data[i]
        i += 1
        if marker in {0xD8, 0xD9, 0x01, *range(0xD0, 0xD8)}:
            continue
        if i + 2 > len(data):
            break
        length = int.from_bytes(data[i : i + 2], "big")
        if length < 2 or i + length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(data[i + 3 : i + 5], "big")
            width = int.from_bytes(data[i + 5 : i + 7], "big")
            return width, height
        i += length
    raise RuntimeError("LightCraft export JPEG has no valid frame dimensions")


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or not header.startswith(b"\x89PNG\r\n\x1a\n") or header[12:16] != b"IHDR":
        raise RuntimeError("LightCraft render is not a valid PNG")
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def sample_output_path(target_dir: Path, task: str, suffix: str) -> Path:
    directory = target_dir / "lightcraft-output-samples" / task
    directory.mkdir(parents=True, exist_ok=True)
    revision = os.environ.get("CRAFT_JOURNEY_APP_REV", "unknown").replace("/", "_")[:12]
    return directory / f"{revision}-{time.time_ns()}{suffix}"


def latest_sample(target_dir: Path, task: str, suffix: str) -> Path:
    directory = target_dir / "lightcraft-output-samples" / task
    files = list(directory.glob(f"*{suffix}")) if directory.is_dir() else []
    if not files:
        raise RuntimeError(f"LightCraft {task} did not preserve an output sample")
    return max(files, key=lambda path: path.stat().st_mtime_ns)


def exposure_identity(control: Control, photo_id, source_hash: str, task: str) -> str:
    state = control.call("engine.execute", {"command": "develop.get", "params": {"id": photo_id}})
    exposure = state.get("light", {}).get("exposure") if isinstance(state, dict) else None
    if not isinstance(exposure, (int, float)) or abs(float(exposure) - 0.7) > 1e-6:
        raise RuntimeError(f"LightCraft did not retain exposure +0.7: {exposure!r}")
    return digest_json({"source": source_hash, "task": task, "light.exposure": 0.7})


def stable_identity(source_hash: str, task: str, **result) -> str:
    return digest_json({"source": source_hash, "task": task, "result": result})


def spawn(binary: Path, library: Path, profile: Path, photo_path: Path | None, *, log_path: Path | None = None, on_started=None):
    profile.mkdir(parents=True, exist_ok=True)
    library.mkdir(parents=True, exist_ok=True)
    port = free_port()
    env = os.environ.copy()
    env.update({
        "HOME": str(profile),
        "XDG_CONFIG_HOME": str(profile / ".config"),
        "XDG_DATA_HOME": str(profile / ".local/share"),
        "XDG_CACHE_HOME": str(profile / ".cache"),
        "LIGHTCRAFT_CONFIG_DIR": str(profile / "lightcraft-config"),
    })
    if log_path is not None:
        # Session-only profile: a launcher-managed pin suppresses asynchronous update
        # prompts/network checks without changing the app or the legacy journeys.
        versions = profile / 'versions.json'
        versions.write_text(json.dumps({'apps': {'lightcraft': {'Pinned': 'session-benchmark'}}}))
        env['CRAFT_VERSIONS_FILE'] = str(versions)
    command = [str(binary), "--library", str(library), "--no-demo", "--control", str(port)]
    if photo_path is not None:
        command.append(str(photo_path))
    with log_path.open("wb") if log_path else open(os.devnull, "wb") as log:
        process = subprocess.Popen(command, cwd=profile, env=env, stdout=log, stderr=log)
    if on_started is not None:
        on_started(process.pid)
    deadline = time.monotonic() + 90
    control = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"LightCraft exited during startup with status {process.returncode}")
        try:
            stream = socket.create_connection(("127.0.0.1", port), timeout=0.25)
            stream.settimeout(max(1.0, deadline - time.monotonic()))
            control = Control(stream)
            break
        except OSError:
            time.sleep(0.002 if log_path is not None else 0.02)
    if control is None:
        process.terminate()
        process.wait(timeout=5)
        raise TimeoutError("LightCraft control channel did not start")
    control.process_pid=process.pid
    control.session_log=log_path
    return process, control


def wait_for_photo(control: Control, process: subprocess.Popen) -> dict:
    deadline = time.monotonic() + 90
    last_error = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"LightCraft exited while opening the photo with status {process.returncode}")
        try:
            photo = control.call("engine.execute", {"command": "photo.inspect"})
            if isinstance(photo, dict) and photo.get("id") is not None:
                return photo
        except RuntimeError as error:
            last_error = error
        time.sleep(0.05)
    raise TimeoutError(f"LightCraft did not activate the photo: {last_error}")


def render_preview(control: Control, output: Path, photo_id) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    control.call("ui.render", {"id": photo_id, "size": 1024, "path": str(output)})
    if not output.is_file() or not output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("LightCraft did not write the requested preview PNG")
    return file_digest(output)


def stop(process: subprocess.Popen, control: Control) -> None:
    try:
        control.call("engine.execute", {"command": "app.quit"})
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


def run_task(binary: Path, task: str, input_path: Path, target_dir: Path) -> int:
    state_dir = target_dir / "lightcraft-real-world-task"
    shutil.rmtree(state_dir, ignore_errors=True)
    library = state_dir / "library"
    profile = state_dir / "profile"
    expected_path = state_dir / "expected.json"
    preview = sample_output_path(target_dir, task, ".png") if task in {"open", "edit", "save"} else state_dir / "preview.png"
    export_path = sample_output_path(target_dir, task, ".jpg") if task == "export" else state_dir / "export.jpg"
    source_hash = file_digest(input_path)

    process, control = spawn(binary, library, profile, input_path)
    try:
        photo = wait_for_photo(control, process)
        photo_id = photo["id"]
        operation_started = time.perf_counter_ns()
        if task == "open":
            preview_hash = render_preview(control, preview, photo_id)
            identity = stable_identity(source_hash, task, output="valid-png")
        elif task in {"edit", "save"}:
            control.call("engine.execute", {"command": "develop.set", "params": {"values": {"light.exposure": 0.7}}})
            edited = control.call("engine.execute", {"command": "photo.inspect"})
            if not isinstance(edited, dict) or edited.get("id") is None:
                raise RuntimeError("LightCraft did not return the edited photo state")
            preview_hash = render_preview(control, preview, photo_id)
            identity = exposure_identity(control, photo_id, source_hash, task)
            expected_path.write_text(json.dumps({"source": source_hash, "task": task, "identity": identity}, sort_keys=True) + "\n")
            if task == "save":
                identity = str(json.loads(expected_path.read_text())["identity"])
        elif task == "export":
            result = control.call("engine.execute", {
                "command": "app.export",
                "params": {
                    "path": str(export_path),
                    "ids": [photo_id],
                    "format": "jpeg",
                    "longEdge": 2048,
                    "quality": 90,
                    "background": False,
                },
            })
            if not export_path.is_file() or export_path.stat().st_size == 0:
                raise RuntimeError(f"LightCraft export did not write a JPEG: {result}")
            identity = stable_identity(source_hash, task, format="jpeg", long_edge=2048, quality=90)
        else:
            raise ValueError(f"unknown LightCraft task {task!r}")
        task_ns = time.perf_counter_ns() - operation_started
        if task == "save":
            stop(process, control)
            process = None
        else:
            stop(process, control)
            process = None
        print(f"CRAFT_JOURNEY_NS={task_ns}")
        print(f"CRAFT_OUTPUT_SHA256={identity}")
        if task in {"open", "edit", "save"}:
            print(f"CRAFT_RENDER_SHA256={preview_hash}")
        return 0
    finally:
        if process is not None:
            stop(process, control)
        control.stream.close()


def verify_save(binary: Path, input_path: Path, target_dir: Path) -> int:
    state_dir = target_dir / "lightcraft-real-world-task"
    library = state_dir / "library"
    profile = state_dir / "verify-profile"
    expected_path = state_dir / "expected.json"
    expected = json.loads(expected_path.read_text())
    process, control = spawn(binary, library, profile, None)
    try:
        photo = wait_for_photo(control, process)
        render_preview(control, state_dir / "verified.png", photo["id"])
        identity = exposure_identity(control, photo["id"], expected["source"], expected["task"])
        expected_identity = str(expected["identity"])
        if identity != expected_identity:
            raise RuntimeError("saved LightCraft exposure edit did not reproduce its pre-save state")
        sample = latest_sample(target_dir, "save", ".png")
        if not all(dimension > 0 for dimension in png_size(sample)):
            raise RuntimeError("saved LightCraft edit preview has invalid dimensions")
        print(f"CRAFT_OUTPUT_SHA256={identity}")
        return 0
    finally:
        stop(process, control)
        control.stream.close()


def verify_output(task: str, input_path: Path, target_dir: Path) -> int:
    source_hash = file_digest(input_path)
    if task in {"open", "edit"}:
        sample = latest_sample(target_dir, task, ".png")
        if not all(dimension > 0 for dimension in png_size(sample)):
            raise RuntimeError(f"LightCraft {task} preview has invalid dimensions")
        if task == "edit":
            expected_path = target_dir / "lightcraft-real-world-task" / "expected.json"
            expected = json.loads(expected_path.read_text())
            if expected.get("source") != source_hash or expected.get("task") != task:
                raise RuntimeError("LightCraft edit output does not match its source photo")
            identity = str(expected["identity"])
        else:
            identity = stable_identity(source_hash, task, output="valid-png")
    elif task == "export":
        sample = latest_sample(target_dir, task, ".jpg")
        dimensions = jpeg_size(sample)
        if max(dimensions) != 2048:
            raise RuntimeError(f"LightCraft export has unexpected dimensions {dimensions}; expected a 2048-pixel long edge")
        identity = stable_identity(source_hash, task, format="jpeg", long_edge=2048, quality=90)
    else:
        raise ValueError(f"unknown output verification task {task!r}")
    print(f"CRAFT_OUTPUT_SHA256={identity}")
    return 0


def session_wait_exit(process, timeout=150):
    # Popen.wait(timeout=...) polls with up to 50 ms sleeps on POSIX. A pidfd gives
    # an event-driven exit observation on Agentbox, without quantizing short quits.
    import select
    if not hasattr(os, 'pidfd_open'):
        raise RuntimeError('session exit timing requires Linux pidfd support')
    descriptor=os.pidfd_open(process.pid)
    try:
        if not select.select([descriptor],[],[],timeout)[0]:
            raise TimeoutError('quit did not exit before the deadline')
        process.wait()
        return time.perf_counter_ns()
    finally:
        os.close(descriptor)


def session_execute(control, command, params=None):
    delay=getattr(control,'test_delay_ms',0) if command=='library.select' and getattr(control,'action_sampler',None) else 0
    if delay:
        started=time.perf_counter_ns()
        time.sleep(delay/1000)
    result=control.call('engine.execute', {'command': command, 'params': params or {}})
    if delay:
        control.last_sent_ns=started
    return result


def session_idle(state):
    perf = state['perf']
    return perf.get('renderQueue') == 0 and perf.get('rendersInFlight') == 0 and perf.get('pendingSlots') == []


def session_wait(control, predicate, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = control.call('ui.inspect')
        if predicate(state):
            return state
        time.sleep(.005)
    raise TimeoutError(f'LightCraft frame state did not converge: {state}')


def session_drain(control, record, phase, require_saved=False):
    """Wait outside action/quit/startup clocks for real background work to finish."""
    entry=dict(phase=phase,start_ns=time.perf_counter_ns(),progress=[])
    record.setdefault('background_drains',[]).append(entry)
    next_log=time.monotonic()+30
    idle_since=None
    def ready(state):
        nonlocal next_log,idle_since
        now=time.monotonic()
        idle=session_idle(state) and not state['activity'] and not state['tasks']
        if idle and (not require_saved or state.get('unsaved') is None):
            if idle_since is None:idle_since=now
            # ui.inspect omits activity rows younger than 0.5s. A single empty
            # snapshot must not mistake a newly started preparation job for idle.
            if now-idle_since>=1:return True
        else:idle_since=None
        if now>=next_log:
            progress=dict(ns=time.perf_counter_ns(),activity=state['activity'],tasks=state['tasks'],unsaved=state.get('unsaved'))
            entry['progress'].append(progress)
            print(f'background drain {phase}: '+json.dumps(progress),flush=True)
            next_log=time.monotonic()+30
        return False
    state=session_wait(control,ready,timeout=1800)
    entry['end_ns']=time.perf_counter_ns()
    return state


class SessionX11Capture:
    """Read our visible X11 window; later native PNG must prove identical pixels."""
    def __init__(self, pid):
        import re
        from PIL import ImageGrab
        self.display=os.environ.get('DISPLAY')
        tree=subprocess.check_output(['xwininfo','-display',self.display,'-root','-tree'],text=True)
        selected=None
        for wid in re.findall(r'^\s*(0x[0-9a-f]+)\s',tree,re.M):
            prop=subprocess.run(['xprop','-display',self.display,'-id',wid,'_NET_WM_PID'],capture_output=True,text=True)
            if re.search(r'=\s*'+str(pid)+r'\s*$',prop.stdout):
                info=subprocess.check_output(['xwininfo','-display',self.display,'-id',wid],text=True)
                def value(key):return int(re.search(re.escape(key)+r':\s*(-?\d+)',info)[1])
                rectangle=(value('Absolute upper-left X'),value('Absolute upper-left Y'),value('Width'),value('Height'))
                if selected is None or rectangle[2]*rectangle[3]>selected[2]*selected[3]:selected=rectangle
        if selected is None:raise RuntimeError('no X11 window belongs to the app PID')
        x,y,w,h=selected
        screen=ImageGrab.grab(xdisplay=self.display)
        if x<0 or y<0 or x+w>screen.width or y+h>screen.height:
            raise RuntimeError('app window extends outside the X display')
        self.bounds=(x,y,x+w,y+h)

    def grab(self):
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=self.bounds,xdisplay=self.display).convert('RGB')


class SessionSampler:
    """Observe displayed pixels from BEFORE dispatch, independently of readiness polling."""
    def __init__(self, control):
        import threading
        if not hasattr(control, 'x11_capture'):
            control.x11_capture = SessionX11Capture(control.process_pid)
        self.capture = control.x11_capture
        self.candidates = []
        self.failures = []
        self.stop = threading.Event()
        self.started = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        if not self.started.wait(3):
            raise RuntimeError('X11 observer did not start before action')

    def run(self):
        try:
            while not self.stop.is_set():
                pixels = self.capture.grab()
                ns = time.perf_counter_ns()
                self.candidates.append((ns, pixels.size, hashlib.sha256(pixels.tobytes()).hexdigest()))
                self.started.set()
                self.stop.wait(.001)
        except Exception as error:
            self.failures.append(str(error))
            self.started.set()

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            raise RuntimeError('X11 observer did not stop')


def session_arm(control, record, action):
    session_drain(control, record, 'before-' + action)
    if getattr(control, 'action_sampler', None) is not None:
        raise RuntimeError('previous action observer still running')
    control.action_sampler = SessionSampler(control)


def session_capture_once(control, path):
    import threading
    from PIL import Image
    candidates=[]
    failures=[]
    stop_sampling=threading.Event()
    sampler=None
    try:
        if not hasattr(control,'x11_capture'):
            control.x11_capture=SessionX11Capture(control.process_pid)
        def sample():
            try:
                while not stop_sampling.is_set():
                    pixels=control.x11_capture.grab()
                    captured=time.perf_counter_ns()
                    candidates.append((captured,pixels.size,hashlib.sha256(pixels.tobytes()).hexdigest()))
                    stop_sampling.wait(.005)
            except Exception as error:
                failures.append(str(error))
        if getattr(control,'action_sampler',None) is None:
            sampler=threading.Thread(target=sample,daemon=True)
            sampler.start()
    except Exception as error:
        failures.append(str(error))
    try:
        # A later native PNG verifies which earlier displayed frame really showed
        # this result. Hashes retain every observed candidate without duplicate media.
        control.call('ui.screenshot', {'path': str(path), 'headless': False})
        verified_ns=time.perf_counter_ns()
    finally:
        stop_sampling.set()
        if sampler is not None:sampler.join(timeout=3)
    if min(png_size(path))<=0:raise RuntimeError('empty native frame')
    reference=Image.open(path).convert('RGB')
    reference_hash=hashlib.sha256(reference.tobytes()).hexdigest()
    observer=getattr(control,'action_sampler',None)
    if observer is not None:
        candidates=list(observer.candidates)+candidates
        failures+=observer.failures
    matching=[ns for ns,size,digest in candidates if ns<=verified_ns and size==reference.size and digest==reference_hash]
    end=min(matching) if matching else verified_ns
    control.last_capture_proof=dict(method='verified-x11' if matching else 'native-upper-bound',frame_ns=end,verified_ns=verified_ns,
        reference_png=str(path),reference_png_sha256=file_digest(path),rgb_sha256=reference_hash,
        width=reference.width,height=reference.height,failures=failures,
        candidates=[dict(ns=ns,width=size[0],height=size[1],rgb_sha256=digest) for ns,size,digest in candidates if ns<=verified_ns])
    return end,reference_hash


def session_frame(control, path):
    # The native API can fall back after a compositor timeout. Keep that failed
    # evidence, retry without resetting the caller's action clock, and require a
    # successful native capture before accepting any endpoint.
    attempts=[]
    for attempt in range(3):
        log=getattr(control,'session_log',None)
        before=log.stat().st_size if log is not None else 0
        end,digest=session_capture_once(control,path)
        recent=log.read_bytes()[before:] if log is not None else b''
        proof=control.last_capture_proof
        proof['native']='rendering headlessly' not in recent.decode(errors='replace')
        if proof['native']:
            proof['attempts']=attempts
            # A failed control screenshot may still have sampled the correct real
            # window. The successful native PNG verifies those earlier X11 pixels
            # too: take the earliest match across every attempt, never a timeout
            # or an assumed subtraction from the action duration.
            proof['candidates']=[c for failed in attempts for c in failed['candidates']]+proof['candidates']
            matching=[c['ns'] for c in proof['candidates'] if c['ns']<=proof['verified_ns'] and c['rgb_sha256']==digest and (c['width'],c['height'])==(proof['width'],proof['height'])]
            if matching:
                end=min(matching)
                proof.update(method='verified-x11',frame_ns=end)
            return end,digest
        retained=path.with_name(f'{path.stem}.headless-attempt-{attempt}{path.suffix}')
        path.rename(retained)
        proof['reference_png']=str(retained)
        attempts.append(proof)
    raise RuntimeError(f'native compositor capture failed after three attempts: {attempts}')


def session_result(control, path, sent, not_before=None):
    end, digest = session_frame(control, path)
    observer = getattr(control, 'action_sampler', None)
    if observer is not None:
        observer.finish()
        control.action_sampler = None
    proof = control.last_capture_proof
    proof['candidates'] = [c for c in proof['candidates'] if c['ns'] > sent and (not_before is None or c['ns']>=not_before)]
    matches = [c['ns'] for c in proof['candidates'] if c['rgb_sha256'] == digest
               and (c['width'], c['height']) == (proof['width'], proof['height'])]
    end = min(matches) if matches else proof['verified_ns']
    proof.update(frame_ns=end, method='verified-x11' if matches else 'native-upper-bound')
    return end, digest


def session_detail(control, photo):
    def ready(state):
        loupe = state.get('loupe') or {}
        if loupe.get('failed'):
            raise RuntimeError(f'preview failed: {loupe}')
        return state.get('active') == photo and loupe.get('photo') == photo and loupe.get('source') in ('render', 'cached') and not loupe.get('pending') and session_idle(state)
    return session_wait(control, ready)


def session_sample(record, action, sent, end, digest, warmup, **evidence):
    phase='cold' if not any(x['action']==action for x in record['samples']) else 'warm'
    record['samples'].append(dict(action=action, phase=phase, sent_ns=sent, frame_ns=end, duration_ns=end-sent,
                                  frame_sha256=digest, warmup=warmup, checked=True, evidence=evidence))
    (Path(record['directory'])/'partial-session.json').write_text(json.dumps(record,indent=2)+'\n')


def session_pointer(control, x, y, kind='move'):
    # ui.pointer coordinates are relative to imageRect, including points outside the photo.
    rect = control.call('ui.inspect')['imageRect']
    if not rect:
        raise RuntimeError('pointer gesture needs a displayed photo')
    control.call('ui.pointer', {'events': [{'kind': kind, 'x': (x-rect[0])/rect[2], 'y': (y-rect[1])/rect[3]}]})


def session_grid_settled(control):
    previous=None
    stable=0
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        state=control.call('ui.inspect')
        offset=state.get('scroll',{}).get('grid')
        stable=stable+1 if offset is not None and previous is not None and abs(offset-previous)<.05 else 0
        if stable>=3 and session_idle(state):return state
        previous=offset
        time.sleep(.01)
    raise TimeoutError('grid did not settle')


def session_grid_at_top(state):
    offset=state.get('scroll',{}).get('grid')
    return offset is not None and abs(offset)<1


def session_grid(control, ids, directory):
    """Visit every grid thumbnail, retaining a native frame and checking actual image content."""
    from PIL import Image, ImageStat
    seen = set()
    frames = []
    session_execute(control, 'view.squareGrid')
    control.call('ui.set', {'thumbSize': 100})
    first=session_execute(control,'catalog.query',{'limit':1})['photos'][0]['id']
    session_execute(control,'library.select',{'ids':[first]})
    session_frame(control,directory/'grid-ready.png')
    # Import can reveal the active photo near the bottom of the date-sorted grid.
    # Wheel points clamp at the boundary. An unended trackpad gesture can hold a
    # huge negative rubber-band offset and leave every thumbnail outside the view.
    view=next(w for w in control.call('ui.widgets',{'filter':'grid:scroll'}) if w['id']=='grid:scroll')
    vx,vy,vw,vh=view['rect']
    control.call('ui.move',{'x':vx+vw/2,'y':vy+vh/2})
    control.call('ui.scroll',{'dy':100000,'source':'wheel','unit':'point'})
    session_wait(control,session_grid_at_top)
    session_frame(control,directory/'grid-top.png')
    previous_scroll = None
    for page in range(len(ids) + 5):
        state = session_grid_settled(control)
        widgets = control.call('ui.widgets', {'filter': 'thumb:'})
        visible = []
        for w in widgets:
            if not w['id'].startswith('thumb:'):
                continue
            ident = int(w['id'].split(':')[1])
            x,y,width,height = w['rect']
            if ident in ids and y >= vy and y+height <= vy+vh and x >= vx and x+width <= vx+vw:
                visible.append((ident, (x,y,width,height)))
        if not visible:
            (directory/f'empty-grid-{page}.json').write_text(json.dumps(dict(state=state,widgets=widgets),indent=2))
            session_frame(control,directory/f'empty-grid-{page}.png')
            raise RuntimeError('no fully visible grid thumbnails; state and native frame retained')
        # With no pending renders, require resident thumbnail textures as well as non-placeholder pixels.
        if state['perf']['thumbTextures'] < len(visible):
            time.sleep(.02)
            continue
        path = directory / f'grid-{page}.png'
        end,digest = session_frame(control,path)
        after=control.call('ui.inspect')
        if abs(after['scroll']['grid']-state['scroll']['grid'])>.5:
            continue  # The recorded geometry and captured pixels must describe the same viewport.
        image = Image.open(path).convert('RGB')
        ppp = state['pixelsPerPoint']
        for ident,(x,y,w,h) in visible:
            # Stay inside the photo, away from its caption, border and selection markers.
            crop=image.crop(tuple(round(v*ppp) for v in (x+w*.3,y+h*.25,x+w*.7,y+h*.55)))
            if max(ImageStat.Stat(crop).stddev) < 1.0:
                raise RuntimeError(f'blank/placeholder thumbnail {ident} on page {page}')
            seen.add(ident)
        frames.append(dict(path=str(path), sha256=digest, ids=[i for i,_ in visible],perf=state['perf'],capture=control.last_capture_proof))
        if seen == set(ids):
            return end,digest,frames
        scroll = state.get('scroll',{}).get('grid')
        if scroll == previous_scroll and page > 0:
            raise RuntimeError(f'grid stopped before all thumbnails: {len(seen)}/{len(ids)}')
        previous_scroll = scroll
        control.call('ui.move', {'x': state['window'][0]/2, 'y': state['window'][1]/2})
        control.call('ui.scroll', {'dy': -vh*.5,'source':'wheel','unit':'point'})
        session_wait(control,lambda s:s.get('scroll',{}).get('grid')!=scroll)
    raise RuntimeError(f'not all thumbnails shown: {len(seen)}/{len(ids)}')


def session_gpu_processes():
    import csv
    import io
    command=['nvidia-smi','--query-compute-apps=pid,name','--format=csv']
    output=subprocess.check_output(command,text=True,timeout=15)
    rows=list(csv.reader(io.StringIO(output)))
    if not rows or rows[0][0].strip()!='pid':raise RuntimeError(f'invalid GPU process listing: {output}')
    processes=[dict(pid=int(row[0].strip()),name=row[1].strip()) for row in rows[1:] if row]
    return dict(ns=time.perf_counter_ns(),command=command,csv=output,processes=processes)


def session_gpu_foreign(snapshots, own_pids=()):
    own=set(own_pids)
    found={}
    for snapshot in snapshots:
        for process in (snapshot or {}).get('processes',[]):
            if process['pid'] in own:
                continue
            found[(process['pid'],process['name'])]=process
    return sorted(found.values(),key=lambda process:(process['name'],process['pid']))


def session_gpu_admit(deadline, provisional=False, observe=None, pause=None, now=None, on_wait=None):
    observe=observe or session_gpu_processes
    pause=pause or time.sleep
    now=now or time.monotonic
    while True:
        snapshot=observe()
        if not snapshot['processes']:
            return snapshot,provisional
        if provisional or now()>=deadline:
            return snapshot,True
        if on_wait is not None:on_wait(snapshot)
        pause(min(30,max(0,deadline-now())))


class SessionGpuWatch:
    def __init__(self):
        import threading
        self.samples=[]
        self.errors=[]
        self.stopped=threading.Event()
        self.thread=threading.Thread(target=self.collect,daemon=True)

    def collect(self):
        while not self.stopped.is_set():
            try:self.samples.append(session_gpu_processes())
            except Exception as error:self.errors.append(str(error))
            self.stopped.wait(2)

    def start(self):self.thread.start()

    def stop(self):
        self.stopped.set()
        self.thread.join(timeout=20)
        if self.thread.is_alive():self.errors.append('GPU process watcher did not stop')


def session_guarded_attempt(report,checkpoint,binary,directory,tier,side,pair,run):
    """Resource admission around the existing driver; action clocks stay inside run()."""
    deadline=time.monotonic()+1800
    cycle_started=time.perf_counter_ns()
    attempt=0
    report.setdefault('discarded_sessions',[])
    report.setdefault('failed_sessions',[])
    report.setdefault('gpu_wait_events',[])
    provisional_tiers=report.setdefault('provisional_tiers',{})
    def mark_provisional(offenders):
        names=provisional_tiers.setdefault(tier,[])
        names[:]=sorted(set(names)|{p['name'] for p in offenders})
    while True:
        def waited(snapshot):
            report['gpu_wait_events'].append(dict(tier=tier,side=side,pair=pair,attempt=attempt,snapshot=snapshot))
            print(f'GPU wait {tier} pair {pair} {side}: '+', '.join(p['name'] for p in snapshot['processes']),flush=True)
            checkpoint()
        admitted,provisional=session_gpu_admit(deadline,tier in provisional_tiers,on_wait=waited)
        if provisional:
            mark_provisional(admitted['processes'])
            print(f'PROVISIONAL {tier}: GPU-clean session budget exhausted; offenders '+', '.join(provisional_tiers[tier]),flush=True)
        attempt_dir=directory.with_name(f'{directory.name}-attempt-{attempt}')
        watcher=SessionGpuWatch()
        watcher.start()
        error=None
        owned_pids=[]
        try:
            record=run(attempt_dir,provisional,owned_pids.append)
        except Exception as failure:
            error=failure
            record={}
            for name in ('partial-session.json','diagnostic.json'):
                path=attempt_dir/name
                if path.exists():record=json.loads(path.read_text());break
            rejected=attempt_dir/'gpu-processes-rejected.json'
            if rejected.exists():record['gpu_processes_before']=json.loads(rejected.read_text())
        finally:
            watcher.stop()
        after=session_gpu_processes()
        # A startup failure may precede the first driver checkpoint/control connection.
        # Preserve ownership from Popen so our failed app is never retried as contention.
        record['process_ids']=sorted(set(record.get('process_ids',[]))|set(owned_pids))
        record.setdefault('gpu_processes_before',admitted)
        driver_after=record.get('gpu_processes_after')
        record.update(directory=str(attempt_dir),side=side,tier=tier,pair=pair,attempt=attempt,
                      gpu_processes_after=after,gpu_poll_snapshots=watcher.samples,
                      gpu_processes_driver_after=driver_after,
                      gpu_admission_snapshot=admitted,gpu_wait_cycle_started_ns=cycle_started,
                      gpu_provisional=provisional)
        foreign=session_gpu_foreign([admitted,record['gpu_processes_before'],driver_after,after,*watcher.samples],record.get('process_ids',[]))
        record['gpu_foreign_processes']=foreign
        if error is not None:record['application_error']=str(error)
        if watcher.errors:record['gpu_inspection_errors']=watcher.errors
        attempt_dir.mkdir(parents=True,exist_ok=True)
        if foreign and not provisional:
            record['gpu_status']='discarded-contention'
            report['discarded_sessions'].append(record)
            (attempt_dir/'discarded-session.json').write_text(json.dumps(record,indent=2)+'\n')
            if (attempt_dir/'session.json').exists():(attempt_dir/'session.json').write_text(json.dumps(record,indent=2)+'\n')
            print(f'discard {tier} pair {pair} {side} attempt {attempt}: '+', '.join(p['name'] for p in foreign),flush=True)
            if time.monotonic()>=deadline:mark_provisional(foreign)
            checkpoint()
            attempt+=1
            continue
        if error is not None or watcher.errors:
            record['gpu_status']='failed'
            report['failed_sessions'].append(record)
            (attempt_dir/'failed-session.json').write_text(json.dumps(record,indent=2)+'\n')
            checkpoint()
            if error is not None:raise error
            raise RuntimeError(f'GPU process inspection failed: {watcher.errors}')
        if provisional:mark_provisional(foreign)
        record['gpu_status']='shared-provisional' if provisional else 'clean'
        record['gpu_tier_offenders']=list(provisional_tiers.get(tier,[]))
        (attempt_dir/('diagnostic.json' if 'quit_ns' in record else 'session.json')).write_text(json.dumps(record,indent=2)+'\n')
        checkpoint()
        return record


def run_session(binary, payload, directory, side, tier, pair, repetitions, warmups, gpu_provisional=False, on_started=None, exposure_steps=10):
    from lightcraft_session_report import validate_session, check_export_pixels
    directory.mkdir(parents=True,exist_ok=False)
    library,profile = directory/'library',directory/'profile'
    log_path=directory/'app.log'
    gpu_before=session_gpu_processes()
    if gpu_before['processes'] and not gpu_provisional:
        (directory/'gpu-processes-rejected.json').write_text(json.dumps(gpu_before,indent=2))
        raise RuntimeError(f'foreign GPU process before session: {gpu_before}')
    record=dict(side=side,tier=tier,pair=pair,directory=str(directory),samples=[],gpu_provisional=gpu_provisional,gpu_processes_before=gpu_before,launch_ns=time.perf_counter_ns())
    process,control=spawn(binary,library,profile,None,log_path=log_path,on_started=on_started)
    control.test_delay_ms=float(os.environ.get('CRAFT_JOURNEYS_TEST_SWITCH_DELAY_MS','0')) if side=='main' else 0
    record['test_switch_delay_ms']=control.test_delay_ms
    record['process_ids']=[process.pid]
    try:
        state=control.call('ui.inspect')
        # ui.inspect deliberately omits transient dialogs. Cancel optional first-run
        # onboarding through the supported dialog API before any action is timed.
        control.call('ui.set',{'settings':{'previewLimit':0,'lensDatabase':'declined'}})
        control.call('ui.dialog.cancel')
        record['interactive_ns'],_=session_frame(control,directory/'interactive.png')
        record['interactive_capture']=control.last_capture_proof
        # Initial GPU setup may continue after the first interactive (CPU) window.
        # Warm it completely before measuring actions; never publish silent CPU fallback.
        state=session_wait(control,lambda s:bool(s['perf'].get('gpu')),timeout=900)
        record['gpu_ready_ns']=time.perf_counter_ns()
        record['gpu_adapter']=state['perf']['gpu']
        paths=[str(p) for p in sorted(payload.iterdir()) if p.is_file() and not p.name.startswith('.')]
        if not paths:
            raise ValueError('empty RAW payload')
        # Warm import and repeat real import after removing catalog records only; originals stay.
        for iteration in range(warmups+repetitions):
            if iteration:
                session_execute(control,'photo.deletePermanently',{'ids': ids})
                control.call('ui.move', {'x': 600, 'y': 350})
                control.call('ui.scroll', {'dy': 100000})
            session_arm(control,record,'import')
            control.call('ui.dropFiles',{'paths':[str(payload)]})
            sent=control.last_sent_ns
            review=session_wait(control,lambda s:any(w['id']=='label:importSource' for w in control.call('ui.widgets',{'filter':'label:importSource'})))
            control.call('ui.clickWidget',{'id':'button:importAdd'})
            result=control.call('ui.dialog.confirm')
            if result.get('importing')!=len(paths):
                raise RuntimeError(f'incomplete import request: {result}')
            session_wait(control,lambda s:s.get('import') is None and s.get('scan') is None)
            catalog=session_execute(control,'catalog.query',{'limit':len(paths)+1})
            photos=sorted(catalog['photos'],key=lambda p:p['fileName'])
            if len(photos)!=len(paths) or {p['fileName'] for p in photos}!={Path(p).name for p in paths}:
                raise RuntimeError(f'incomplete/wrong import: {catalog}')
            ids=[p['id'] for p in photos]
            grid_dir=directory/f'import-{iteration}'
            grid_dir.mkdir()
            end,digest,frames=session_grid(control,ids,grid_dir)
            end,digest=session_result(control,grid_dir/'verified-result.png',sent)
            session_sample(record,'import',sent,end,digest,iteration<warmups,imported=len(ids),frames=frames,capture=control.last_capture_proof)
        record['photo_ids']=ids
        record['photos']=photos
        photo=ids[0]
        if photos[0].get('previewOnly'):
            raise RuntimeError(f'full-quality RAW preview unavailable: {photos[0]}')
        for iteration in range(warmups+repetitions):
            session_execute(control,'view.squareGrid')
            session_execute(control,'view.zoomFit')
            session_execute(control,'library.select',{'ids':[photo]})
            session_arm(control,record,'preview')
            session_execute(control,'view.detail')
            sent=control.last_sent_ns
            session_execute(control,'view.zoom100')
            state=session_detail(control,photo)
            end,digest=session_result(control,directory/f'preview-{iteration}.png',sent)
            session_sample(record,'preview',sent,end,digest,iteration<warmups,loupe=state['loupe'],image_rect=state['imageRect'],perf=state['perf'],capture=control.last_capture_proof)
            session_execute(control,'view.squareGrid')
            session_execute(control,'view.zoomFit')
        session_execute(control,'view.detail')
        session_detail(control,photo)
        # A held real slider gesture, one acknowledged pointer movement and resulting frame per step.
        slider=next(w for w in control.call('ui.widgets',{'filter':'slider:light.exposure'}) if w['id']=='slider:light.exposure')
        x,y,w,h=slider['rect']
        for iteration in range(repetitions):
            start=.30 if iteration%2==0 else .70
            control.call('ui.move',{'x':x+w*start,'y':y+h*.5})
            session_pointer(control,x+w*start,y+h*.5,'down')
            # Cross egui's drag threshold before the 60 individually timed moves.
            session_pointer(control,x+w*(.35 if iteration%2==0 else .65),y+h*.5)
            session_detail(control,photo)
            for step in range(warmups+exposure_steps):
                before=session_execute(control,'develop.get',{'id':photo})['light']['exposure']
                position=.35+.3*(step+1)/(warmups+exposure_steps) if iteration%2==0 else .65-.3*(step+1)/(warmups+exposure_steps)
                session_arm(control,record,'exposure')
                session_pointer(control,x+w*position,y+h*.5)
                sent=control.last_sent_ns
                state=session_detail(control,photo)
                end,digest=session_result(control,directory/f'exposure-{iteration}-{step}.png',sent)
                exposure=session_execute(control,'develop.get',{'id':photo})['light']['exposure']
                if exposure==before:
                    raise RuntimeError(f'slider step {step} had no effect: {exposure}')
                session_sample(record,'exposure',sent,end,digest,step<warmups,step=step-warmups,exposure=exposure,loupe=state['loupe'],image_rect=state['imageRect'],perf=state['perf'],capture=control.last_capture_proof)
            session_pointer(control,x+w*position,y+h*.5,'up')
        for iteration in range(warmups+repetitions):
            session_execute(control,'library.select',{'ids':[photo]})
            session_detail(control,photo)
            selected=ids[1]
            session_arm(control,record,'switch')
            session_execute(control,'library.select',{'ids':[selected]})
            sent=control.last_sent_ns
            state=session_detail(control,selected)
            end,digest=session_result(control,directory/f'switch-{iteration}.png',sent)
            session_sample(record,'switch',sent,end,digest,iteration<warmups,photo=selected,loupe=state['loupe'],image_rect=state['imageRect'],perf=state['perf'],capture=control.last_capture_proof)
        for iteration in range(warmups+repetitions):
            output=directory/f'export-{iteration}.jpg'
            session_arm(control,record,'export')
            result=session_execute(control,'app.export',{'path':str(output),'ids':[photo],'format':'jpeg','longEdge':2048,'quality':90,'background':True})
            sent=control.last_sent_ns
            state=session_wait(control,lambda s: not (s.get('export') or {}).get('running'))
            ready_ns=time.perf_counter_ns()
            end,digest=session_result(control,directory/f'export-{iteration}.png',sent,not_before=ready_ns)
            if max(jpeg_size(output))!=2048:
                raise RuntimeError(f'invalid JPEG export: {result}, {state["export"]}')
            session_sample(record,'export',sent,end,digest,iteration<warmups,jpeg_sha256=file_digest(output),dimensions=jpeg_size(output),perf=state['perf'],capture=control.last_capture_proof)
        record['export_sample']=str(output)
        record['export_oracle']=str(directory/'export-oracle.png')
        # Preview rounding and resampling differ from export (1366 vs1365 pixels).
        # A noisy RAW cannot be compared pixelwise after stretching the preview.
        # Keep the JPEG bound fixed and use the lossless export before its codec.
        record['export_oracle_method']='png-export-same-geometry'
        session_execute(control,'app.export',{'path':record['export_oracle'],'ids':[photo],'format':'png','longEdge':2048,'colorSpace':'srgb','bitDepth':8,'background':True})
        session_wait(control,lambda s:not (s.get('export') or {}).get('running'))
        if png_size(Path(record['export_oracle']))!=jpeg_size(output):
            raise RuntimeError('JPEG and lossless PNG export geometry differ')
        record['export_output_check']=check_export_pixels(record)
        # A fixed-state pixel oracle outside every action clock; use identical source/settings.
        session_execute(control,'library.select',{'ids':[photo]})
        session_execute(control,'develop.set',{'values':{'light.exposure':0.7}})
        session_detail(control,photo)
        oracle=directory/'oracle.png'
        render_preview(control,oracle,photo)
        record['oracle']=str(oracle)
        record['oracle_source']=file_digest(Path(paths[0]))
        state=session_drain(control,record,'before-idle-quit',require_saved=True)
        record['gpu_adapter']=state['perf'].get('gpu')
        record['pre_quit_state']=state
        # No forced process termination is allowed to masquerade as a quit sample.
        control.call('engine.execute',{'command':'app.quit'})
        record['quit_request_ns']=control.last_sent_ns
        record['exit_ns']=session_wait_exit(process)
        if process.returncode!=0:
            raise RuntimeError(f'quit failed: {process.returncode}')
        control.stream.close()
        # Separately measure reopening the already-populated library, including a finished photo frame.
        started=time.perf_counter_ns()
        process,control=spawn(binary,library,profile,None,log_path=directory/'startup.log',on_started=on_started)
        record['process_ids'].append(process.pid)
        control.action_sampler=SessionSampler(control)
        session_detail(control,photo)
        ended,_=session_result(control,directory/'startup-library.png',started)
        record['startup_library_ns']=ended-started
        record['startup_samples']=[dict(duration_ns=ended-started,phase='cold')]
        record['quit_samples']=[dict(duration_ns=record['exit_ns']-record['quit_request_ns'],phase='cold')]
        record['startup_capture']=control.last_capture_proof
        record['startup_state']=control.call('ui.inspect')
        session_drain(control,record,'after-startup-frame')
        for lifecycle in range(3):
            session_drain(control,record,f'before-repeat-quit-{lifecycle}',require_saved=True)
            control.call('engine.execute',{'command':'app.quit'})
            sent=control.last_sent_ns
            exited=session_wait_exit(process)
            if process.returncode!=0:raise RuntimeError(f'quit failed: {process.returncode}')
            record['quit_samples'].append(dict(duration_ns=exited-sent,phase='warm',sent_ns=sent,exit_ns=exited,exit_code=process.returncode))
            control.stream.close()
            if lifecycle==2:break
            started=time.perf_counter_ns()
            process,control=spawn(binary,library,profile,None,log_path=directory/f'startup-repeat-{lifecycle}.log',on_started=on_started)
            record['process_ids'].append(process.pid)
            control.action_sampler=SessionSampler(control)
            session_detail(control,photo)
            ended,_=session_result(control,directory/f'startup-repeat-{lifecycle}.png',started)
            record['startup_samples'].append(dict(duration_ns=ended-started,phase='warm',sent_ns=started,frame_ns=ended,capture=control.last_capture_proof))
        process=None
        record['gpu_processes_after']=session_gpu_processes()
        validate_session(record)
        (directory/'session.json').write_text(json.dumps(record,indent=2)+'\n')
        return record
    except Exception as error:
        record['failure']=str(error)
        (directory/'partial-session.json').write_text(json.dumps(record,indent=2)+'\n')
        raise
    finally:
        observer=getattr(control,'action_sampler',None)
        if observer is not None:observer.finish()
        if process is not None and process.poll() is None:
            stop(process,control)
        control.stream.close()


def session_quit_probe(binary, photo_path, directory, side, pair, trace_quit=False, task="open", gpu_provisional=False, on_started=None):
    """Diagnostic of the previous ui.render→quit path, never a session action claim."""
    directory.mkdir(parents=True,exist_ok=False)
    gpu_before=session_gpu_processes()
    if gpu_before['processes'] and not gpu_provisional:
        (directory/'gpu-processes-rejected.json').write_text(json.dumps(gpu_before,indent=2))
        raise RuntimeError(f'foreign GPU process before quit probe: {gpu_before}')
    launched=time.perf_counter_ns()
    process,control=spawn(binary,directory/'library',directory/'profile',photo_path,log_path=directory/'app.log',on_started=on_started)
    try:
        photo=wait_for_photo(control,process)
        opened=time.perf_counter_ns()
        if task in ('edit','save'):
            session_execute(control,'develop.set',{'values':{'light.exposure':0.7}})
            render_preview(control,directory/'render.png',photo['id'])
            exposure_identity(control,photo['id'],file_digest(photo_path),task)
        elif task=='export':
            session_execute(control,'app.export',{'path':str(directory/'export.jpg'),'ids':[photo['id']],'format':'jpeg','longEdge':2048,'quality':90,'background':False})
            if max(jpeg_size(directory/'export.jpg'))!=2048:raise RuntimeError('quit probe export failed')
        elif task=='open':
            render_preview(control,directory/'render.png',photo['id'])
        else:
            raise ValueError('unknown legacy diagnostic action')
        rendered=time.perf_counter_ns()
        state=control.call('ui.inspect')
        quit_reply_error=None
        try:control.call('engine.execute',{'command':'app.quit'})
        except (RuntimeError,OSError) as error:quit_reply_error=str(error)
        sent=control.last_sent_ns
        if trace_quit:
            with (directory/'quit-backtrace.txt').open('wb') as log:
                subprocess.run(['sudo','-n','gdb','-q','-batch','-p',str(process.pid),'-ex','set pagination off','-ex','thread apply all bt 90','-ex','detach'],stdout=log,stderr=log,timeout=45)
        ended=session_wait_exit(process)
        gpu_after=session_gpu_processes()
        record=dict(side=side,pair=pair,task=task,gpu_provisional=gpu_provisional,profiled=trace_quit,exit_code=process.returncode,success=process.returncode==0,forced_termination=False,quit_reply_error=quit_reply_error,gpu_processes_before=gpu_before,gpu_processes_after=gpu_after,process_ids=[process.pid],launch_ns=launched,photo_ready_ns=opened,render_done_ns=rendered,
                    quit_request_ns=sent,exit_ns=ended,quit_ns=ended-sent,render_ns=rendered-opened,
                    process_ns=ended-launched,pre_quit_state=state,gpu_adapter=state['perf'].get('gpu'))
        if not gpu_provisional and any(p['pid']!=process.pid for p in gpu_after['processes']):
            record['failure']=f'foreign GPU process after quit probe: {gpu_after}'
        (directory/'diagnostic.json').write_text(json.dumps(record,indent=2)+'\n')
        if record.get('failure'):raise RuntimeError(record['failure'])
        return record
    finally:
        if process.poll() is None:stop(process,control)
        control.stream.close()


def session_resume(config, binary_hashes):
    """Reuse completed sessions, preserving the guard and provenance of each acquisition."""
    if not config.get('resume_report'):
        return None
    path=Path(config['resume_report'])
    prior=json.loads(path.read_text())
    def workload(c):return {k:v for k,v in c.items() if k not in ('pair','side','resume_report')}
    if prior.get('schema')!='lightcraft-session-v1' or workload(prior['config'])!=workload(config):
        raise ValueError('resume report workload/revisions differ')
    if prior.get('binary_sha256')!=binary_hashes:
        raise ValueError('resume report binary hashes differ')
    from lightcraft_session_report import validate_session
    keys=set()
    for session in prior['sessions']:
        validate_session(session)
        key=(session['tier'],session['pair'],session['side'])
        if key in keys:raise ValueError(f'duplicate resumed session: {key}')
        keys.add(key)
    return prior


def session_comparison_complete(config,sessions):
    expected={(tier,pair,side) for tier in config['payloads'] for pair in range(config.get('sessions',10)) for side in config.get('sides',('point','main','upstream'))}
    actual=[(s['tier'],s['pair'],s['side']) for s in sessions]
    return len(actual)==len(expected) and set(actual)==expected


def session_main(args):
    import argparse
    from lightcraft_session_report import summarize, markdown
    parser=argparse.ArgumentParser(description='One running LightCraft session per revision/pair; binaries must be built before locking.')
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    options=parser.parse_args(args)
    config=json.loads(options.config.read_text())
    config.setdefault('measurement_method','pre-dispatch-v2')
    pair=config.get('pair',0)
    if not isinstance(pair,int) or not 0<=pair<config.get('sessions',10):
        raise ValueError('pair must be an index in 0..sessions')
    if not config.get('quit_probe') and len(config['payloads'])!=1:
        raise ValueError('one payload tier per lock acquisition is required')
    binary_hashes={side:file_digest(Path(rev['binary'])) for side,rev in config['revisions'].items()}
    prior=session_resume(config,binary_hashes)
    options.out.mkdir(parents=True,exist_ok=False)
    (options.out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    sessions=list(prior['sessions']) if prior else []
    report=dict(discarded_sessions=[],failed_sessions=[],gpu_wait_events=[],provisional_tiers={},gpu_policy=dict(wait_poll_seconds=30,attempt_budget_seconds=1800,during_session_poll_seconds=2),schema='lightcraft-session-v1',publish_scope='fork-point-to-fork-main',config=config,sessions=sessions,publishable=False,
                statistics=dict(resamples=2000,seed=313,bootstrap_unit='paired-session',ratio='point/main',percentiles='linear'),
                environment={key:os.environ.get(key) for key in ('DISPLAY','WGPU_BACKEND','LIGHTCRAFT_GPU_BACKEND','LIGHTCRAFT_GPU_ADAPTER','__GL_SHADER_DISK_CACHE_PATH','CRAFT_BENCH_ISOLATED')},
                timing_scope='control send to first X11 capture proven pixel-identical to the native control PNG; mismatches fall back to the later native capture upper bound',
                driver_sha256=file_digest(Path(__file__)),
                harness_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[3],text=True).strip(),
                binary_sha256=binary_hashes,comparison_complete=False,prior_acquisitions_passed=True)
    if prior:
        for key in ('discarded_sessions','failed_sessions','gpu_wait_events','provisional_tiers'):
            report[key]=prior.get(key,report[key])
        report['prior_acquisitions']=prior.get('prior_acquisitions',[])+[dict(
            path=config['resume_report'],sha256=file_digest(Path(config['resume_report'])),
            harness_revision=prior['harness_revision'],guard=prior.get('guard'),fingerprint=prior.get('fingerprint'))]
        report['prior_acquisitions_passed']=prior.get('prior_acquisitions_passed',True) and prior.get('guard',{}).get('contended') is False
    def checkpoint():
        temporary=options.out/'report.json.tmp'
        temporary.write_text(json.dumps(report,indent=2)+'\n')
        temporary.replace(options.out/'report.json')
    checkpoint()
    display=ensure_display()
    try:
        if config.get('quit_probe'):
            report['schema']='lightcraft-quit-diagnostic-v1'
            report['diagnostic']=[]
            report['diagnostic_only']=True
            report['input_sha256']=file_digest(Path(config['quit_probe']))
            for task in config.get('quit_tasks',['open']):
                for pair in [pair]:
                    order=('point','main','upstream') if pair%2==0 else ('upstream','main','point')
                    for side in order:
                        print(f'quit probe {task} pair {pair} {side}',flush=True)
                        binary=Path(config['revisions'][side]['binary'])
                        record=session_guarded_attempt(report,checkpoint,binary,options.out/f'probe-{task}-{pair}-{side}','legacy-quit',side,pair,
                            lambda directory,provisional,on_started:session_quit_probe(binary,Path(config['quit_probe']),directory,side,pair,task=task,gpu_provisional=provisional,on_started=on_started))
                        report['diagnostic'].append(record)
                        checkpoint()
            report['gpu_adapters']=sorted({r['gpu_adapter'] for r in report['diagnostic'] if r['gpu_adapter']})
            report['gpu_process_checks_passed']=not report['provisional_tiers']
            report['exit_failures']=[dict(side=r['side'],task=r['task'],pair=r['pair'],exit_code=r['exit_code']) for r in report['diagnostic'] if not r['success']]
            report['all_exits_successful']=not report['exit_failures']
            print(f'quit diagnostic: {len(report["diagnostic"])} attempts, {len(report["exit_failures"])} process failures; no forced exits',flush=True)
            checkpoint()
            return 0
        # ABC/CBA blocks keep the primary comparison adjacent, reverse order on alternate pairs.
        for tier,payload in config['payloads'].items():
            for pair in [pair]:
                order=('point','main','upstream') if pair%2==0 else ('upstream','main','point')
                for side in order:
                    if side not in config.get('sides',('point','main','upstream')) or (config.get('side') and config['side']!=side):continue
                    if any((s['tier'],s['pair'],s['side'])==(tier,pair,side) for s in sessions):
                        continue
                    print(f'session {tier} pair {pair} {side}',flush=True)
                    revision=config['revisions'][side]
                    binary=Path(revision['binary'])
                    record=session_guarded_attempt(report,checkpoint,binary,options.out/f'{tier}-{pair}-{side}',tier,side,pair,
                        lambda directory,provisional,on_started:run_session(binary,Path(payload),directory,side,tier,pair,config.get('repetitions',3),config.get('warmups',2),gpu_provisional=provisional,on_started=on_started,exposure_steps=config.get('exposure_steps',10)))
                    sessions.append(record)
                    checkpoint()
        from lightcraft_session_report import check_pixels
        complete_pairs=[p for p in range(config.get('sessions',10)) if all(any(s['side']==side and s['pair']==p for s in sessions) for side in config.get('sides',('point','main','upstream')))]
        paired=[s for s in sessions if s['pair'] in complete_pairs]
        report['pixel_checks']=check_pixels(paired) if paired else []
        # Keep hashes and measured evidence, not thousands of passing native PNGs.
        for accepted in paired:
            if 'directory' not in accepted:continue
            protected={accepted['oracle'],accepted['export_sample'],accepted['export_oracle']}
            for image in Path(accepted['directory']).rglob('*.png'):
                if str(image) not in protected and 'headless-attempt' not in image.name:
                    image.unlink()
        report['rows']=summarize(paired, calibration=config.get('aa_report'), aa=config.get('aa',False)) if paired else []
        report['secondary_pixel_equivalent']=all(c['equivalent'] for c in report['pixel_checks'] if c['side']=='upstream')
        for row in report['rows']:
            row['upstream_equivalent']=all(c['equivalent'] for c in report['pixel_checks'] if c['side']=='upstream' and c['tier']==row['tier'])
        report['gpu_adapters']=sorted({s['gpu_adapter'] for s in sessions})
        report['output_checked']=True
        report['comparison_complete']=session_comparison_complete(config,sessions)
        report['gpu_process_checks_passed']=not report['provisional_tiers']
        # The Rust entry point attaches craft-bench's guard/fingerprint and decides publication.
        checkpoint()
        (options.out/'table.md').write_text(markdown(report['rows']))
        print(markdown(report['rows']))
        return 0
    except Exception as error:
        report['failure']=str(error)
        checkpoint()
        raise
    finally:
        if display is not None:
            display.terminate()
            display.wait(timeout=2)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "session":
        return session_main(sys.argv[2:])
    if len(sys.argv) != 5:
        print("usage: lightcraft_real_app.py BINARY TASK INPUT TARGET_DIR", file=sys.stderr)
        return 2
    binary = Path(sys.argv[1]).resolve()
    task = sys.argv[2]
    input_path = Path(sys.argv[3]).resolve()
    target_dir = Path(sys.argv[4]).resolve()
    if not binary.is_file() or not input_path.is_file():
        raise FileNotFoundError(f"LightCraft binary or input is missing: {binary}, {input_path}")
    display = ensure_display()
    try:
        if task == "verify-save":
            return verify_save(binary, input_path, target_dir)
        if task.startswith("verify-output-"):
            return verify_output(task.removeprefix("verify-output-"), input_path, target_dir)
        return run_task(binary, task, input_path, target_dir)
    finally:
        if display is not None:
            display.terminate()
            display.wait(timeout=2)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"LightCraft real-world journey failed: {error}", file=sys.stderr)
        raise SystemExit(1)
