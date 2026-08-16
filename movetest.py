"""
Mouse-movement test bench. Run this while the game is OPEN and watch the
cursor. Each test moves between two points using a DIFFERENT method, so you
can see which one glides smoothly on YOUR machine.

    python movetest.py

Watch for ~15 seconds. At the end it prints which track you should use.
"""

import ctypes
import time
from ctypes import wintypes

from pynput.mouse import Controller, Button


def _send_rel(dx, dy):
    if dx == 0 and dy == 0:
        return
    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    class _MI(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
    class _IN(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("mi", _MI)]
    s = _IN()
    s.type = INPUT_MOUSE
    s.mi.dx = int(dx)
    s.mi.dy = int(dy)
    s.mi.dwFlags = MOUSEEVENTF_MOVE
    ctypes.windll.user32.SendInput(1, ctypes.byref(s), ctypes.sizeof(_IN))
    time.sleep(0.015)


def _cursor():
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def smooth_absolute(x, y):
    """Glide via many small SetCursorPos steps (no relative input)."""
    sx, sy = _cursor()
    for i in range(1, 51):
        t = i / 50
        ptx = int(sx + (x - sx) * t)
        pty = int(sy + (y - sy) * t)
        ctypes.windll.user32.SetCursorPos(ptx, pty)
        time.sleep(0.01)


def small_chunks_relative(x, y):
    """Glide via many small (<=10px) relative SendInput deltas (bot method)."""
    sx, sy = _cursor()
    gx, gy = int(sx), int(sy)
    dx, dy = x - gx, y - gy
    n = max(1, int(max(abs(dx), abs(dy)) / 10) + 1)
    fx, fy = dx / n, dy / n
    for _ in range(n):
        gx += fx
        gy += fy
        ex = int(gx) - int(gx - fx)
        ey = int(gy) - int(gy - fy)
        if ex or ey:
            _send_rel(ex, ey)


def big_jumps_relative(x, y):
    """Few big relative SendInput jumps (the old 'teleport' behaviour)."""
    sx, sy = _cursor()
    gx, gy = int(sx), int(sy)
    for i in range(1, 6):
        _send_rel(int((x - gx) / 5), int((y - gy) / 5))


def main():
    ctl = Controller()
    sx, sy = ctl.position
    targets = [(sx - 300, sy), (sx + 300, sy), (sx, sy + 200), (sx, sy - 200)]

    print("=" * 56)
    print("  Watches the cursor glide. Note which run is SMOOTHEST.")
    print("  Watch in the GAME if possible (clear a few screens of water).")
    print("=" * 56)
    input("Press Enter to start Test 1 (watch closely)...")

    tests = [("SMOOTH absolute glide", smooth_absolute),
             ("SMALL-chunk relative glide", small_chunks_relative),
             ("BIG-jump relative (old buggy)", big_jumps_relative)]
    results = []
    for name, fn in tests:
        input(f"\nTest: {name}\nPress Enter when cursor is back at center...")
        print("  moving... watch it!")
        time.sleep(1.0)
        for tx, ty in targets:
            fn(tx, ty)
            time.sleep(0.1)
        time.sleep(1.0)
        results.append(name)
    ctl.position = (sx, sy)

    print("\n" + "=" * 56)
    print("Results summary:")
    for r in results:
        print("   ", r)
    print("=" * 56)
    print("Tell the bot dev: which one looked SMOOTH (no teleports) and")
    print("which one landed accurately. Hit ESC to exit whenever.")


if __name__ == "__main__":
    main()