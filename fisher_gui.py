import os, sys, threading, queue, json, shutil

# Ensure we're in the bot folder so cfg.json etc. resolve
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

# --- one-time migration: old root pngs -> assets/, cfg.json patch, PATH ---
def _migrate():
    try:
        # move old pngs if still at root
        a = os.path.join(HERE, "assets")
        os.makedirs(a, exist_ok=True)
        for name in ("text_hold.png","text_about.png","text_running.png","shutdown.png"):
            src = os.path.join(HERE, name)
            dst = os.path.join(a, name)
            if os.path.exists(src) and not os.path.exists(dst):
                try: shutil.move(src, dst)
                except: pass
        # also copy Desktop shutdown.png into assets if missing
        desk = os.path.join(os.path.expanduser("~"), "Desktop", "shutdown.png")
        if os.path.exists(desk) and not os.path.exists(os.path.join(a,"shutdown.png")):
            try: shutil.copy(desk, os.path.join(a,"shutdown.png"))
            except: pass
        # patch cfg.json text_ref_images to assets/
        cfgp = os.path.join(HERE, "cfg.json")
        if os.path.exists(cfgp):
            try:
                with open(cfgp) as f: d=json.load(f)
                tr=d.get("text_ref_images") or {}
                changed=False
                for k,v in list(tr.items()):
                    if v and "assets" not in v:
                        base=os.path.basename(v)
                        tr[k]=os.path.join("assets", base)
                        changed=True
                    elif v:
                        # normalize slashes
                        tr[k]=os.path.join("assets", os.path.basename(v))
                if changed:
                    d["text_ref_images"]=tr
                    with open(cfgp,"w") as f: json.dump(d,f,indent=2)
            except: pass
        # ensure fisher.bat exists
        fb=os.path.join(HERE,"fisher.bat")
        if not os.path.exists(fb):
            try:
                with open(fb,"w") as f:
                    f.write('@echo off\ncd /d "%~dp0"\npython fisher_gui.py\nif errorlevel 1 py fisher_gui.py\n')
            except: pass
    except: pass
_migrate()

import tkinter as tk

# --- colours ---
BG = "#1e1e1e"
TITLE_BG = "#3a3a3c"
TEXT_WHITE = "#ffffff"
TEXT_PINK = "#ff7ab8"
RED = "#ff5f57"
YELLOW = "#ffbd2e"
GREEN = "#28ca42"
RED_HOVER = "#ff7b74"

q = queue.Queue()

class GuiWriter:
    def write(self, s):
        if s:
            q.put(s)
    def flush(self):
        pass

def pump():
    import re
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    try:
        while True:
            s = q.get_nowait()
            s = ansi.sub("", s)
            # Route all output through the text widget with colour tags
            # Pink for mode/running messages, white for everything else
            low = s.lower()
            tag = "pink" if any(k in low for k in ("mode", "running", "fish caught")) else "white"
            text.configure(state="normal")
            text.insert("end", s, tag)
            text.see("end")
            text.configure(state="disabled")
    except queue.Empty:
        pass
    root.after(30, pump)

def on_close():
    try:
        # Signal the bot loop to stop if it's running
        import main as _main  # noqa
        # The bot's hooks dict is local to main(), so we just kill the process
        # by destroying the window; the daemon thread will die with the process.
        # Give the bot a chance to release the mouse.
        try:
            from pynput.mouse import Controller, Button  # noqa
            Controller().release(Button.left)
        except Exception:
            pass
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass
    os._exit(0)

def start_drag(e):
    root._dx = e.x
    root._dy = e.y

def do_drag(e):
    try:
        root.geometry(f"+{root.winfo_x() + e.x - root._dx}+{root.winfo_y() + e.y - root._dy}")
    except Exception:
        pass

root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)
try:
    root.config(bg="magenta")
    root.attributes("-transparentcolor", "magenta")
except Exception:
    root.configure(bg=TITLE_BG)
root.geometry("500x300+80+80")
root.minsize(380, 220)
root.resizable(True, True)

# Rounded background via canvas
bg_canvas = tk.Canvas(root, bg="magenta", highlightthickness=0, bd=0)
bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

outer = tk.Frame(bg_canvas, bg=TITLE_BG)
# place outer inset 6px so rounded corners show
def _layout_outer(e=None):
    try:
        w, h = root.winfo_width(), root.winfo_height()
        bg_canvas.delete("all")
        if w > 4 and h > 4:
            # draw rounded rect
            r = 12
            bg_canvas.create_oval(0, 0, 2*r, 2*r, fill=TITLE_BG, outline=TITLE_BG)
            bg_canvas.create_oval(w-2*r, 0, w, 2*r, fill=TITLE_BG, outline=TITLE_BG)
            bg_canvas.create_oval(0, h-2*r, 2*r, h, fill=TITLE_BG, outline=TITLE_BG)
            bg_canvas.create_oval(w-2*r, h-2*r, w, h, fill=TITLE_BG, outline=TITLE_BG)
            bg_canvas.create_rectangle(r, 0, w-r, h, fill=TITLE_BG, outline=TITLE_BG)
            bg_canvas.create_rectangle(0, r, w, h-r, fill=TITLE_BG, outline=TITLE_BG)
        # keep outer filling the rounded area
        bg_canvas.coords("outer_win", 0, 0)
    except Exception:
        pass

bg_canvas.create_window(0, 0, anchor="nw", window=outer, tags="outer_win")
root.bind("<Configure>", _layout_outer)
outer.place(x=6, y=6, relwidth=1, relheight=1, width=-12, height=-12)
# Resize grip — more visible
grip = tk.Label(outer, text="◢", bg="#3a3a3c", fg="#cccccc", font=("Arial", 10, "bold"), cursor="sizing", bd=0, padx=6, pady=4)
grip.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-1)
def _start_resize(e):
    root._rx, root._ry = e.x_root, e.y_root
    root._rw, root._rh = root.winfo_width(), root.winfo_height()
def _do_resize(e):
    try:
        dx = e.x_root - root._rx
        dy = e.y_root - root._ry
        root.geometry(f"{max(380, root._rw+dx)}x{max(220, root._rh+dy)}")
    except Exception:
        pass
grip.bind("<Button-1>", _start_resize)
grip.bind("<B1-Motion>", _do_resize)

# Title bar (macOS traffic lights)
title = tk.Frame(outer, bg=TITLE_BG, height=28)
title.pack(fill="x", side="top")
title.pack_propagate(False)
title.bind("<Button-1>", start_drag)
title.bind("<B1-Motion>", do_drag)

# Traffic lights
btn_frame = tk.Frame(title, bg=TITLE_BG)
btn_frame.pack(side="left", padx=10, pady=6)

def _dot(col, cmd=None):
    c = tk.Canvas(btn_frame, width=12, height=12, bg=TITLE_BG, highlightthickness=0)
    c.create_oval(1, 1, 11, 11, fill=col, outline="")
    if cmd:
        c.bind("<Button-1>", lambda e: cmd())
        # hover
        def on_enter(e, c=c, orig=col): c.itemconfig(1, fill=RED_HOVER)
        def on_leave(e, c=c, orig=col): c.itemconfig(1, fill=orig)
        c.bind("<Enter>", on_enter)
        c.bind("<Leave>", on_leave)
    c.pack(side="left", padx=3)
    return c

_dot(RED, on_close)
_dot(YELLOW)
_dot(GREEN)

# Title text
tk.Label(title, text="fisher  —  fishingbot", bg=TITLE_BG, fg="#cfcfcf", font=("SF Mono", 9)).pack(side="left", padx=12)
title.bind("<Button-1>", start_drag)
title.bind("<B1-Motion>", do_drag)

# Calibrate button - top right, requires double-press
_cal_state = {"last": 0.0, "running": False}
def _on_calibrate():
    import time as _tm
    now = _tm.time()
    if _cal_state["running"]:
        q.put("[calibrate] already running...\n")
        return
    if now - _cal_state["last"] > 2.0:
        _cal_state["last"] = now
        q.put("[calibrate] press again within 2s to confirm calibrate\n")
        # reset after 2s if not pressed
        def _reset():
            import time as __tm2
            __tm2.sleep(2.0)
            if __tm2.time() - _cal_state["last"] >= 2.0:
                pass
        threading.Thread(target=_reset, daemon=True).start()
        return
    # double-press confirmed
    _cal_state["last"] = 0
    _cal_state["running"] = True
    q.put("[calibrate] starting full 9-step calibration...\n")
    def _run_cal():
        try:
            import main as _m
            cfg = _m.Config()
            _m.load_config(cfg, os.path.join("config","cfg.json"))
            # Step 1/9 region
            q.put("\n[1/9] Click TOP-LEFT then BOTTOM-RIGHT of fishing bar...\n")
            cfg.region = _m.calibrate_region()
            _m.save_config(cfg, os.path.join("config","cfg.json"))
            q.put(f"[1/9] Region saved: {cfg.region}\n")
            # Step 2/9 text region
            q.put("\n[2/9] Click TOP-LEFT then BOTTOM-RIGHT of status TEXT...\n")
            cfg.text_region = _m.calibrate_text(cfg)
            _m.save_config(cfg, os.path.join("config","cfg.json"))
            q.put(f"[2/9] Text region: {cfg.text_region}\n")
            # Step 3/5 text snaps - hold
            q.put("\n[3/9] Hold text: make HOLD visible then press Enter in console...\n")
            # reuse snap logic directly
            import cv2 as _cv2
            from main import Capture, text_crop
            cap = Capture(cfg.region)
            q.put("[3/9] Waiting for Enter...\n")
            input("")
            crop = text_crop(cap.grab(), cfg)
            import os as _os
            _assets = os.path.join(HERE, "assets")
            try: _os.makedirs(_assets, exist_ok=True)
            except: pass
            out = _os.path.join(_assets, "text_hold.png")
            _cv2.imwrite(out, crop[:,:,:3] if crop.ndim==3 and crop.shape[2]==4 else crop)
            cfg.text_ref_images["hold"] = os.path.join("assets","text_hold.png")
            _m.save_config(cfg, os.path.join("config","cfg.json"))
            q.put(f"[3/9] Saved hold to {out}\n")
            # Step 4/9 about
            q.put("\n[4/9] About to run: make 'ABOUT TO START RUNNING' visible then press Enter...\n")
            q.put("[4/9] Waiting for Enter...\n")
            input("")
            crop = text_crop(cap.grab(), cfg)
            out = _os.path.join(_assets, "text_about.png")
            _cv2.imwrite(out, crop[:,:,:3] if crop.ndim==3 and crop.shape[2]==4 else crop)
            cfg.text_ref_images["about"] = os.path.join("assets","text_about.png")
            _m.save_config(cfg, os.path.join("config","cfg.json"))
            q.put(f"[4/9] Saved about to {out}\n")
            # Step 5/9 running
            q.put("\n[5/9] Running text: make 'RUNNING' visible then press Enter...\n")
            q.put("[5/9] Waiting for Enter...\n")
            input("")
            crop = text_crop(cap.grab(), cfg)
            out = _os.path.join(_assets, "text_running.png")
            _cv2.imwrite(out, crop[:,:,:3] if crop.ndim==3 and crop.shape[2]==4 else crop)
            cfg.text_ref_images["running"] = os.path.join("assets","text_running.png")
            _m.save_config(cfg, os.path.join("config","cfg.json"))
            q.put(f"[5/9] Saved running to {out}\n")
            # Step 6/9 color
            q.put("\n[6/9] Click TOP-LEFT then BOTTOM-RIGHT of colour indicator...\n")
            cfg.color_region = _m.calibrate_color(cfg)
            _m.save_config(cfg, os.path.join("config","cfg.json"))
            q.put(f"[6/9] Colour region: {cfg.color_region}\n")
            # Step 7/9 seq 4
            q.put("\n[7/9] Click 4 SEQUENCE locations (3 after F, 1 after T)...\n")
            cfg.seq_locations = _m.calibrate_seq_locations()
            _m.save_config(cfg, os.path.join("config","cfg.json"))
            q.put(f"[7/9] Seq 4: {cfg.seq_locations}\n")
            # Step 8/9 mode2 7
            q.put("\n[8/9] MODE2: Click 7 locations (6 after F, 1 after T)...\n")
            cfg.mode2_seq_locations = _m.calibrate_seq2_locations()
            _m.save_config(cfg, os.path.join("config","cfg.json"))
            q.put(f"[8/9] Mode2 7: {cfg.mode2_seq_locations}\n")
            # Step 9/9 mode2 store 4
            q.put("\n[9/9] MODE2 STORE: Click 4 locations (3 after F, 1 after T)...\n")
            cfg.mode2_store_locations = _m.calibrate_seq2_store_locations()
            _m.save_config(cfg, os.path.join("config","cfg.json"))
            q.put(f"[9/9] Mode2 store 4: {cfg.mode2_store_locations}\n")
            q.put("\n[calibrate] Complete! You can now use F8 to fish.\n")
        except Exception as e:
            q.put(f"\n[calibrate error] {e}\n")
        finally:
            _cal_state["running"] = False
    threading.Thread(target=_run_cal, daemon=True).start()

cal_btn = tk.Button(title, text="calibrate", bg="#2d2d2d", fg="#cccccc", activebackground="#3a3a3a", activeforeground="#ffffff",
                    relief="flat", bd=0, padx=10, pady=2, font=("SF Mono", 8), cursor="hand2", command=_on_calibrate)
cal_btn.pack(side="right", padx=12, pady=4)

# Separator
tk.Frame(outer, bg="#2a2a2a", height=1).pack(fill="x")

# Console text
text = tk.Text(outer, bg=BG, fg=TEXT_WHITE, insertbackground=TEXT_WHITE,
               font=("Cascadia Code", 9), relief="flat", bd=0, padx=8, pady=8,
               wrap="word", state="disabled")
text.pack(fill="both", expand=True)
text.tag_configure("white", foreground=TEXT_WHITE)
text.tag_configure("pink", foreground=TEXT_PINK)

# Scrollbar (thin, mac-like)
sb = tk.Scrollbar(outer, command=text.yview, width=6, bg=BG, troughcolor=BG,
                  activebackground="#555", highlightthickness=0, bd=0)
text.configure(yscrollcommand=sb.set)

# Run the bot in a thread, capturing its output
def run_bot():
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = GuiWriter()
    sys.stderr = GuiWriter()
    try:
        import main
        main.main()
    except SystemExit:
        pass
    except Exception as e:
        print(f"\n[error] {e}\n")
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        # keep window open until red is clicked
        q.put("\n[done — click red to close]\n")

threading.Thread(target=run_bot, daemon=True).start()
root.after(30, pump)
root.mainloop()