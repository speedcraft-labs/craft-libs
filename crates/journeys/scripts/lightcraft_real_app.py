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


def spawn(binary: Path, library: Path, profile: Path, photo_path: Path | None, *, log_path: Path | None = None):
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
    command = [str(binary), "--library", str(library), "--no-demo", "--control", str(port)]
    if photo_path is not None:
        command.append(str(photo_path))
    with log_path.open("wb") if log_path else open(os.devnull, "wb") as log:
        process = subprocess.Popen(command, cwd=profile, env=env, stdout=log, stderr=log)
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
            time.sleep(0.02)
    if control is None:
        process.terminate()
        process.wait(timeout=5)
        raise TimeoutError("LightCraft control channel did not start")
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


def session_execute(control, command, params=None):
    return control.call('engine.execute', {'command': command, 'params': params or {}})


def session_idle(state):
    perf = state['perf']
    return all(perf.get(k) == 0 for k in ('renderQueue', 'rendersInFlight', 'pendingSlots'))


def session_wait(control, predicate, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = control.call('ui.inspect')
        if predicate(state):
            return state
        time.sleep(.005)
    raise TimeoutError(f'LightCraft frame state did not converge: {state}')


def session_frame(control, path):
    # Never use ui.render: it is a separate render, not the visible result of the action.
    control.call('ui.screenshot', {'path': str(path), 'headless': False})
    end = time.perf_counter_ns()
    if min(png_size(path)) <= 0:
        raise RuntimeError('empty native frame')
    return end, file_digest(path)


def session_detail(control, photo):
    def ready(state):
        loupe = state.get('loupe') or {}
        if loupe.get('failed'):
            raise RuntimeError(f'preview failed: {loupe}')
        return state.get('active') == photo and loupe.get('photo') == photo and loupe.get('source') in ('render', 'cached') and not loupe.get('pending') and session_idle(state)
    return session_wait(control, ready)


def session_sample(record, action, sent, end, digest, warmup, **evidence):
    record['samples'].append(dict(action=action, sent_ns=sent, frame_ns=end, duration_ns=end-sent,
                                  frame_sha256=digest, warmup=warmup, checked=True, evidence=evidence))


def session_pointer(control, x, y, kind='move'):
    # ui.pointer coordinates are relative to imageRect, including points outside the photo.
    rect = control.call('ui.inspect')['imageRect']
    if not rect:
        raise RuntimeError('pointer gesture needs a displayed photo')
    control.call('ui.pointer', {'events': [{'kind': kind, 'x': (x-rect[0])/rect[2], 'y': (y-rect[1])/rect[3]}]})


def session_grid(control, ids, directory):
    """Visit every grid thumbnail, retaining a native frame and checking actual image content."""
    from PIL import Image, ImageStat
    seen = set()
    frames = []
    session_execute(control, 'view.squareGrid')
    control.call('ui.set', {'thumbSize': 100})
    previous_scroll = None
    for page in range(len(ids) + 5):
        state = session_wait(control, session_idle)
        widgets = control.call('ui.widgets', {'filter': 'thumb:'})
        visible = []
        for w in widgets:
            if not w['id'].startswith('thumb:'):
                continue
            ident = int(w['id'].split(':')[1])
            x,y,width,height = w['rect']
            if ident in ids and y >= 0 and y+height <= state['window'][1] and x >= 0:
                visible.append((ident, (x,y,width,height)))
        if not visible:
            raise RuntimeError('no fully visible grid thumbnails')
        # With no pending renders, require resident thumbnail textures as well as non-placeholder pixels.
        if state['perf']['thumbTextures'] < len(visible):
            time.sleep(.02)
            continue
        path = directory / f'grid-{page}.png'
        end,digest = session_frame(control,path)
        image = Image.open(path).convert('RGB')
        ppp = state['pixelsPerPoint']
        for ident,(x,y,w,h) in visible:
            # Stay inside the photo, away from its caption, border and selection markers.
            crop=image.crop(tuple(round(v*ppp) for v in (x+w*.3,y+h*.25,x+w*.7,y+h*.55)))
            if max(ImageStat.Stat(crop).stddev) < 1.0:
                raise RuntimeError(f'blank/placeholder thumbnail {ident} on page {page}')
            seen.add(ident)
        frames.append(dict(path=str(path), sha256=digest, ids=[i for i,_ in visible]))
        if seen == set(ids):
            return end,digest,frames
        scroll = state.get('scroll',{}).get('grid')
        if scroll == previous_scroll and page > 0:
            raise RuntimeError(f'grid stopped before all thumbnails: {len(seen)}/{len(ids)}')
        previous_scroll = scroll
        control.call('ui.move', {'x': state['window'][0]/2, 'y': state['window'][1]/2})
        control.call('ui.scroll', {'dy': -state['window'][1]*.55})
    raise RuntimeError(f'not all thumbnails shown: {len(seen)}/{len(ids)}')


def run_session(binary, payload, directory, side, tier, pair, repetitions, warmups):
    from lightcraft_session_report import validate_session
    directory.mkdir(parents=True,exist_ok=False)
    library,profile = directory/'library',directory/'profile'
    log_path=directory/'app.log'
    record=dict(side=side,tier=tier,pair=pair,samples=[],launch_ns=time.perf_counter_ns())
    process,control=spawn(binary,library,profile,None,log_path=log_path)
    try:
        state=control.call('ui.inspect')
        record['interactive_ns'],_=session_frame(control,directory/'interactive.png')
        control.call('ui.set', {'settings': {'previewLimit': 0}})
        paths=[str(p) for p in sorted(payload.iterdir()) if p.is_file() and not p.name.startswith('.')]
        if not paths:
            raise ValueError('empty RAW payload')
        # Warm import and repeat real import after removing catalog records only; originals stay.
        for iteration in range(warmups+repetitions):
            if iteration:
                session_execute(control,'photo.deletePermanently',{'ids': ids})
                control.call('ui.move', {'x': 600, 'y': 350})
                control.call('ui.scroll', {'dy': 100000})
            result=session_execute(control,'library.import',{'paths':paths,'mode':'add'})
            sent=control.last_sent_ns
            ids=result['imported']
            if result.get('failed') or len(ids)!=len(paths) or result.get('duplicates'):
                raise RuntimeError(f'incomplete import: {result}')
            grid_dir=directory/f'import-{iteration}'
            grid_dir.mkdir()
            end,digest,frames=session_grid(control,ids,grid_dir)
            session_sample(record,'import',sent,end,digest,iteration<warmups,imported=len(ids),frames=frames)
        record['photo_ids']=ids
        photo=ids[0]
        for iteration in range(warmups+repetitions):
            session_execute(control,'library.select',{'ids':[photo]})
            session_execute(control,'view.detail')
            sent=control.last_sent_ns
            state=session_detail(control,photo)
            end,digest=session_frame(control,directory/f'preview-{iteration}.png')
            session_sample(record,'preview',sent,end,digest,iteration<warmups,loupe=state['loupe'],image_rect=state['imageRect'])
            session_execute(control,'view.squareGrid')
        session_execute(control,'view.detail')
        session_detail(control,photo)
        # A held real slider gesture, one acknowledged pointer movement and resulting frame per step.
        slider=next(w for w in control.call('ui.widgets',{'filter':'slider:light.exposure'}) if w['id']=='slider:light.exposure')
        x,y,w,h=slider['rect']
        for iteration in range(warmups+repetitions):
            session_pointer(control,x+w*(.35 if iteration%2==0 else .65),y+h*.5,'down')
            for step in range(60):
                before=session_execute(control,'develop.get',{'id':photo})['light']['exposure']
                position=.35+.3*(step+1)/60 if iteration%2==0 else .65-.3*(step+1)/60
                session_pointer(control,x+w*position,y+h*.5)
                sent=control.last_sent_ns
                state=session_detail(control,photo)
                end,digest=session_frame(control,directory/f'exposure-{iteration}-{step}.png')
                exposure=session_execute(control,'develop.get',{'id':photo})['light']['exposure']
                if exposure==before:
                    raise RuntimeError(f'slider step {step} had no effect: {exposure}')
                session_sample(record,'exposure',sent,end,digest,iteration<warmups,step=step,exposure=exposure,loupe=state['loupe'])
            session_pointer(control,x+w*position,y+h*.5,'up')
        for iteration in range(warmups+repetitions):
            selected=ids[1+iteration%(len(ids)-1)]
            session_execute(control,'library.select',{'ids':[selected]})
            sent=control.last_sent_ns
            state=session_detail(control,selected)
            end,digest=session_frame(control,directory/f'switch-{iteration}.png')
            session_sample(record,'switch',sent,end,digest,iteration<warmups,photo=selected,loupe=state['loupe'])
        for iteration in range(warmups+repetitions):
            output=directory/f'export-{iteration}.jpg'
            result=session_execute(control,'app.export',{'path':str(output),'ids':[photo],'format':'jpeg','longEdge':2048,'quality':90,'background':True})
            sent=control.last_sent_ns
            state=session_wait(control,lambda s: not (s.get('export') or {}).get('running'))
            end,digest=session_frame(control,directory/f'export-{iteration}.png')
            if max(jpeg_size(output))!=2048:
                raise RuntimeError(f'invalid JPEG export: {result}, {state["export"]}')
            session_sample(record,'export',sent,end,digest,iteration<warmups,jpeg_sha256=file_digest(output),dimensions=jpeg_size(output))
        state=control.call('ui.inspect')
        record['gpu_adapter']=state['perf'].get('gpu')
        record['pre_quit_state']=state
        # No forced process termination is allowed to masquerade as a quit sample.
        control.call('engine.execute',{'command':'app.quit'})
        record['quit_request_ns']=control.last_sent_ns
        process.wait(timeout=150)
        record['exit_ns']=time.perf_counter_ns()
        if process.returncode!=0:
            raise RuntimeError(f'quit failed: {process.returncode}')
        control.stream.close()
        # Separately measure reopening the already-populated library, including a finished photo frame.
        started=time.perf_counter_ns()
        process,control=spawn(binary,library,profile,None,log_path=directory/'startup.log')
        session_detail(control,selected)
        ended,_=session_frame(control,directory/'startup-library.png')
        record['startup_library_ns']=ended-started
        record['startup_state']=control.call('ui.inspect')
        stop(process,control)
        process=None
        for log in (log_path,directory/'startup.log'):
            if 'rendering headlessly' in log.read_text(errors='replace'):
                raise RuntimeError('native screenshot fell back to headless rendering')
        validate_session(record)
        (directory/'session.json').write_text(json.dumps(record,indent=2)+'\n')
        return record
    finally:
        if process is not None and process.poll() is None:
            stop(process,control)
        control.stream.close()


def session_main(args):
    import argparse
    from lightcraft_session_report import summarize, markdown
    parser=argparse.ArgumentParser(description='One running LightCraft session per revision/pair; binaries must be built before locking.')
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    options=parser.parse_args(args)
    config=json.loads(options.config.read_text())
    options.out.mkdir(parents=True,exist_ok=False)
    (options.out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    sessions=[]
    report=dict(schema='lightcraft-session-v1',config=config,sessions=sessions,publishable=False)
    def checkpoint():
        (options.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    checkpoint()
    display=ensure_display()
    try:
        # ABC/CBA blocks keep the primary comparison adjacent, reverse order on alternate pairs.
        for tier,payload in config['payloads'].items():
            for pair in range(config.get('sessions',10)):
                order=('point','main','upstream') if pair%2==0 else ('upstream','main','point')
                for side in order:
                    print(f'session {tier} pair {pair} {side}',flush=True)
                    revision=config['revisions'][side]
                    record=run_session(Path(revision['binary']),Path(payload),options.out/f'{tier}-{pair}-{side}',side,tier,pair,config.get('repetitions',3),config.get('warmups',2))
                    sessions.append(record)
                    checkpoint()
        report['rows']=summarize(sessions)
        report['gpu_adapters']=sorted({s['gpu_adapter'] for s in sessions})
        report['output_checked']=True
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
