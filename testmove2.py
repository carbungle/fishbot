"""
Movement-only test, using the knowledge from debugging:

  * Relative SendInput deltas are what the game cursor actually follows.
  * An absolute SetCursorPos snap at the end = the visible "teleport/jump".
  * So this test glides using RELATIVE deltas ONLY (no SetCursorPos).

It moves through the real 4 `seq_locations` from cfg.json several times,
each pass with a different (steps, delay) config. Watch the cursor in-game
and judge how SMOOTH each pass is and whether it lands on the right spots.

    python testmove2.py

No clicks are sent. F8 = start next pass, ESC = quit.
"""

import ctypes
import json
import os
import time
from ctypes import wintypes

from pynput.mouse import Controller


def _send_rel(dx, dy, sleep_t):
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
    time.sleep(sleep_t)


def glide_relative(x, y, steps, delay):
    """Pure relative glide to (x,y). No SetCursorPos anywhere."""
    ctl = Controller()
    sx, sy = ctl.position
    if abs(sx - x) < 2 and abs(sy - y) < 2:
        return
    chunk = []
    gx, gy = sx, sy
    for i in range(1, steps + 1):
        t = i / steps
        px = int(sx + (x - sx) * t)
        py = int(sy + (y - sy) * t)
        chunk.append((px - gx, py - gy))
        gx, gy = px, py
    for dx, dy in chunk:
        _send_rel(dx, dy, delay)


def load_locations() -> list:
    path = "cfg.json"
    if not os.path.exists(path):
        print("No cfg.json here. Run from the fishingbot folder.")
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        locs = data.get("seq_locations", [])
        return [tuple(l) for l in locs] if locs else []
    except Exception as ex:
        print("Could not read cfg.json:", ex)
        return []


CONFIGS = [
    ("A  rel 40 steps 12ms  (your current bot config)", 40, 0.012),
    ("B  rel 60 steps 8ms", 60, 0.008),
    ("C  rel 30 steps 15ms", 30, 0.015),
    ("D  rel 80 steps 6ms", 80, 0.006),
]


def main():
    locs = load_locations()
    if len(locs) < 4:
        print("Need 4 seq_locations in cfg.json first.")
        return

    from pynput import keyboard
    state = {"idx": 0, "run": False, "done": False}

    def on_press(key):
        try:
            name = key.name
        except AttributeError:
            name = key.char
        if name == "esc":
            state["done"] = True
            return False
        if name == "f8":
            state["idx"] += 1
            state["run"] = True
        return True

    lst = keyboard.Listener(on_press=on_press)
    lst.daemon = True
    lst.start()

    print("=" * 62)
    print("Movement-only test (RELATIVE deltas, NO SetCursorPos).")
    print("Make sure Roblox is focused. No clicks are sent.")
    print("")
    print("Park the cursor anywhere, then press F8 to run each pass.")
    print("Judge each pass: SMOOTH or JITTERY/JUMPY, and does it land on")
    print("the right 4 spots?")
    print("=" * 62)

    while not state["done"]:
        if state["run"]:
            state["run"] = False
            i = (state["idx"] - 1) % len(CONFIGS)
            name, steps, delay = CONFIGS[i]
            print(f"\n>>> F8 #{state['idx']} -> {name}")
            time.sleep(1.0)
            for n, (x, y) in enumerate(locs, 1):
                print(f"  spot {n} ({x},{y})")
                glide_relative(x, y, steps, delay)
                time.sleep(0.6)
            print("  done. F8 = next config, ESC = quit.")
        time.sleep(0.03)

    lst.stop()
    print("Quit.")


if __name__ == "__main__":
    main()