"""
Roblox fishing macro (auto-loop, text-change based):

  1. Clicks the water to cast.
  2. Waits for the fishing menu to appear (bottom half of the screen).
  3. The moment the menu pops up, HOLDS left click.
  4. When the text on the menu changes (e.g. "reel in" -> "fish is running"),
     it LETS GO right away.
  5. When the text changes back, it HOLDS again.
  6. When the catch ends (menu disappears), it clicks the water and repeats.

Setup:
    python main.py --calibrate         # click 2 corners of the fishing bar
    python main.py --set-cast          # click the water spot to cast from
    python main.py --set-text          # (optional) click 2 corners of the TEXT
    python main.py --set-color         # (alt mode) click 2 corners of the
                                       #   region that changes colour; releases
                                       #   when it turns a different colour and
                                       #   holds off 5s before resuming

Run:
    python main.py --preview           # live preview window (tune thresholds)
    python main.py                     # run the auto-fisher
    python main.py --demo              # run without touching the mouse

Controls (pynput global hotkeys):
    F8    - toggle auto-fishing on/off
    F1    - switch mode: NORMAL (1) / BOX (2, box + maintenance cycle)
    ESC   - quit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

import ctypes as _ctypes

VERSION = "27"
UPDATE_BASE = "https://raw.githubusercontent.com/carbungle/fishbot/main"
UPDATE_FILES = ["main.py", "auth.py", "VERSION.txt", "fisher_gui.py", "fisher.bat", "run.bat"]
AUTO_LEAVE_ENABLED = False


def _fetch(url: str, timeout: int = 15) -> bytes:
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _local_version() -> str:
    return VERSION


def check_update(force: bool = False) -> bool:
    """Check for (and apply) a newer version. Returns True if the files were
    replaced and the user should restart. Never touches users.dat/session.dat/
    cfg.json, so credentials and PC locks survive updates. force=True skips the
    version comparison and re-downloads anyway."""
    base = UPDATE_BASE.rstrip("/")
    apply = force
    remote = ""
    try:
        remote = _fetch(base + "/VERSION.txt").decode("utf-8").strip()
    except Exception:
        return False
    if apply is False:
        try:
            if int(remote) <= int(_local_version()):
                return False
        except Exception:
            if remote == _local_version():
                return False
    if apply is False:
        print(f"Updating {_local_version()} -> {remote} ...")
    elif apply is True:
        print(f"Checking {base}/VERSION.txt ... latest is {remote}.")
    here = os.path.dirname(os.path.abspath(__file__))
    ok, changed = True, []
    for name in UPDATE_FILES:
        try:
            data = _fetch(base + "/" + name)
            tmp = os.path.join(here, name + ".new")
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, os.path.join(here, name))
            changed.append(name)
        except Exception:
            ok = False
            break
    if ok:
        print("Update applied. Please restart the script.")
        return True
    print("Update failed; keeping the current version.")
    return False


def _enable_ansi():
    if os.name != "nt":
        return
    try:
        h = _ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = _ctypes.c_uint32()
        if _ctypes.windll.kernel32.GetConsoleMode(h, _ctypes.byref(mode)):
            _ctypes.windll.kernel32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


BLUE = "\x1b[94m"
GREEN = "\x1b[92m"
RED = "\x1b[91m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"
COUNTER_FILE = os.path.join("data", "fish_counter.txt")
_COUNTER_OLD = "fish_counter.txt"


def _info(msg):
    print(f"{BLUE}{msg}{RESET}")


def _running_msg(msg):
    print(f"{GREEN}{msg}{RESET}")


def _stopped_msg(msg):
    print(f"{RED}{msg}{RESET}")


def _counter_path() -> str:
    # data/fish_counter.txt with fallback auto-migrate
    if os.path.exists(COUNTER_FILE):
        return COUNTER_FILE
    if os.path.exists(_COUNTER_OLD):
        try:
            os.makedirs(os.path.dirname(COUNTER_FILE), exist_ok=True)
            import shutil
            shutil.move(_COUNTER_OLD, COUNTER_FILE)
        except:
            pass
        return COUNTER_FILE if os.path.exists(COUNTER_FILE) else _COUNTER_OLD
    return COUNTER_FILE

def load_total_caught() -> int:
    """Load the all-time fish counter saved on disk (survives restarts)."""
    for p in (COUNTER_FILE, _COUNTER_OLD):
        try:
            with open(p) as f:
                v = int(f.read().strip() or "0")
                # migrate if was old
                if p == _COUNTER_OLD and not os.path.exists(COUNTER_FILE):
                    try:
                        os.makedirs(os.path.dirname(COUNTER_FILE), exist_ok=True)
                        import shutil
                        shutil.move(p, COUNTER_FILE)
                    except: pass
                return v
        except Exception:
            continue
    return 0


def save_total_caught(n: int):
    try:
        os.makedirs(os.path.dirname(COUNTER_FILE), exist_ok=True)
    except: pass
    try:
        with open(_counter_path(), "w") as f:
            f.write(str(n))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Tunables - adjust for your specific Roblox game if needed. The --preview
# window visualizes what the detector sees so you can tune the thresholds.
# ---------------------------------------------------------------------------


@dataclass
class Config:
    # --- Menu detection -----------------------------------------------------
    # The fishing menu is detected when the region changes a lot from the
    # "water" background learned right after casting. Color-based checks are
    # only a fallback. Tune the thresholds if the menu isn't detected.
    bg_learn_frames: int = 15        # frames to learn the no-menu background
    bg_change_frac: float = 0.50     # fraction of pixels that must change
    bg_change_px: int = 60           # per-channel diff to count as changed
    fish_color: Tuple[int, int, int] = (255, 200, 40)   # fallback: fish icon
    fish_tol: int = 90
    bar_color: Tuple[int, int, int] = (255, 255, 255)   # fallback: catch bar/text
    bar_tol: int = 70

    # --- Text-change detection ---------------------------------------------
    # Both text states share one colour, so we detect a CHANGE in the text
    # region instead. text_region is RELATIVE to the menu region
    # (x0, y0, width, height). None = the whole menu region.
    text_region: Optional[Tuple[int, int, int, int]] = None
    text_change_px: int = 45         # per-channel diff to count a pixel as changed
    text_motion_px: int = 8          # smaller threshold to detect animation-in
    text_latch_frames: int = 1       # frames to confirm a change (release fast)
    text_resume_frames: int = 1      # frames of normal text before re-holding
    text_settle_frames: int = 10     # stable frames required before snapshotting
    text_min_trigger: float = 0.04   # lowest change fraction that counts

    # --- Text-template matching (alt mode) -----------------------------------
    # Instead of change-detection, save a reference crop of the text region for
    # each state with:  python main.py --snap-text hold|about|running
    # (while that text is on screen). When all three exist, the bot matches the
    # live region to them and releases ONLY when "running" is the best match.
    text_ref_images: dict = field(default_factory=dict)   # state -> file path
    menu_via_text: bool = True        # menu UP only while text is visible

    # --- Color-change detection --------------------------------------------
    # Alternative to text detection. Hold while a calibrated region keeps its
    # original colour; the instant it turns a different colour, release and
    # stay released for color_release_seconds, then resume holding.
    color_region: Optional[Tuple[int, int, int, int]] = None   # absolute rect
    color_change_px: int = 40        # per-channel diff to count a pixel changed
    color_change_frac: float = 0.15  # fraction of region that must change
    color_release_seconds: float = 2.0   # hold off after a colour change
    color_settle_frames: int = 5     # frames before snapshotting original colour

    # --- State machine ------------------------------------------------------
    min_wait: float = 10.0    # do not recast sooner than this after casting
    max_wait: float = 30.0    # if the menu never shows, recast after this
    menu_confirm_frames: int = 3     # frames of menu pixels to trigger fishing
    hold_delay: float = 0.3          # wait this long after menu opens before holding
    end_idle_frames: int = 8         # frames with NO menu pixels = catch over
    post_catch_pause: float = 1.5    # seconds to wait after a catch before recast
    loop_hz: int = 60

    # --- Screen data (set by --calibrate / --set-cast / --set-text) ---------
    region: Optional[Tuple[int, int, int, int]] = None   # (x,y,w,h) menu area
    cast_pos: Optional[Tuple[int, int]] = None           # (x,y) water to cast

    # --- Post-catch sequence -------------------------------------------------
    # After every so many catches: press F, click the first 3 calibrated
    # locations, press T, click the 4th, then return the mouse to the session
    # water spot captured on F8.
    seq_every_n_catches: int = 3
    seq_locations: list = field(default_factory=list)   # 4 absolute (x,y)

    # --- Mode 2 (F1 toggle: "box + maintenance") -----------------------------
    # Every mode2_store_every_n_catches catches: store in the trunk (F +
    # 4-spot sequence using mode2_store_locations).  Every
    # mode2_every_n_catches catches, run the maintenance cycle:
    #   press 2, hold left click mode2_hold_seconds, press 2 again,
    #   press F + click the first 6 mode2_seq_locations, press T + click the
    #   7th, press 2 again, return to the water spot, click once (throw the
    #   box out), press 1, click again to continue.
    # Startup also throws the box: click once, press 1, click again.
    mode2_every_n_catches: int = 15
    mode2_store_every_n_catches: int = 1
    mode2_hold_seconds: float = 20.0
    mode2_seq_locations: list = field(default_factory=list)  # 7 absolute (x,y)
    mode2_store_locations: list = field(default_factory=list)  # 4 absolute (x,y)

    # --- Debug --------------------------------------------------------------
    preview: bool = False
    demo: bool = False


# ---------------------------------------------------------------------------
# Screen capture (mss)
# ---------------------------------------------------------------------------

class Capture:
    def __init__(self, region: Tuple[int, int, int, int]):
        import mss
        self.sct = mss.mss()
        self.region = region

    def grab(self) -> np.ndarray:
        raw = self.sct.grab(
            {"left": self.region[0], "top": self.region[1],
             "width": self.region[2], "height": self.region[3]})
        frame = np.frombuffer(raw.raw, dtype=np.uint8).reshape(
            raw.height, raw.width, -1)[:, :, :4].copy()
        return frame  # BGRA


# ---------------------------------------------------------------------------
# Menu detection
# ---------------------------------------------------------------------------

def colour_present(frame: np.ndarray, color, tol) -> bool:
    b, g, r = color
    f = frame.astype(int)
    return bool(((np.abs(f[:, :, 0] - b) < tol)
                 & (np.abs(f[:, :, 1] - g) < tol)
                 & (np.abs(f[:, :, 2] - r) < tol)).any())


def menu_visible(cfg: Config, frame) -> bool:
    """Is the fishing menu showing? True if the fish or bar colour appears."""
    return (colour_present(frame, cfg.fish_color, cfg.fish_tol)
            or colour_present(frame, cfg.bar_color, cfg.bar_tol))


class MenuDetector:
    """Detects the menu by learning the background (water) after casting and
    flagging when a big chunk of the region changes. Colour checks are only a
    fallback for games where the background is unstable."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.bg = None
        self.learned = 0

    def reset(self):
        self.bg = None
        self.learned = 0

    def step(self, frame: np.ndarray) -> bool:
        """Returns True when the menu is present. Also learns the background
        for the first bg_learn_frames calls."""
        if self.bg is None:
            self.bg = frame.astype(np.int16).copy()
            self.learned = 1
            return False

        if self.learned < self.cfg.bg_learn_frames:
            # keep averaging the background so moving water settles down
            self.bg = self.bg * (self.learned / (self.learned + 1)) \
                + frame.astype(np.int16) * (1 / (self.learned + 1))
            self.learned += 1
            return False

        diff = np.abs(frame.astype(np.int16) - self.bg)
        changed = np.mean(diff.max(axis=2) > self.cfg.bg_change_px)
        return changed > self.cfg.bg_change_frac


def _text_visible(cfg: Config, frame: np.ndarray, watcher) -> bool:
    if not cfg.menu_via_text or cfg.text_region is None or frame is None or frame.size == 0:
        return False
    crop = text_crop(frame, cfg)
    if crop.size == 0:
        return False
    if watcher is not None and getattr(watcher, "templates", None):
        if len(watcher.templates) >= 1:
            import cv2
            g = cv2.cvtColor(crop, cv2.COLOR_BGRA2GRAY) if crop.ndim == 3 and crop.shape[2] == 4 else \
                cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
            for tpl in watcher.templates.values():
                tt = tpl
                if tt.shape != g.shape:
                    tt = cv2.resize(tt, (g.shape[1], g.shape[0]))
                res = cv2.matchTemplate(g, tt, cv2.TM_CCOEFF_NORMED)
                if float(res[0, 0]) > 0.95:
                    return True
            return False
    import cv2
    g = cv2.cvtColor(crop, cv2.COLOR_BGRA2GRAY) if crop.ndim == 3 and crop.shape[2] == 4 else \
        cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    return float(np.std(g)) > 15.0
    import cv2
    g = cv2.cvtColor(crop, cv2.COLOR_BGRA2GRAY) if crop.ndim == 3 and crop.shape[2] == 4 else \
        cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    return float(np.std(g)) > 10.0


# ---------------------------------------------------------------------------
# Text-change detection
# ---------------------------------------------------------------------------

def text_crop(frame: np.ndarray, cfg: Config) -> np.ndarray:
    """Return the sub-frame that holds the status text."""
    h, w = frame.shape[:2]
    if cfg.text_region is not None:
        x0, y0, tw, th = cfg.text_region
        x0 = max(0, min(x0, w)); y0 = max(0, min(y0, h))
        x1 = max(0, min(x0 + tw, w)); y1 = max(0, min(y0 + th, h))
        return frame[y0:y1, x0:x1]
    return frame  # default: whole menu region


class TextWatcher:
    """Three-state text detector for the updated fishing mechanic.

        "hold"                  -> hold (reel)
        "about to start running" -> still hold
        "running"               -> release

    The resting "hold" text is snapshotted when the menu opens. The two
    non-rest texts ("about to start running" vs "running") are told apart by
    keeping ONE reference snapshot of each. Returns (released, frac) where
    released=True means let go.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.hold_ref: Optional[np.ndarray] = None      # the "hold" text
        self.alt_ref: Optional[np.ndarray] = None       # "about to start running"
        self.run_ref: Optional[np.ndarray] = None       # "running"
        self.changed = False
        self.settle = 0
        self.up = 0
        self.down = 0
        # Template-matching mode: if the user saved reference crops for each
        # state, compare against those instead of change-detection.
        self.templates: dict = {}
        self._load_templates(cfg.text_ref_images or {})

    def _load_templates(self, paths: dict):
        if not (paths.get("hold") and paths.get("about") and paths.get("running")):
            return
        import cv2
        for state in ("hold", "about", "running"):
            p = paths.get(state)
            if p and os.path.exists(p):
                img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.templates[state] = img

    def reset(self):
        self.hold_ref = None
        self.alt_ref = None
        self.run_ref = None
        self.changed = False
        self.settle = 0
        self.up = 0
        self.down = 0

    def _frac(self, crop, ref) -> float:
        if ref is None:
            return 1.0
        diff = np.abs(crop.astype(np.int16) - ref)
        return float(np.mean(diff.max(axis=2) > self.cfg.text_change_px))

    def _matches(self, crop, ref) -> bool:
        return ref is not None and self._frac(crop, ref) < self.cfg.text_min_trigger

    def _template_release(self, crop) -> bool:
        """Template-match the live crop against the saved state images.
        Returns True (release) only when 'running' is the best match."""
        if len(self.templates) < 3:
            return False
        import cv2
        if crop.ndim == 3 and crop.shape[2] == 4:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        scores = {}
        for state, tpl in self.templates.items():
            tt = tpl
            if tt.shape != gray.shape:
                tt = cv2.resize(tt, (gray.shape[1], gray.shape[0]))
            # normalized correlation; 1.0 = perfect match
            res = cv2.matchTemplate(gray, tt, cv2.TM_CCOEFF_NORMED)
            scores[state] = float(res[0, 0])
        best = max(scores, key=scores.get)
        return best == "running" and scores["running"] > self.cfg.text_min_trigger

    def step(self, frame: np.ndarray):
        """Returns (released, change_fraction). released=True -> let go."""
        crop = text_crop(frame, self.cfg)
        if crop.size == 0:
            return self.changed, 0.0

        if self.templates:
            self.changed = self._template_release(crop)
            return self.changed, 0.0

        # Snapshot the resting text after the menu's opening animation.
        if self.hold_ref is None:
            self.settle += 1
            if self.settle >= self.cfg.text_settle_frames:
                self.hold_ref = crop.astype(np.int16).copy()
            return self.changed, 0.0

        # Still on the resting "hold" text -> hold (reel).
        if self._matches(crop, self.hold_ref):
            self.up = 0
            self.down += 1
            if self.down >= self.cfg.text_resume_frames:
                self.changed = False
                self.hold_ref = crop.astype(np.int16).copy()  # self-correct
            return self.changed, 0.0

        # We're on a non-rest text: "about to start running" or "running".
        if self.run_ref is not None:
            if self._matches(crop, self.alt_ref):
                # back to "about to start running" -> keep holding
                self.up = 0
                self.down = 0
                self.changed = False
                return self.changed, 0.0
            if self._matches(crop, self.run_ref):
                # "running" -> release
                self.up += 1
                if self.up >= self.cfg.text_latch_frames:
                    self.changed = True
                return self.changed, 0.0
            # Matches neither saved state; hold by default and re-anchor so
            # transient transition frames don't cause a false release.
            self.up = 0
            self.down += 1
            if self.down >= self.cfg.text_resume_frames:
                self.changed = False
                self.alt_ref = crop.astype(np.int16).copy()
            return self.changed, 0.0

        # "running" not seen yet. First non-rest text is "about to start..."?
        if self.alt_ref is None:
            self.up += 1
            if self.up >= self.cfg.text_latch_frames:
                self.alt_ref = crop.astype(np.int16).copy()
                self.changed = False
                self.up = 0
            return self.changed, 0.0

        if self._matches(crop, self.alt_ref):
            # still "about to start running" -> hold
            self.up = 0
            self.down += 1
            if self.down >= self.cfg.text_resume_frames:
                self.changed = False
            return self.changed, 0.0

        # Different from "about to start running" and from "hold":
        # this is "running" -> release.
        self.up += 1
        if self.up >= self.cfg.text_latch_frames:
            self.run_ref = crop.astype(np.int16).copy()
            self.changed = True
            self.up = 0
        return self.changed, 0.0


# ---------------------------------------------------------------------------
# Color-change detection
# ---------------------------------------------------------------------------

class ColorWatcher:
    """Holds while a calibrated region keeps its original colour, and releases
    the instant that region turns a different colour. Stays released for
    color_release_seconds, then resumes holding.

    Original colour is snapshotted on reset() so it matches the moment the
    menu confirms. color_region is RELATIVE to the menu region.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.baseline: Optional[np.ndarray] = None
        self.released_until: float = 0.0
        self.running = False

    def reset(self):
        self.baseline = None
        self.released_until = 0.0
        self.running = False

    def _crop(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        x0, y0, cw, ch = self.cfg.color_region
        x0 = max(0, min(x0, w)); y0 = max(0, min(y0, h))
        x1 = max(0, min(x0 + cw, w)); y1 = max(0, min(y0 + ch, h))
        return frame[y0:y1, x0:x1]

    def step(self, frame: np.ndarray):
        """Returns (released, change_fraction)."""
        crop = self._crop(frame)
        if crop.size == 0:
            return self.running, 0.0

        now = time.time()
        if self.baseline is None:
            # snapshot the original colour the moment fishing starts
            self.baseline = crop.astype(np.int16).copy()
            return False, 0.0

        frac = float(np.mean(
            np.abs(crop.astype(np.int16) - self.baseline).max(axis=2)
            > self.cfg.color_change_px))

        if now >= self.released_until and frac > self.cfg.color_change_frac:
            # colour changed -> release, then hold off for the pause
            self.running = True
            self.released_until = now + self.cfg.color_release_seconds
        elif now >= self.released_until:
            # back to normal -> re-hold
            self.running = False
        # else: still inside the release pause, keep released

        return self.running, frac


# ---------------------------------------------------------------------------
# Low-level mouse movement (SendInput relative)
# ---------------------------------------------------------------------------
# Roblox captures/locks the cursor while fishing. When the cursor is captured,
# setting its position absolutely (SetCursorPos / pynput .position) does NOT
# move the in-game cursor, so clicks land where the cursor used to be. Relative
# movement deltas still register even when captured, so we move that way.

import ctypes
from ctypes import wintypes


def _send_rel_moves(steps):
    """Send a chunk of relative MOUSEEVENTF_MOVE deltas to the OS."""
    inp = ctypes.c_uint()
    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    class _MI(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_size_t)]
    class _IN(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("mi", _MI)]
    for dx, dy in steps:
        if dx == 0 and dy == 0:
            continue
        s = _IN()
        s.type = INPUT_MOUSE
        s.mi.dx = int(dx)
        s.mi.dy = int(dy)
        s.mi.dwFlags = MOUSEEVENTF_MOVE
        if not ctypes.windll.user32.SendInput(1, ctypes.byref(s), ctypes.sizeof(_IN)):
            raise OSError("SendInput failed")
        time.sleep(0.008)


# ---------------------------------------------------------------------------
# Mouse (pynput)
# ---------------------------------------------------------------------------

class Mouse:
    def __init__(self):
        from pynput.mouse import Controller, Button
        self.ctl = Controller()
        self.btn = Button.left
        self.held = False

    def hold(self):
        if not self.held:
            self.ctl.press(self.btn)
            self.held = True

    def release(self):
        if self.held:
            self.ctl.release(self.btn)
            self.held = False

    def move_to(self, x: int, y: int, speed: int = 10):
        """Move to (x,y) using pyautoit (AutoItX mouse_move). Higher speed
        value = smoother/blower glide; 0 = instant (teleport). This smooth
        glide also lets the game register the cursor before clicking."""
        import autoit
        sx, sy = autoit.mouse_get_pos()
        if abs(sx - x) < 2 and abs(sy - y) < 2:
            return
        autoit.mouse_move(int(x), int(y), speed=speed)

    def click_pos(self):
        """Click firmly at the cursor's current position (no mouse-move)."""
        import autoit
        focus_roblox()
        time.sleep(0.15)
        autoit.mouse_click("left")
        time.sleep(0.2)
        autoit.mouse_click("left")      # second click in case the first focused
        time.sleep(0.2)

    def click_at(self, x: int, y: int):
        """Focus the game, move to (x,y), and click."""
        import autoit
        focus_roblox()
        time.sleep(0.15)
        self.move_to(x, y)
        time.sleep(0.25)                 # settle so the click registers
        autoit.mouse_click("left")
        time.sleep(0.25)

    def press_key(self, key: str):
        """Tap a single key, ensuring the game window is focused."""
        import autoit
        focus_roblox()
        time.sleep(0.15)
        autoit.send(key)
        time.sleep(0.1)

    def position(self) -> Tuple[int, int]:
        return tuple(int(v) for v in self.ctl.position)


def focus_roblox():
    """Bring the Roblox window to the front so clicks land on it."""
    import ctypes
    try:
        user32 = ctypes.windll.user32
        hwnds = []
        def _find(hwnd, lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                name = buf.value.lower()
                if "roblox" in name:
                    hwnds.append(hwnd)
            return True
        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_find), 0)
        if hwnds:
            user32.SetForegroundWindow(hwnds[0])
            return True
    except Exception:
        pass
    return False


def _load_shutdown_template():
    """Load Desktop/shutdown.png pixel-perfect template if present."""
    import cv2
    cands = [
        r"C:\Users\xneas\Desktop\shutdown.png",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "shutdown.png"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "shutdown.png"),
        os.path.join(os.path.expanduser("~"), "Desktop", "shutdown.png"),
    ]
    for p in cands:
        try:
            if p and os.path.exists(p):
                img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
                if img is not None and img.size > 0:
                    return img, p
        except Exception:
            continue
    return None, None


def _shutdown_visible_on_screen(tpl) -> bool:
    """True if tpl appears anywhere on the primary monitor (pixel-perfect 0.99)."""
    if tpl is None:
        return False
    try:
        import cv2
        import mss
        import numpy as np
        with mss.mss() as sct:
            mon = sct.monitors[1]
            raw = sct.grab(mon)
            frame = np.frombuffer(raw.raw, dtype=np.uint8).reshape(raw.height, raw.width, -1)
            # drop alpha if present, convert to gray
            if frame.shape[2] == 4:
                gray = cv2.cvtColor(frame[:, :, :3], cv2.COLOR_BGR2GRAY)
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
            if gray.shape[0] < tpl.shape[0] or gray.shape[1] < tpl.shape[1]:
                return False
            res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            return float(max_val) > 0.99
    except Exception:
        return False




# ---------------------------------------------------------------------------
# Whole-game automaton (cast -> wait -> fish -> cast ...)
# ---------------------------------------------------------------------------

class AutoFisher:
    def __init__(self, cfg: Config, cap: Optional[Capture], mouse: Mouse):
        self.cfg = cfg
        self.cap = cap
        self.mouse = mouse
        self.watcher = TextWatcher(cfg)
        self.color_watcher = ColorWatcher(cfg)
        self.use_color = cfg.color_region is not None
        self.menu_det = MenuDetector(cfg)
        self.enabled = False
        self.state = "idle"
        self.cast_time: Optional[float] = None
        self.menu_frames = 0
        self.end_frames = 0
        self.caught = 0
        self.hold_start: Optional[float] = None
        self.water_spot: Optional[Tuple[int, int]] = None  # captured on start
        self.total_caught = load_total_caught()   # all-time persistent count
        self.mode = "normal"            # "normal" or "box" (F1 toggles)
        self.mode2_startup_done = False  # box-throw done at start of a run
        self.shutdown_tpl, self.shutdown_path = _load_shutdown_template()
        self._last_shutdown_check = 0.0

    def on_press_key(self, key):
        try:
            name = key.name
        except AttributeError:
            name = key.char
        if name == "f1":
            now = time.time()
            if getattr(self, "_last_f1", 0.0) and now - self._last_f1 < 0.5:
                return name  # debounce
            self._last_f1 = now
            self.mode = "box" if self.mode != "box" else "normal"
            _info("Mode: %s" % ("BOX (2)" if self.mode == "box" else "NORMAL (1)"))
            return name
        if name == "f8":
            now = time.time()
            if getattr(self, "_last_f8", 0.0) and now - self._last_f8 < 0.5:
                return name  # debounce: ignore OS key-repeat
            self._last_f8 = now
            self.enabled = not self.enabled
            if self.enabled:
                self.state = "idle"
                self.menu_frames = 0
                self.end_frames = 0
                self.caught = 0
                self.water_spot = self.mouse.position()   # session water spot
                self.mode2_startup_done = False
                self.menu_det.reset()
                self.watcher.reset()
                self.color_watcher.reset()
                _running_msg("RUNNING (%s)" % ("MODE 2" if self.mode == "box" else "MODE 1"))
            else:
                self.state = "idle"
                self.menu_frames = 0
                self.end_frames = 0
                self.water_spot = None                     # new spot next time
                self.mode2_startup_done = False
                self.mouse.release()   # fully let go
                _stopped_msg("STOPPED")
                print(f"  Fish caught this run: {self.caught}")
                print(f"  All-time total: {self.total_caught}")
        return name

    def cast(self):
        self.mouse.click_pos()
        self.cast_time = time.time()
        return True

    def start_casting(self) -> bool:
        if not self.cast():
            return False
        self.state = "waiting"
        self.menu_frames = 0
        self.menu_det.reset()   # re-learn this cast's background
        return True

    def step_demo(self):
        t = time.time()
        if self.state == "idle":
            print("[demo] casting")
            self.state = "casting"
            self.cast_time = t
        elif self.state == "casting":
            self.state = "waiting"
            print("[demo] waiting for menu...")
        elif self.state == "waiting":
            if t - self.cast_time > 3:
                self.state = "fishing"
                self.hold_start = t
                print("[demo] menu appeared -> waiting %.1fs before holding" %
                      self.cfg.hold_delay)
                self.watcher.reset()
        elif self.state == "fishing":
            if t - self.hold_start < self.cfg.hold_delay:
                return self.state
            # simulate the text toggling every ~3s, fish ends at ~12s
            period = (t - self.cast_time) % 6.0
            running = period > 3.0
            self._apply_hold(running)
            if t - self.cast_time > 12:
                self.caught += 1
                self._finish_catch()
        return self.state

    def step(self):
        if not self.enabled or self.cap is None:
            return self.state

        frame = self.cap.grab()

        if self.state == "idle":
            if self.mode == "box" and not self.mode2_startup_done:
                self._mode2_throw_box()
                self.mode2_startup_done = True
                # The final click of the throw-box already continues fishing
                # (that click IS the cast), so enter "waiting" directly.
                self._mode2_enter_waiting()
                return self.state
            self.start_casting()
            return self.state

        now = time.time()

        if self.state == "waiting":
            if self.cfg.menu_via_text and self.cfg.text_region is not None and getattr(self.watcher, "templates", None):
                menu_up = _text_visible(self.cfg, frame, self.watcher)
            else:
                menu_up = self.menu_det.step(frame) or menu_visible(self.cfg, frame)
                if self.cfg.menu_via_text and self.cfg.text_region is not None:
                    menu_up = menu_up and _text_visible(self.cfg, frame, self.watcher)
            if menu_up:
                self.menu_frames += 1
                if self.menu_frames >= self.cfg.menu_confirm_frames:
                    self.state = "fishing"
                    self.end_frames = 0
                    self.hold_start = now
                    self.watcher.reset()          # snapshot the current text
                    self.color_watcher.reset()    # snapshot the original colour
            else:
                self.menu_frames = 0
            if (self.cast_time is not None
                    and now - self.cast_time > self.cfg.max_wait):
                self.start_casting()

        elif self.state == "fishing":
            # Wait the delay before starting to hold so the menu settles in.
            if now - self.hold_start < self.cfg.hold_delay:
                self.mouse.release()   # don't click yet
                if self.cfg.menu_via_text and self.cfg.text_region is not None and getattr(self.watcher, "templates", None):
                    _menu = _text_visible(self.cfg, frame, self.watcher)
                else:
                    _menu = self.menu_det.step(frame) or menu_visible(self.cfg, frame)
                    if self.cfg.menu_via_text and self.cfg.text_region is not None:
                        _menu = _menu and _text_visible(self.cfg, frame, self.watcher)
                if _menu:
                    self.end_frames = 0
                elif self.end_frames >= self.cfg.end_idle_frames:
                    self.caught += 1
                    self._finish_catch()
                return self.state

            # THE RULE: hold while the text is normal, let go the instant it
            # changes, re-hold when it changes back. ADDITIONALLY, if the
            # calibrated colour region turns a different colour, let go for
            # color_release_seconds no matter what.
            running, _ = self.watcher.step(frame)
            if self.use_color:
                color_released, _ = self.color_watcher.step(frame)
                if color_released and not running:
                    running = True
            self._apply_hold(running)

            if self.cfg.menu_via_text and self.cfg.text_region is not None and getattr(self.watcher, "templates", None):
                _menu2 = _text_visible(self.cfg, frame, self.watcher)
            else:
                _menu2 = self.menu_det.step(frame) or menu_visible(self.cfg, frame)
                if self.cfg.menu_via_text and self.cfg.text_region is not None:
                    _menu2 = _menu2 and _text_visible(self.cfg, frame, self.watcher)
            if _menu2:
                self.end_frames = 0
            else:
                self.end_frames += 1
                if self.end_frames >= self.cfg.end_idle_frames:
                    self.caught += 1
                    self._finish_catch()

        return self.state

    def _apply_hold(self, running: bool):
        if running:
            self.mouse.release()
        else:
            self.mouse.hold()

    def _finish_catch(self):
        self.mouse.release()
        time.sleep(self.cfg.post_catch_pause)
        if self.mode == "box":
            # Box mode: quick timed store after menu down.
            # Menu up -> catch -> menu down -> click water -> F+first -> T+last.
            if self.cfg.mode2_store_locations and \
                    self.caught % self.cfg.mode2_store_every_n_catches == 0:
                self._run_box_quick_store()
                # If this catch also hits the maintenance interval, run it right after the quick store.
                if self.cfg.mode2_seq_locations and \
                        self.caught % self.cfg.mode2_every_n_catches == 0:
                    self._mode2_maintenance()
                    self.total_caught += 1
                    if not self.cfg.demo:
                        save_total_caught(self.total_caught)
                    self._mode2_enter_waiting()
                    return
                self.total_caught += 1
                if not self.cfg.demo:
                    save_total_caught(self.total_caught)
                self._mode2_enter_waiting()
                return
            # Big maintenance cycle every mode2_every_n_catches catches (when not also a store).
            if self.cfg.mode2_seq_locations and \
                    self.caught % self.cfg.mode2_every_n_catches == 0:
                self._mode2_maintenance()
                # Maintenance ends with the throw-box + press 1 + click, and
                # that final click already continues fishing, so do not cast
                # again on top of it.
                self.total_caught += 1
                if not self.cfg.demo:
                    save_total_caught(self.total_caught)
                self._mode2_enter_waiting()
                return
        elif self.cfg.seq_locations and self.caught % self.cfg.seq_every_n_catches == 0:
            self.run_post_catch_sequence()
        self.total_caught += 1
        if not self.cfg.demo:
            save_total_caught(self.total_caught)
        self.start_casting()

    def _scan_shutdown(self):
        """Called after the last click of any sequence. Logs 'scanned' every time,
        and pauses the bot if shutdown.png is visible. If AUTO_LEAVE_ENABLED and
        shutdown is seen, waits 5s, presses Esc, waits 1s, presses l, Enter, then exits."""
        print("scanned")
        if self.shutdown_tpl is None:
            return False
        if _shutdown_visible_on_screen(self.shutdown_tpl):
            # check global auto-leave toggle (set by GUI button)
            try:
                _auto = bool(globals().get("AUTO_LEAVE_ENABLED", False))
            except:
                _auto = False
            if _auto:
                print("Shutdown image detected — auto leave in 5s...")
                try:
                    self.mouse.release()
                except: pass
                time.sleep(5)
                # Esc
                try:
                    import autoit as _ai
                    _ai.send("{ESC}")
                except:
                    try:
                        from pynput.keyboard import Controller as _KC, Key as _KK
                        _k=_KC(); _k.press(_KK.esc); _k.release(_KK.esc)
                    except: pass
                time.sleep(1)
                # l + Enter
                try:
                    import autoit as _ai2
                    _ai2.send("l")
                    time.sleep(0.1)
                    _ai2.send("{ENTER}")
                except:
                    try:
                        from pynput.keyboard import Controller as _KC2, Key as _KK2
                        _k2=_KC2(); _k2.press("l"); _k2.release("l")
                        time.sleep(0.1)
                        _k2.press(_KK2.enter); _k2.release(_KK2.enter)
                    except: pass
                print("auto leave executed — exiting")
                try:
                    self.enabled=False; self.state="idle"
                    self.mouse.release()
                except: pass
                # turn script off
                try:
                    os._exit(0)
                except:
                    pass
                return True
            if self.enabled:
                print("Shutdown image detected — paused.")
                self.enabled = False
                self.state = "idle"
                try:
                    self.mouse.release()
                except Exception:
                    pass
            else:
                print("Shutdown image detected — paused.")
            print("shutdown/paused")
            return True
        return False

    def _mode2_enter_waiting(self):
        self.state = "waiting"
        self.menu_frames = 0
        self.cast_time = time.time()
        self.menu_det.reset()

    def _mode2_throw_box(self):
        """Startup (and after maintenance): click once to throw the box out,
        press 1, then click in the same spot to keep fishing."""
        print("Mode 2: throwing box...")
        self.mouse.click_pos()
        time.sleep(0.4)
        self.mouse.press_key("1")
        time.sleep(0.3)
        self.mouse.click_pos()
        time.sleep(0.4)
        time.sleep(2.0)
        self._scan_shutdown()

    def _mode2_maintenance(self):
        """Every N catches: press 2, hold left click mode2_hold_seconds,
        press 2 again, press F + 6 spots, press T + 1 spot, press 2 again,
        back to the water spot, throw the box, press 1, click again to
        continue."""
        locs = list(self.cfg.mode2_seq_locations)
        if len(locs) < 7:
            print("Mode-2 maintenance skipped (need 7 calibrated locations).")
            return
        print("Mode 2 maintenance: press 2, hold %ds..." % self.cfg.mode2_hold_seconds)
        self.mouse.press_key("2")
        time.sleep(0.3)
        self.mouse.hold()
        time.sleep(self.cfg.mode2_hold_seconds)
        self.mouse.release()
        time.sleep(0.3)
        self.mouse.press_key("2")
        time.sleep(0.3)
        self.mouse.press_key("f")
        time.sleep(0.3)
        import autoit as _autoit
        for x, y in locs[:6]:
            self.mouse.move_to(int(x), int(y), speed=5)
            time.sleep(0.05)
            _autoit.mouse_click("left")
            time.sleep(0.08)
        self.mouse.press_key("t")
        time.sleep(0.3)
        x, y = locs[6]
        self.mouse.move_to(int(x), int(y), speed=5)
        time.sleep(0.05)
        _autoit.mouse_click("left")
        time.sleep(0.3)
        time.sleep(2.0)
        self._scan_shutdown()
        self.mouse.press_key("2")
        time.sleep(0.3)
        if self.water_spot is not None:
            self.mouse.move_to(int(self.water_spot[0]), int(self.water_spot[1]), speed=5)
            print("Back to water spot:", self.water_spot)
            time.sleep(0.3)
        self._mode2_throw_box()

    def run_post_catch_sequence(self, use_seq2: bool = False):
        """After every N catches: press F, click the first 3 calibrated spots,
        press T, click the 4th spot, then move back to the session water spot.
        use_seq2=True uses mode 2's own store locations (mode2_store_locations)."""
        locs = list(self.cfg.mode2_store_locations if use_seq2 else self.cfg.seq_locations)
        if len(locs) < 4:
            return
        self.mouse.press_key("f")
        time.sleep(0.15)
        import autoit as _autoit2
        for x, y in locs[:3]:
            self.mouse.move_to(int(x), int(y), speed=5)
            time.sleep(0.05)
            _autoit2.mouse_click("left")
            time.sleep(0.08)
        self.mouse.press_key("t")
        time.sleep(0.15)
        x, y = locs[3]
        self.mouse.move_to(int(x), int(y), speed=5)
        time.sleep(0.05)
        _autoit2.mouse_click("left")
        time.sleep(0.08)
        time.sleep(2.0)
        self._scan_shutdown()
        if self.water_spot is not None:
            self.mouse.move_to(int(self.water_spot[0]), int(self.water_spot[1]), speed=5)

    def _run_box_quick_store(self):
        """Box mode only: after catch, menu down, click water, then
        F + first location, T + last location, with quick mouse moves."""
        locs = list(self.cfg.mode2_store_locations)
        if len(locs) < 4:
            return
        # Click water again to recast (menu already down)
        if self.water_spot is not None:
            self.mouse.move_to(int(self.water_spot[0]), int(self.water_spot[1]), speed=5)
            time.sleep(0.05)
        self.mouse.click_pos()
        time.sleep(0.15)
        self.mouse.press_key("f")
        time.sleep(0.1)
        import autoit
        self.mouse.move_to(int(locs[0][0]), int(locs[0][1]), speed=5)
        time.sleep(0.05)
        autoit.mouse_click("left")
        time.sleep(0.08)
        self.mouse.press_key("t")
        time.sleep(0.1)
        self.mouse.move_to(int(locs[3][0]), int(locs[3][1]), speed=5)
        time.sleep(0.05)
        autoit.mouse_click("left")
        time.sleep(0.08)
        time.sleep(2.0)
        self._scan_shutdown()
        if self.water_spot is not None:
            self.mouse.move_to(int(self.water_spot[0]), int(self.water_spot[1]), speed=5)
            time.sleep(0.05)


# ---------------------------------------------------------------------------
# Calibration helpers
# ---------------------------------------------------------------------------

def _click_points(n: int, prompts: list) -> list:
    from pynput import mouse as pm
    pts: list = []
    state = {"done": False}

    def on_click(x, y, button, pressed):
        if pressed and button == pm.Button.left:
            pts.append((x, y))
            if len(pts) >= n:
                state["done"] = True
                return False

    lst = pm.Listener(on_click=on_click)
    lst.start()
    for p in prompts:
        print("  ", p)
    while not state["done"]:
        time.sleep(0.05)
    lst.stop()
    return pts


def calibrate_region() -> Tuple[int, int, int, int]:
    (x0, y0), (x1, y1) = _click_points(
        2, ["Click the TOP-LEFT corner of the fishing bar.",
            "Then click the BOTTOM-RIGHT corner of the fishing bar."])
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1))
    r = (x0, y0, x1 - x0, y1 - y0)
    print(f"  Region saved: {r}")
    return r


def calibrate_cast() -> Tuple[int, int]:
    (x, y) = _click_points(
        1, ["Click the exact spot on the WATER where you cast to."])[0]
    print(f"  Cast spot saved: {(x, y)}")
    return int(x), int(y)


def calibrate_seq_locations() -> list:
    """Click 4 absolute screen locations in order:
    1-3 are the F-key clicks, 4 is the T-key click."""
    pts = _click_points(4, [
        "Click LOCATION 1 (first of the 3 spots after pressing F).",
        "Click LOCATION 2 (second of the 3 spots).",
        "Click LOCATION 3 (third of the 3 spots).",
        "Click LOCATION 4 (the spot to click after pressing T)."])
    locs = [(int(x), int(y)) for (x, y) in pts]
    print(f"  Sequence locations saved: {locs}")
    return locs


def calibrate_seq2_locations() -> list:
    """Click 7 absolute screen locations in order for MODE 2:
    1-6 are the F-key clicks, 7 is the T-key click."""
    pts = _click_points(7, [
        "Click LOCATION 1 (first of the 6 spots after pressing F).",
        "Click LOCATION 2 (second of the 6 spots).",
        "Click LOCATION 3 (third of the 6 spots).",
        "Click LOCATION 4 (fourth of the 6 spots).",
        "Click LOCATION 5 (fifth of the 6 spots).",
        "Click LOCATION 6 (sixth of the 6 spots).",
        "Click LOCATION 7 (the spot to click after pressing T)."])
    locs = [(int(x), int(y)) for (x, y) in pts]
    print(f"  Mode-2 sequence locations saved: {locs}")
    return locs


def calibrate_seq2_store_locations() -> list:
    """Click 4 absolute screen locations in order for MODE 2's trunk store:
    1-3 are the F-key clicks, 4 is the T-key click."""
    pts = _click_points(4, [
        "Click MODE-2 STORE LOCATION 1 (first of the 3 spots after pressing F).",
        "Click MODE-2 STORE LOCATION 2 (second of the 3 spots).",
        "Click MODE-2 STORE LOCATION 3 (third of the 3 spots).",
        "Click MODE-2 STORE LOCATION 4 (the spot to click after pressing T)."])
    locs = [(int(x), int(y)) for (x, y) in pts]
    print(f"  Mode-2 store locations saved: {locs}")
    return locs


def calibrate_text(cfg: Config) -> Tuple[int, int, int, int]:
    (x0, y0), (x1, y1) = _click_points(
        2, ["Click the TOP-LEFT corner of the status TEXT on the menu.",
            "Then click the BOTTOM-RIGHT corner of that text."])
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1))
    # convert absolute screen coords to relative-to-region coords
    rx, ry, _, _ = cfg.region
    r = (x0 - rx, y0 - ry, x1 - x0, y1 - y0)
    print(f"  Text region saved (relative): {r}")
    return r


def calibrate_color(cfg: Config) -> Tuple[int, int, int, int]:
    (x0, y0), (x1, y1) = _click_points(
        2, ["Click the TOP-LEFT corner of the small region that changes",
            "colour (the bell/indicator), then click its BOTTOM-RIGHT corner."])
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1))
    rx, ry, _, _ = cfg.region
    r = (x0 - rx, y0 - ry, x1 - x0, y1 - y0)
    print(f"  Colour region saved (relative): {r}")
    return r


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------

def _resolve_cfg(path: str) -> str:
    # default organized path is config/cfg.json, fallback to old root
    if path in ("cfg.json", "config/cfg.json"):
        for cand in (os.path.join("config","cfg.json"), "cfg.json", os.path.join(os.path.dirname(os.path.abspath(__file__)),"config","cfg.json")):
            if os.path.exists(cand):
                return cand
        return os.path.join("config","cfg.json")
    return path

def save_config(cfg: Config, path: str):
    path = _resolve_cfg(path)
    try: os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    except: pass
    data = {"region": cfg.region, "cast_pos": cfg.cast_pos,
            "text_region": cfg.text_region, "color_region": cfg.color_region,
            "seq_locations": cfg.seq_locations,
            "mode2_seq_locations": cfg.mode2_seq_locations,
            "mode2_store_locations": cfg.mode2_store_locations,
            "text_ref_images": cfg.text_ref_images}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_config(cfg: Config, path: str):
    path = _resolve_cfg(path)
    if not os.path.exists(path):
        # try old location
        alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg.json")
        if os.path.exists(alt):
            path = alt
        else:
            return
    try:
        with open(path) as f:
            data = json.load(f)
        cfg.region = tuple(data["region"]) if data.get("region") else None
        cfg.cast_pos = tuple(data["cast_pos"]) if data.get("cast_pos") else None
        cfg.text_region = tuple(data["text_region"]) if data.get("text_region") else None
        cfg.color_region = tuple(data["color_region"]) if data.get("color_region") else None
        cfg.seq_locations = [tuple(l) for l in data["seq_locations"]] \
            if data.get("seq_locations") else []
        cfg.mode2_seq_locations = [tuple(l) for l in data["mode2_seq_locations"]] \
            if data.get("mode2_seq_locations") else []
        cfg.mode2_store_locations = [tuple(l) for l in data["mode2_store_locations"]] \
            if data.get("mode2_store_locations") else []
        cfg.text_ref_images = data.get("text_ref_images") or {}
    except Exception as ex:
        print("Could not read cfg:", ex)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _migrate_layout():
    """One-time reorg: move root pngs -> assets/, patch cfg.json, remove old bats."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        a = os.path.join(here, "assets")
        os.makedirs(a, exist_ok=True)
        import shutil, json
        for name in ("text_hold.png","text_about.png","text_running.png","shutdown.png"):
            s = os.path.join(here, name)
            d = os.path.join(a, name)
            if os.path.exists(s) and not os.path.exists(d):
                try: shutil.move(s, d)
                except: pass
        desk = os.path.join(os.path.expanduser("~"), "Desktop", "shutdown.png")
        if os.path.exists(desk) and not os.path.exists(os.path.join(a,"shutdown.png")):
            try: shutil.copy(desk, os.path.join(a,"shutdown.png"))
            except: pass
        # migrate cfg.json / cfg.txt to config/
        try:
            os.makedirs(os.path.join(here, "config"), exist_ok=True)
            for name in ("cfg.json","cfg.txt"):
                s=os.path.join(here, name)
                d=os.path.join(here, "config", name)
                if os.path.exists(s) and not os.path.exists(d):
                    try: shutil.move(s,d)
                    except: pass
        except: pass
        # migrate data files to data/
        try:
            os.makedirs(os.path.join(here, "data"), exist_ok=True)
            for name in ("users.dat","session.dat","fish_counter.txt","owner.dat","fish_counter.txt"):
                s=os.path.join(here, name)
                d=os.path.join(here, "data", name)
                if os.path.exists(s) and not os.path.exists(d):
                    try: shutil.move(s,d)
                    except: pass
        except: pass
        # patch config/cfg.json if still at new location
        cfgp = os.path.join(here, "config", "cfg.json")
        altp = os.path.join(here, "cfg.json")
        for p in (cfgp, altp):
            if os.path.exists(p):
                try:
                    with open(p) as f: d=json.load(f)
                    tr=d.get("text_ref_images") or {}
                    changed=False
                    for k,v in list(tr.items()):
                        if v and "assets" not in v:
                            tr[k]=os.path.join("assets", os.path.basename(v))
                            changed=True
                        elif v:
                            tr[k]=os.path.join("assets", os.path.basename(v))
                    if changed:
                        d["text_ref_images"]=tr
                        with open(p,"w") as f: json.dump(d,f,indent=2)
                except: pass
                break
        # create fisher.bat if missing
        fb=os.path.join(here,"fisher.bat")
        if not os.path.exists(fb):
            try:
                with open(fb,"w") as f:
                    f.write('@echo off\ncd /d "%~dp0"\npython fisher_gui.py\nif errorlevel 1 py fisher_gui.py\n')
            except: pass
        # remove old bats silently (keep fisher.bat and run.bat migration stub)
        for b in ("setup.bat","calibrate.bat","preview.bat"):
            p=os.path.join(here,b)
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
    except: pass

def main():
    _migrate_layout()
    if "--update" in sys.argv:
        check_update(force=True)
        sys.exit(0)
    if check_update():
        print("Restart the script to use the updated version.")
        sys.exit(0)

    import auth
    if auth.login() is None:
        return

    ap = argparse.ArgumentParser(description="Roblox autofisher (text-change)")
    ap.add_argument("--calibrate", action="store_true",
                    help="click two corners of the fishing bar to set its region")
    ap.add_argument("--set-cast", action="store_true",
                    help="click the water spot the program should cast from")
    ap.add_argument("--set-text", action="store_true",
                    help="click two corners of the status TEXT (optional)")
    ap.add_argument("--set-color", action="store_true",
                    help="click two corners of the colour-change region (alt mode)")
    ap.add_argument("--set-seq", action="store_true",
                    help="click 4 locations for the post-catch F/T sequence")
    ap.add_argument("--set-seq2", action="store_true",
                    help="click 7 locations for MODE 2 (6 F-key + 1 T-key)")
    ap.add_argument("--set-seq2-store", action="store_true",
                    help="click 4 locations for MODE 2's trunk store (3 F-key + 1 T-key)")
    ap.add_argument("--preview", action="store_true",
                    help="open a live preview window showing detected targets")
    ap.add_argument("--demo", action="store_true",
                    help="simulate the whole session without touching the mouse")
    ap.add_argument("--snap-text", metavar="STATE",
                    help="save the current text-region crop as a reference for "
                         "STATE = hold|about|running (run with each state visible)")
    ap.add_argument("--cfg", default=os.path.join("config","cfg.json"),
                    help="path to the saved config file (default: config/cfg.json)")
    args = ap.parse_args()

    cfg = Config()
    cfg.preview = args.preview
    cfg.demo = args.demo

    load_config(cfg, args.cfg)

    if args.calibrate:
        cfg.region = calibrate_region()
        save_config(cfg, args.cfg)
        print(f"Region saved to {args.cfg}")
        return
    if args.set_cast:
        cfg.cast_pos = calibrate_cast()
        save_config(cfg, args.cfg)
        print(f"Cast spot saved to {args.cfg}")
        return
    if args.set_text:
        if cfg.region is None:
            print("Set the region first: python main.py --calibrate")
            return
        cfg.text_region = calibrate_text(cfg)
        save_config(cfg, args.cfg)
        print(f"Text region saved to {args.cfg}")
        return
    if args.set_color:
        if cfg.region is None:
            print("Set the region first: python main.py --calibrate")
            return
        cfg.color_region = calibrate_color(cfg)
        save_config(cfg, args.cfg)
        print(f"Colour region saved to {args.cfg}")
        return
    if args.set_seq:
        cfg.seq_locations = calibrate_seq_locations()
        save_config(cfg, args.cfg)
        print(f"Sequence locations saved to {args.cfg}")
        return
    if args.set_seq2:
        cfg.mode2_seq_locations = calibrate_seq2_locations()
        save_config(cfg, args.cfg)
        print(f"Mode-2 sequence locations saved to {args.cfg}")
        return
    if args.set_seq2_store:
        cfg.mode2_store_locations = calibrate_seq2_store_locations()
        save_config(cfg, args.cfg)
        print(f"Mode-2 store locations saved to {args.cfg}")
        return

    if args.snap_text:
        state = args.snap_text
        if state not in ("hold", "about", "running"):
            print("--snap-text must be hold, about, or running")
            return
        if cfg.text_region is None:
            print("Set the text region first: python main.py --set-text")
            return
        import cv2 as _cv2
        cap = Capture(cfg.region)
        print(f"Capturing '{state}' state. Wait for that text to be visible, "
              f"then press Enter in this window...")
        input("")
        crop = text_crop(cap.grab(), cfg)
        import os as _os
        _assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        try:
            os.makedirs(_assets, exist_ok=True)
        except Exception:
            pass
        out = os.path.join(_assets, f"text_{state}.png")
        ok = _cv2.imwrite(out, crop[:, :, :3] if crop.ndim == 3 and crop.shape[2] == 4 else crop)
        if not ok:
            print("Could not write", out); return
        cfg.text_ref_images[state] = out
        save_config(cfg, args.cfg)
        print(f"Saved {state} reference to {out} and stored in {args.cfg}")
        return

    if cfg.region is None:
        print("No fishing-bar region set. Run: python main.py --calibrate")
        return

    cap = Capture(cfg.region)
    mouse = Mouse()
    auto = AutoFisher(cfg, cap if not args.demo else None, mouse)

    _enable_ansi()

    from pynput import keyboard
    hooks = {"done": False}

    def on_press(key):
        name = auto.on_press_key(key)
        if name == "esc":
            mouse.release()
            hooks["done"] = True
            return False
    lst = keyboard.Listener(on_press=on_press)
    lst.daemon = True
    lst.start()

    _info("Auto-fisher ready.")
    _info("Hotkeys: F8 = toggle auto-fishing, F1 = switch mode, ESC = quit.")
    _info("Fish counter: %d" % load_total_caught())

    if args.preview:
        _preview_loop(cfg, cap)

    last_t = time.time()
    over = 1.0 / cfg.loop_hz

    try:
        while not hooks["done"]:
            if args.demo:
                auto.step_demo()
                time.sleep(0.05)
            else:
                auto.step()
                dt = over - (time.time() - last_t)
                if dt > 0:
                    time.sleep(dt)
                last_t = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        auto._apply_hold(False)
        print("\nQuit.")

    lst.stop()


def _preview_loop(cfg: Config, cap: Capture):
    import cv2
    watcher = TextWatcher(cfg)
    color_watcher = ColorWatcher(cfg)
    menu_det = MenuDetector(cfg)
    print("Preview: box = text region, 'changed' = running state, 'menu' = menu up.")
    print(f"Templates loaded: {len(watcher.templates)} (need 3 for text-menu)")
    while True:
        frame = cap.grab()
        running, frac = watcher.step(frame)
        if cfg.color_region is not None:
            running, frac = color_watcher.step(frame)
        # Use same menu logic as the bot: text-only when templates exist
        if cfg.menu_via_text and cfg.text_region is not None and len(watcher.templates) >= 1:
            menu = _text_visible(cfg, frame, watcher)
        else:
            menu = menu_det.step(frame) or menu_visible(cfg, frame)
            if cfg.menu_via_text and cfg.text_region is not None:
                menu = menu and _text_visible(cfg, frame, watcher)
        crop = text_crop(frame, cfg)

        bgr = frame[:, :, :3].copy()
        # text region box
        h, w = bgr.shape[:2]
        if cfg.text_region is not None:
            x0, y0, tw, th = cfg.text_region
            cv2.rectangle(bgr, (x0, y0), (x0 + tw, y0 + th), (255, 0, 0), 2)
        else:
            cv2.rectangle(bgr, (0, 0), (w, h), (255, 0, 0), 2)
        # colour region box
        if cfg.color_region is not None:
            x0, y0, cw, ch = cfg.color_region
            cv2.rectangle(bgr, (x0, y0), (x0 + cw, y0 + ch), (0, 255, 0), 2)

        status = f"menu={'UP' if menu else 'down'} state={'released' if running else 'held'} frac={frac:.3f}"
        cv2.putText(bgr, status, (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.imshow("Autofisher preview (ESC in console to exit)", bgr)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()