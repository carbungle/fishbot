"""
In-game movement/click test (CENTER-ANCHORED RELATIVE).

The game locks/hides the cursor (Roblox MouseBehavior.LockCenter), so the
game cursor is pinned at the CENTER of the window, NOT where the OS mouse is.
To hit an (x,y) on screen we send relative deltas measured from screen center:

    delta = target - center

This test runs that method with different chunk sizes so you can pick the
smoothest one that clicks the right spots.

    python testcycle.py

Controls:
    F8  - test the next method on the 4 locations
    ESC - quit
"""

import ctypes
import json
import os
import time
from ctypes import wintypes


def _cursor():
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _center():
    sw = ctypes.windll.user32.GetSystemMetrics(0)  # SM_CXSCREEN
    sh = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return sw // 2, sh // 2


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
    s.mi.dwFlags = 0x0001  # MOUSEEVENTF_MOVE
    ctypes.windll.user32.SendInput(1, ctypes.byref(s), ctypes.sizeof(_IN))
    time.sleep(sleep_t)


def _click():
    from pynput.mouse import Controller, Button
    ctl = Controller()
    ctl.press(Button.left)
    time.sleep(0.05)
    ctl.release(Button.left)
    time.sleep(0.1)


class SyncRelative:
    """Anchor once (sync) to the OS cursor, then track via relative deltas."""

    def __init__(self):
        self.vx, self.vy = _cursor()

    def sync(self):
        self.vx, self.vy = _cursor()

    def move(self, x, y, chunk, sleep_t):
        gx, gy = self.vx, self.vy
        if abs(gx - x) < 2 and abs(gy - y) < 2:
            return
        dx, dy = x - gx, y - gy
        n = max(1, int(max(abs(dx), abs(dy)) / chunk) + 1)
        fx, fy = dx / n, dy / n
        for _ in range(n):
            gx += fx
            gy += fy
            ex = int(gx) - int(gx - fx)
            ey = int(gy) - int(gy - fy)
            if ex or ey:
                _send_rel(ex, ey, sleep_t)
        ex, ey = int(x) - int(gx), int(y) - int(gy)
        if ex or ey:
            _send_rel(ex, ey, sleep_t)
        self.vx, self.vy = int(x), int(y)


_tracked = SyncRelative()


METHODS = [
    ("TEST30 SYNC-REL 10px 10ms", 10, 0.010),
    ("TEST31 SYNC-REL 15px 8ms", 15, 0.008),
    ("TEST32 SYNC-REL 20px 6ms", 20, 0.006),
    ("TEST33 SYNC-REL 30px 6ms", 30, 0.006),
]


def load_locations() -> list:
    path = "cfg.json"
    if not os.path.exists(path):
        print("No cfg.json found here. Run from the fishingbot folder.")
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        locs = data.get("seq_locations", [])
        return [tuple(l) for l in locs] if locs else []
    except Exception as ex:
        print("Could not read cfg.json:", ex)
        return []


def main():
    locs = load_locations()
    if len(locs) < 4:
        print("Need 4 seq_locations in cfg.json first. Run: python main.py --set-seq")
        return

    from pynput import keyboard
    state = {"idx": 0, "running": False, "done": False}

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
            state["running"] = True
        return True

    lst = keyboard.Listener(on_press=on_press)
    lst.daemon = True
    lst.start()

    print("=" * 60)
    print("In-game movement/click test (SYNC-RELATIVE).")
    print("Park your cursor somewhere consistent (e.g. over the water),")
    print("then press F8. Each F8 = one method tried on all 4 locations.")
    print("")
    print("JUDGE EACH ONE:")
    print("  A) smooth or rough?  B) do the 4 clicks land on the spots?")
    print("Report e.g. 'TEST30 smooth, clicks land right'")
    print("=" * 60)

    while not state["done"]:
        if state["running"]:
            state["running"] = False
            i = (state["idx"] - 1) % len(METHODS)
            name, chunk, sleep_t = METHODS[i]
            print(f"\n>>> F8 #{state['idx']} -> {name}")
            # anchor NOW (cursor is where he parked it, game focused)
            _tracked.sync()
            print(f"  anchored at ({_tracked.vx}, {_tracked.vy})")
            time.sleep(1.0)
            for n, (x, y) in enumerate(locs, 1):
                print(f"  loc {n} ({x},{y})")
                _tracked.move(x, y, chunk, sleep_t)
                time.sleep(0.2)
                _click()
            print("  done. next F8 = next method, ESC = quit.")
        time.sleep(0.03)

    lst.stop()
    print("Quit.")


if __name__ == "__main__":
    main()