#!/usr/bin/env python3
"""Write the monotonic time when an X11 window with the given title is mapped."""

from __future__ import annotations

import ctypes
import ctypes.util
from pathlib import Path
import sys
import time


class XMapEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("event", ctypes.c_ulong),
        ("window", ctypes.c_ulong),
        ("override_redirect", ctypes.c_int),
    ]


class XCreateEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("parent", ctypes.c_ulong),
        ("window", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("border_width", ctypes.c_int),
        ("override_redirect", ctypes.c_int),
    ]


class XPropertyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("atom", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("state", ctypes.c_int),
    ]


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: x11_map_watch.py TITLES READY_FILE RESULT_FILE", file=sys.stderr)
        return 2
    titles = tuple(title for title in sys.argv[1].split(",") if title)
    ready_path, result_path = sys.argv[2:]
    library = ctypes.util.find_library("X11")
    if library is None:
        raise RuntimeError("libX11 is required to observe a mapped startup window")
    x11 = ctypes.CDLL(library)
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XSelectInput.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]
    x11.XSelectInput.restype = ctypes.c_int
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    x11.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
    x11.XFetchName.restype = ctypes.c_int
    x11.XFree.argtypes = [ctypes.c_void_p]

    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError("could not connect to DISPLAY to observe the startup window")
    root = x11.XDefaultRootWindow(display)
    # SubstructureNotifyMask: receive MapNotify for children of the root window.
    x11.XSelectInput(display, root, 1 << 19)
    x11.XFlush(display)
    Path(ready_path).write_text("ready\n")

    event = ctypes.create_string_buffer(192)
    mapped_windows: set[int] = set()

    def record_if_target(window: int) -> bool:
        name = ctypes.c_char_p()
        if x11.XFetchName(display, window, ctypes.byref(name)) == 0 or not name:
            return False
        try:
            window_name = name.value.decode("utf-8", errors="replace")
            if not any(title in window_name for title in titles):
                return False
            Path(result_path).write_text(f"{time.perf_counter_ns()}\n")
            return True
        finally:
            x11.XFree(name)

    while True:
        x11.XNextEvent(display, event)
        event_type = ctypes.cast(event, ctypes.POINTER(ctypes.c_int)).contents.value
        if event_type == 16:  # CreateNotify
            created = ctypes.cast(event, ctypes.POINTER(XCreateEvent)).contents
            # A window manager may reparent the app window below a root child. Subscribe to
            # descendants too, and watch title changes for windows whose name arrives after map.
            x11.XSelectInput(display, created.window, (1 << 19) | (1 << 22))  # SubstructureNotifyMask | PropertyChangeMask
            x11.XFlush(display)
            continue
        if event_type == 19:  # MapNotify
            mapped = ctypes.cast(event, ctypes.POINTER(XMapEvent)).contents
            mapped_windows.add(mapped.window)
            if record_if_target(mapped.window):
                return 0
            continue
        if event_type == 28:  # PropertyNotify
            changed = ctypes.cast(event, ctypes.POINTER(XPropertyEvent)).contents
            if changed.window in mapped_windows and record_if_target(changed.window):
                return 0


if __name__ == "__main__":
    raise SystemExit(main())
