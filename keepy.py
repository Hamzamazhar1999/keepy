"""
Keepy - a tiny always-on-top pixel-art desktop pet who juggles a football
with his head AND feet, boots it off the edges of your screen, plays a
lives-and-streak rally game with you, fidgets when idle, and reminds you to take
breaks.

Drawn as real blocky pixels: a flat terracotta box-body, wide stick-out arms,
and four little legs that actually move - one foot swings up to kick the ball.

The football has real physics (gravity + bouncing) and lives in its own tiny
transparent window, so Keepy can boot it and it ricochets off your screen edges.
It is multi-monitor aware: the ball bounces within whichever monitor he sits on.

Things to try
  Move:   left-click and drag him
  Pat:    a quick click (no drag) - he hops / spins / squashes / wiggles
  Play:   right-click -> "Play football!" - he serves the ball; click it
          mid-air to volley it back. Miss and you lose a life (3 lives), each
          rally speeds the ball up. Build the longest streak you can!
  Menu:   right-click for the game, timers, settings, mute, and quit

Designed for Windows (true colour-key transparency + click-through). It also
runs on macOS/Linux, just without the transparency.

No third-party packages required - only Python's standard library (Tkinter).

Run:    python keepy.py
"""

import json
import math
import os
import random
import threading
import time
import tkinter as tk
from tkinter import filedialog, simpledialog

# ---- Sound ------------------------------------------------------------------
try:
    import winsound  # Windows only

    def _play(seq):
        def run():
            for freq, dur in seq:
                try:
                    winsound.Beep(int(freq), int(dur))
                except Exception:
                    pass
        threading.Thread(target=run, daemon=True).start()
except ImportError:
    def _play(seq):
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass

BREAK_TUNE = [(523, 130), (659, 130), (784, 220)]
TIMER_TUNE = [(784, 120), (988, 120), (784, 220)]
PAT_TUNE   = [(680, 45), (920, 55)]
KICK_TUNE  = [(440, 35), (660, 45)]               # a little "thwock" on a kick
HIT_TUNE   = [(880, 60), (1175, 90)]              # bright blip on a good volley
MISS_TUNE  = [(330, 130), (247, 200)]             # sad descending "aww"
OVER_TUNE  = [(392, 160), (330, 160), (262, 320)] # game-over jingle

# the customisable sound events, in the order they appear in the menu:
# (key, friendly label, default beep tune)
SOUND_ACTIONS = [
    ("pat",   "Pat / boop",        PAT_TUNE),
    ("kick",  "Kick",              KICK_TUNE),
    ("hit",   "Good volley / goal", HIT_TUNE),
    ("miss",  "Miss / save",       MISS_TUNE),
    ("over",  "Game over",         OVER_TUNE),
    ("break", "Break reminder",    BREAK_TUNE),
    ("timer", "Timer",             TIMER_TUNE),
]
# map each default tune object back to its action so play() can swap in a custom
# WAV with no changes at the call sites.
_TUNE_ACTION = {id(tune): key for key, _label, tune in SOUND_ACTIONS}


def _play_wav(path):
    """Best-effort async WAV playback. Returns True if playback started."""
    try:
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return True
    except Exception:
        pass
    import shutil
    import subprocess
    for player in ("afplay", "aplay", "paplay"):   # macOS / ALSA / PulseAudio
        exe = shutil.which(player)
        if exe:
            try:
                subprocess.Popen([exe, path], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass
    return False


def _sound_config_path():
    return os.path.join(os.path.expanduser("~"), ".keepy", "sounds.json")

# ---- Look & feel ------------------------------------------------------------
TRANSPARENT = "#ff00ff"
S = 7
W, H = 200, 252            # main (pet) window
BW = 70                    # football window (its own little window)
PET_NAME = "Keepy"

BODY  = "#C16A4A"
LIMB  = "#A2543B"           # arms & legs: a darker terracotta so they read clearly
EYE   = "#2b2b2b"
SMILE = "#ffffff"

# one unified theme: coral-orange panels, white text & bars, red hearts
CORAL    = "#DB7A55"        # coral/orange - every bubble & the HUD panel
ACCENT = "#9E4B33"        # deeper orange - borders & bar tracks
BUBBLE_BORDER = ACCENT
BUBBLE_TX     = "#ffffff"    # white bubble text
HEART    = "#E5484D"         # red hearts (kept)
HEART_DK = "#5a2e22"         # a spent heart (dark, reads on the orange panel)

# body only (16 wide x 10 tall) - legs are separate so they can kick
BODY_GRID = [
    "..BBBBBBBBBBBB..",
    ".BBBBBBBBBBBBBB.",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
]
GRID_W, BODY_H, TOTAL_H = 16, 10, 12     # body rows + 2 rows of legs below
LEG_COLS = [2, 5, 9, 12]                 # inner column of each 2-wide leg

BALL_GRID = [
    ".ggggg.",
    "gWWWWWg",
    "gWDWDWg",
    "gWWDWWg",
    "gWDWDWg",
    "gWWWWWg",
    ".ggggg.",
]
BALL_PAL = {"g": "#b8b8b8", "W": "#ffffff", "D": "#262626"}

# on-Keepy juggling tricks. Each flows seamlessly into the next - the ball arcs
# from this trick's contact point to the NEXT one's, so it never teleports.
#   path "up"=straight over him, "orbit"=loops around;  contact "head" or "foot"
HEADER = {"apex": (78, 88), "arms": 1.00, "path": "up",    "contact": "head"}
KEEPY  = {"apex": (52, 70), "arms": 0.30, "path": "up",    "contact": "foot"}
WORLD  = {"apex": (70, 86), "arms": 0.85, "path": "orbit", "contact": "foot"}
TRICKS = [(KEEPY, 0.40), (HEADER, 0.30), (WORLD, 0.30)]
# ...plus a "wall kick": now and then he boots it off the nearest vertical
# screen edge and traps the rebound (see _start_wall).

BREAK_MESSAGES = [
    "Break time! Stretch those arms",
    "Look away from the screen for a bit",
    "Stand up and wiggle!",
    "Hydrate? Hydrate.",
    "Rest your eyes - 20 sec, far away",
    "Roll your shoulders back",
    "Quick walk? Even to the kettle",
]
PAT_REACTIONS = ["nice one!", "ole!", "boop!", "keepy-up!", "did you see that?",
                 "hehe", "again!"]
HIT_CHEERS = ["ole!", "nice!", "keep it up!", "again!", "sharp!"]
MISS_CRIES = ["aw, missed it!", "oof!", "got past me!", "nooo"]

REACT_T = 0.5            # length of a pat reaction (seconds)

# ball physics (screen pixels, seconds)
GRAVITY   = 1700.0
REST      = 0.74         # bounciness off the walls
RET_SPEED = 980.0        # homing speed when flying back to the pet

# penalty shootout
PEN_KEEP_S  = 8          # keeper (Keepy) sprite scale in the arena
PEN_BALL_S  = 6          # ball sprite scale in the arena
PEN_MAXDRAG = 110        # drag radius (px) for a full-power shot
PEN_MINSPD  = 560        # slowest / fastest shot speed (px/s)
PEN_MAXSPD  = 1180
PEN_CURVE   = 1500       # how hard a curved swipe bends the ball
PEN_DRAG_R  = 110        # max drag radius - can't drag beyond this
GOAL_COL = "#ffffff"     # white goalposts
NET_COL  = "#9aa6ad"     # faint net
PITCH    = "#2f6b43"     # arena bg - only visible on non-transparent (Linux)

# DVD bounce mode - he glides corner-to-corner like the old DVD logo, changing
# colour on every wall bounce, and rarely nails a corner (the famous wait).
DVD_SPEED   = 150.0      # glide speed (px/s)
CORNER_BAND = 18         # how close to a screen corner still counts as a corner
DVD_COLORS  = ["#DB7A55", "#E5484D", "#4D96E5", "#48C78E",
               "#E5C94D", "#9B5DE5", "#F15BB5", "#22C3C3"]


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class DesktopPet:
    def __init__(self, root):
        self.root = root
        root.title(PET_NAME)
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-transparentcolor", TRANSPARENT)
            self.transparent_ok = True
        except tk.TclError:
            self.transparent_ok = False

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.x = sw - W - 24
        self.y = sh - H - 64
        root.geometry(f"{W}x{H}+{self.x}+{self.y}")

        self.bg = TRANSPARENT if self.transparent_ok else "#e9e2cc"
        self.canvas = tk.Canvas(root, width=W, height=H, bg=self.bg,
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # geometry anchors (art-pixel grid -> window pixels)
        self.scale = S
        self.ox = (W - GRID_W * S) // 2
        self.oy_base = 140
        self.center_x = self.ox + GRID_W * S / 2
        self.feet_y = self.oy_base + BODY_H * S       # hip line (legs hang below)
        self.foot_bottom = self.oy_base + TOTAL_H * S # anchor for squash/stretch
        self.ball_r = 3.5 * S
        self.head_contact = self.oy_base - self.ball_r + 2
        self.foot_contact = self.feet_y - 18          # ball low point at the feet
        self.knee_contact = self.feet_y - 42

        # animation
        self.frame = 0
        self.blink_until = 0
        self.next_blink = time.time() + random.uniform(2, 5)
        self.excited_until = 0

        # juggling cycle (cur trick -> nxt trick, arcs chained for smoothness)
        self.cycle_start = time.time()
        self.cur = KEEPY
        self.nxt = HEADER
        self.cur_side = 1
        self.apexH = 64
        self.cycle_T = 0.55 + self.apexH / 130.0
        self.last_ball = (self.center_x, self.head_contact)  # for seamless holds
        self._was_held = False
        self._holding = False                    # in a held pose (catch + balance)
        self._catch_t0 = 0.0                      # when the current catch began
        self._catch_from = self.last_ball         # ball pos when the catch began

        # pat reactions
        self.react_kind = None
        self.react_t0 = 0

        # idle fidgets (glance / foottap / boot the ball off the walls)
        self.fidget_kind = None
        self.fidget_until = 0
        self.next_fidget = time.time() + random.uniform(5, 10)
        self.eye_glance = 0.0
        # idle has two phases: "juggle" (ball tricks) and "free" (ball kicked
        # off-screen so he can do ball-free actions without it breaking midair)
        self.idle_phase = "juggle"
        self.static_kind = None                  # current ball-free action
        self.static_t0 = 0.0
        self.static_until = 0.0
        self.static_queue = []                   # ball-free actions still to do

        # dragging
        self.dragging = False
        self.moved = 0
        self._press = (0, 0)
        self._origin = (self.x, self.y)

        # speech bubble
        self.bubble_text = None
        self.bubble_until = 0

        # break + one-off timers
        self.interval = 30
        self.break_enabled = True
        self.next_break = time.time() + self.interval * 60
        self.needs_break = False
        self.oneoff_at = None
        self.oneoff_label = ""

        # ---- the football: one physics object in its own window ----------
        self.mode = "idle"               # "idle" or "rally"
        self.ball_win = None
        self.ball_canvas = None
        self.ball_loose = False          # True when the ball is off the pet
        self.loose_kind = None           # "wall"|"frantic"|"serve"|"return"
        self.bx = self.by = 0.0          # ball centre, screen px
        self.vx = self.vy = 0.0          # ball velocity, px/s
        self._phys_t = time.time()
        self.target_x = None             # pet eases toward this screen x (chasing)
        self._flight_bounds = None       # monitor rect latched at launch time
        # parametric LOOP for the wall trick (two beziers: out high, in low)
        self._loop_t0 = 0.0              # kick start time
        self._loop_dur = 0.0            # kick out-and-back duration
        self._loop_p0 = (0.0, 0.0)      # where the ball starts (its current spot)
        self._loop_end = (0.0, 0.0)     # where it returns to (Keepy's head)
        self._loop_apex = (0.0, 0.0)    # far point out near the wall
        self._loop_cout = (0.0, 0.0)    # the kick's arc control point (shared)
        self._frantic_n = 0             # remaining frantic loops to chain

        # penalty shootout (its own big transparent arena window)
        self.arena = None
        self.arena_canvas = None
        self.arena_w = self.arena_h = 0

        # rally game
        self.rally_state = "ready"       # "ready" | "over"
        self.lives = 3
        self.streak = 0
        self.best_streak = 0
        self.level = 1
        self.next_serve = 0
        self.clock_end = 0
        self.clock_len = 1
        self.over_until = 0

        # multi-monitor bounds cache
        self._bounds = None
        self._bounds_t = 0

        # extras
        self.wander = False
        self.wander_target = None
        self.next_wander = time.time() + random.uniform(8, 16)
        self.muted = False
        self._modal = False
        self.sound_cfg = {}              # per-action custom WAV overrides
        self._load_sounds()

        # DVD bounce mode
        self.dvd_vx = self.dvd_vy = 0.0
        self.dvd_color = DVD_COLORS[0]
        self.dvd_flash_until = 0.0       # brief white flash on each bounce
        self.dvd_corner_until = 0.0      # corner-hit celebration window
        self.dvd_corners = 0             # corners nailed this session
        self.dvd_bounces = 0
        self.dvd_drag_grace = 0.0        # no corner credit right after a hand-drag
        self._dvd_phys_t = time.time()

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.show_menu)

        self.show_bubble(f"hi! I'm {PET_NAME} - I'll remind you to take breaks",
                         6)
        self.animate()
        self.tick()

    # ---- small helpers ---------------------------------------------------
    def show_bubble(self, text, seconds):
        self.bubble_text = text
        self.bubble_until = time.time() + seconds

    def play(self, seq):
        if self.muted:
            return
        action = _TUNE_ACTION.get(id(seq))           # custom WAV for this event?
        if action:
            custom = self.sound_cfg.get(action)
            if custom and os.path.isfile(custom) and _play_wav(custom):
                return
        _play(seq)                                   # else the default beep tune

    # ---- custom sounds ---------------------------------------------------
    def _load_sounds(self):
        try:
            with open(_sound_config_path(), "r", encoding="utf-8") as f:
                self.sound_cfg = json.load(f)
        except Exception:
            self.sound_cfg = {}

    def _save_sounds(self):
        try:
            path = _sound_config_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.sound_cfg, f, indent=2)
        except Exception:
            pass

    def set_action_sound(self, action, label):
        self._dialog_open(True)
        path = filedialog.askopenfilename(
            title=f"Choose a WAV file for: {label}",
            filetypes=[("WAV audio", "*.wav"), ("All files", "*.*")],
            parent=self.root)
        self._dialog_open(False)
        if not path:
            return
        self.sound_cfg[action] = path
        self._save_sounds()
        self.show_bubble(f"{label} sound updated", 2)
        if not self.muted:
            _play_wav(path)                          # quick preview

    def clear_action_sound(self, action, label):
        if self.sound_cfg.pop(action, None) is not None:
            self._save_sounds()
        self.show_bubble(f"{label} back to default beep", 2)

    def reset_sounds(self):
        self.sound_cfg = {}
        self._save_sounds()
        self.show_bubble("all sounds reset to default beeps", 2)

    def pethead(self):
        return (self.x + self.center_x, self.y + self.head_contact)

    def screen_bounds(self):
        """(x0,y0,x1,y1) of the monitor the pet is on (multi-monitor aware)."""
        now = time.time()
        if self._bounds is not None and now - self._bounds_t < 0.5:
            return self._bounds
        b = None
        try:                                          # Windows: real monitor rect
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                            ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

            class MI(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                            ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

            hmon = user32.MonitorFromWindow(self.root.winfo_id(), 2)  # NEAREST
            mi = MI()
            mi.cbSize = ctypes.sizeof(MI)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcMonitor
                b = (r.left, r.top, r.right, r.bottom)
        except Exception:
            b = None
        if b is None:                                 # fallback: whole screen
            b = (0, 0, self.root.winfo_screenwidth(),
                 self.root.winfo_screenheight())
        self._bounds, self._bounds_t = b, now
        return b

    def _virtual_bounds(self):
        """(x0,y0,x1,y1) spanning ALL monitors - for the frantic wall-to-wall."""
        try:
            import ctypes
            u = ctypes.windll.user32
            x = u.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
            y = u.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            w = u.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
            h = u.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
            if w > 0 and h > 0:
                return (x, y, x + w, y + h)
        except Exception:
            pass
        return self.screen_bounds()

    @staticmethod
    def _qbez(a, ctrl, b, e):
        """Quadratic bezier point at e in [0,1]."""
        m = 1.0 - e
        return (m * m * a[0] + 2 * m * e * ctrl[0] + e * e * b[0],
                m * m * a[1] + 2 * m * e * ctrl[1] + e * e * b[1])

    def _pick_trick(self):
        r, acc = random.random(), 0.0
        for t, w in TRICKS:
            acc += w
            if r <= acc:
                return t
        return TRICKS[0][0]

    def _arm_cycle(self, excited=False):
        """Set apexH + cycle_T for the current trick (shared by all entry points)."""
        lo, hi = self.cur["apex"]
        self.apexH = min(random.uniform(lo, hi) * (1.1 if excited else 1.0), 86)
        self.cycle_T = 0.55 + self.apexH / 130.0
        if self.cur["contact"] == "foot" and self.cur["path"] == "up":
            self.cycle_T *= 0.9              # keepy-ups a touch snappier
        if excited:
            self.cycle_T *= 0.82

    def _new_cycle(self, excited):
        self.cur, self.nxt = self.nxt, self._pick_trick()
        self.cur_side = -self.cur_side
        self._arm_cycle(excited)

    # ---- main loop -------------------------------------------------------
    def animate(self):
        self.frame += 1
        now = time.time()

        if self.bubble_text is not None and now >= self.bubble_until:
            self.bubble_text = None
            self.needs_break = False
        if now >= self.next_blink and now >= self.blink_until:
            self.blink_until = now + 0.12
            if random.random() < 0.25:           # sometimes a quick double-blink
                self.next_blink = now + 0.24
            else:
                self.next_blink = now + random.uniform(2.5, 6)
        blink = now < self.blink_until

        if self.mode == "penalty" and self.arena is not None:
            self._penalty_update(now)
            self._penalty_draw()
            self.root.after(33, self.animate)
            return

        if self.mode == "dvd":
            self._dvd_update(now)
            self.draw(now, self._dvd_pose(now, blink))
            self.root.after(33, self.animate)
            return

        if self.ball_loose:
            self._physics_step(now)
            self._update_loose(now)
            if self.ball_win is not None:
                bx, by = self.bx, self.by
                self.ball_win.geometry(f"+{int(bx - BW / 2)}+{int(by - BW / 2)}")
            pose = self._loose_pose(now, blink)
        elif self.mode == "rally":
            self._rally_update(now)
            pose = self._game_pose(now, blink)
        else:
            pose = self._idle_pose(now, blink)

        self.draw(now, pose)
        self._step_locomotion()

        if (self.wander and not self.dragging and not self._modal
                and self.mode == "idle" and not self.ball_loose):
            self.step_wander(now)

        self.root.after(33, self.animate)

    # ---- idle juggling + fidgets ----------------------------------------
    def _idle_pose(self, now, blink):
        # "free" phase: the ball is off-screen, he does ball-free actions
        if self.idle_phase == "free":
            return self._static_pose(now, blink)

        excited = now < self.excited_until
        reacting = self.react_kind is not None and now < self.react_t0 + REACT_T

        # schedule the next fidget / relax-break while he's just juggling
        if not reacting and now >= self.next_fidget:
            self._start_fidget(now)
            if self.ball_loose:                      # he just kicked the ball away
                return self._loose_pose(now, blink)

        sway = math.sin(now * 0.45)                  # slow weight-shift, foot to foot

        # ---- a pat: he catches the ball briefly and reacts -----------------
        if reacting:
            if not self._holding:                    # rising edge -> start a catch
                self._holding = True
                self._catch_t0 = now
                self._catch_from = self.last_ball
            self._was_held = True
            self.cycle_start = now
            kx, ky, dx, dyoff, arm = self._reaction(now)
            head_top = self.foot_bottom - TOTAL_H * S * ky + dyoff
            rest = (self.center_x + dx, head_top - self.ball_r + 3)
            ce = clamp((now - self._catch_t0) / 0.30, 0.0, 1.0)
            ce = ce * ce * (3 - 2 * ce)              # smoothstep
            if ce < 1.0:                             # ease the ball into his hands
                a = self._catch_from
                dist = math.hypot(a[0] - rest[0], a[1] - rest[1])
                ctrl = ((a[0] + rest[0]) / 2,
                        min(a[1], rest[1]) - min(18.0, dist * 0.25))
                ball = self._qbez(a, ctrl, rest, ce)
            else:
                ball = (rest[0] + math.sin(now * 4.5) * 2.0,
                        rest[1] + math.sin(now * 6.0) * 1.4)
            self.last_ball = ball
            if self.react_kind == "spin":
                ball = None
            return self._mk_pose(now, kx=kx, ky=ky, dx=dx, dyoff=dyoff,
                                 arm_l=arm, arm_r=arm, blink=blink, ball=ball,
                                 mouth="smile")

        # leaving a held state -> resume juggling from the head, seamlessly
        self._holding = False
        if self._was_held:
            self._was_held = False
            self.cur, self.nxt = HEADER, self._pick_trick()
            self._arm_cycle()
            self.cycle_start = now

        # ===================== continuous juggling ==========================
        if now - self.cycle_start > 5:
            self.cycle_start = now
        while now - self.cycle_start >= self.cycle_T:
            self.cycle_start += self.cycle_T
            self._new_cycle(excited)
        frac = clamp((now - self.cycle_start) / self.cycle_T, 0.0, 1.0)

        # the ball flies from THIS trick's contact to the NEXT trick's contact
        cy = {"head": self.head_contact, "foot": self.foot_contact}
        c0, c1 = cy[self.cur["contact"]], cy[self.nxt["contact"]]
        by = (c0 + (c1 - c0) * frac) - self.apexH * 4 * frac * (1 - frac)
        if self.cur["path"] == "orbit":
            ox = self.cur_side * 26 * math.sin(2 * math.pi * frac)
        else:
            ox = 0.0
        bx = self.center_x + ox + sway * 3.0         # ball drifts with the sway

        strike = clamp(1 - frac / 0.32, 0.0, 1.0)   # a quick touch at the start
        kick_idx, kick_amt, ball_dir = -1, 0.0, self.cur_side
        if self.cur["contact"] == "head":
            dyoff = -strike * 8                      # body pops up to head it
        else:
            dyoff = strike * 2                       # a small dip into the kick
            kick_idx = 2 if self.cur_side > 0 else 1
            ball_dir = 1 if LEG_COLS[kick_idx] < 8 else -1   # swing toward the ball
            kick_amt = strike
        lift = 0.15 + self.cur["arms"] * strike * 0.85
        wob = math.sin(2 * math.pi * frac) * 0.06
        eye_dx = clamp(ox / 26, -1, 1) * 0.5         # eyes follow the ball
        eye_dy = -clamp((self.head_contact - by) / 90, 0, 1) * 0.35

        # light fidgets ride ON TOP of the juggle - they don't stop the ball
        foot_tap = None
        if self.fidget_kind == "foottap" and now < self.fidget_until:
            tp = clamp((now - (self.fidget_until - 1.2)) / 1.2, 0, 1)
            foot_tap = (3, max(0.0, math.sin(tp * math.pi * 6)) * (1 - tp))
        elif self.fidget_kind == "lookdown" and now < self.fidget_until:
            eye_dy = 0.5

        self.last_ball = (bx, by)
        return self._mk_pose(now, dx=sway * 3.0, dyoff=dyoff,
                             arm_l=lift + wob, arm_r=lift - wob,
                             eye_dx=eye_dx, eye_dy=eye_dy, blink=blink,
                             ball=(bx, by), kick_idx=kick_idx, kick_amt=kick_amt,
                             ball_dir=ball_dir, foot_tap=foot_tap)

    def _start_fidget(self, now):
        roll = random.random()
        # go FREE: kick the ball off-screen and do ball-free actions
        if roll < 0.30 and self.mode == "idle":
            self._begin_free(now)
            return
        # wall trick: boot it off the nearest wall, it comes back the same way
        if roll < 0.46 and self.mode == "idle":
            self._start_wall(now)
            self.next_fidget = now + random.uniform(14, 24)
            return
        # otherwise a quick light overlay that doesn't interrupt the juggle
        r2 = random.random()
        if r2 < 0.4:
            self.fidget_kind = "lookdown"
            self.fidget_until = now + 1.1
        elif r2 < 0.75:
            self.fidget_kind = "foottap"
            self.fidget_until = now + 1.2
        else:
            self.fidget_kind = "glance"
            self.fidget_until = now + 0.9
            self.eye_glance = random.choice((-1, 1))
        self.next_fidget = now + random.uniform(5, 9)

    # ---- ball-free "relax" actions (he kicks the ball away first) --------
    STATIC_ACTIONS = [("yawn", 2.6), ("stretch", 3.2), ("sleep", 15.0),
                      ("ponder", 4.5), ("dance", 5.0),
                      ("wave", 4.5), ("scan", 4.5), ("dizzy", 5.0),
                      ("whistle", 6.0), ("headbop", 5.5)]

    def _begin_free(self, now):
        """Kick the ball off-screen, then do a long set of ball-free actions."""
        self.static_queue = random.sample(self.STATIC_ACTIONS,
                                           random.randint(6, 9))   # a good while
        self.static_kind = None
        self.next_fidget = now + random.uniform(28, 44)
        self._kick_ball_away(now)

    def _kick_ball_away(self, now):
        """Boot the ball hard toward the farther wall so it sails off-screen."""
        x0, _, x1, _ = self.screen_bounds()
        cx, _ = self.pethead()
        to_right = (x1 - cx) >= (cx - x0)            # the farther edge = more travel
        vx = (980 + random.uniform(0, 220)) * (1 if to_right else -1)
        vy = -random.uniform(320, 540)               # up and away
        self.play(KICK_TUNE)
        self._launch("kickaway", vx, vy)

    def _enter_free(self, now):
        """The kicked ball has left the screen - hide it and start relaxing."""
        self._hide_ball()
        self.loose_kind = None
        self.idle_phase = "free"
        self.static_kind = None
        self.static_until = now

    def _fetch_ball(self, now):
        """Done relaxing - the ball drops back in from the top; he juggles on."""
        x0, y0, x1, _ = self.screen_bounds()
        cx, _ = self.pethead()
        self.bx = clamp(cx, x0 + 20, x1 - 20)
        self.by = y0 - 90                            # comes down from above
        self.loose_kind = "return"
        self.ball_loose = True
        self._phys_t = now
        self._show_ball()
        if self.ball_win is not None:
            self.ball_win.geometry(
                f"{BW}x{BW}+{int(self.bx - BW/2)}+{int(self.by - BW/2)}")

    def _static_pose(self, now, blink):
        # advance the queue of ball-free actions; when empty, fetch the ball back
        if self.static_kind is None or now >= self.static_until:
            if self.static_queue:
                kind, dur = self.static_queue.pop(0)
                self.static_kind = kind
                self.static_t0 = now
                self.static_until = now + dur
            else:
                self.static_kind = None
                self._fetch_ball(now)                # -> ball loose, juggle resumes
                return self._loose_pose(now, blink)
        d = max(0.1, self.static_until - self.static_t0)
        p = clamp((now - self.static_t0) / d, 0.0, 1.0)
        env = math.sin(math.pi * p)
        k = self.static_kind
        kx = ky = 1.0
        dx = dyoff = 0.0
        al = ar = 0.18
        mouth = "smile"
        zzz = False
        emote = None
        eye_dx = eye_dy = 0.0
        if k == "yawn":
            ky = 1 + 0.06 * env
            dyoff = -4 * env
            al = ar = 0.2 + 0.7 * env
            mouth = "open" if 0.2 < p < 0.8 else "smile"
            blink = blink or 0.2 < p < 0.85
            zzz = p > 0.3
        elif k == "stretch":
            kx = 1 - 0.05 * env
            ky = 1 + 0.10 * env
            dyoff = -10 * env
            al = ar = 0.2 + 1.0 * env                # both arms shoot up
            blink = blink or 0.55 < p < 0.75
        elif k == "sleep":
            ky = 1 - 0.08 * env
            dyoff = 6 * env + math.sin(now * 2.0) * 2 * env   # slumps and breathes
            al = ar = -0.1
            blink = blink or 0.12 < p < 0.9          # eyes shut while asleep
            zzz = 0.12 < p < 0.92
        elif k == "ponder":
            dyoff = -2 * env
            al = 0.62 + 0.12 * math.sin(now * 3.0)   # one hand up near the chin
            ar = 0.08
            eye_dy = -0.6                             # looking up, thinking
            dx = math.sin(now * 1.4) * 3             # slow head tilt
        elif k == "dance":
            beat = now * 6.0
            dx = math.sin(beat) * 8 * env
            dyoff = -abs(math.sin(beat)) * 8 * env    # little hops
            al = 0.5 + 0.4 * math.sin(beat)
            ar = 0.5 + 0.4 * math.sin(beat + math.pi)  # arms pump alternately
            ky = 1 + 0.03 * math.sin(beat * 2)
            mouth = "open"
        elif k == "wave":
            # greeting: right arm raises HIGH and waves for the whole action
            up = min(p / 0.15, (1 - p) / 0.15, 1.0)  # ramp up, hold, ramp down
            wob = math.sin(now * 11.0)               # fast waving
            al = 0.12                                # left arm rests low
            ar = 0.55 + 0.45 * up + 0.22 * wob * up  # raised high + waving forearm
            dx = wob * 3.5 * up                      # body sways with the wave
            dyoff = -3 * up                          # tiny happy lift
            mouth = "open"
            emote = "!"
            blink = blink or (0.49 < p < 0.53)
        elif k == "scan":
            # curious look-around: head + eyes pan side to side, settle at the end
            up = min(p / 0.12, (1 - p) / 0.12, 1.0)
            pan = math.sin(now * 1.7)                 # keeps panning the whole time
            dx = pan * 9 * up
            eye_dx = pan * 1.1 * up                   # eyes lead the head
            eye_dy = -0.12 * up                       # head lifts slightly, alert
            al = ar = 0.18 + 0.06 * up
            blink = blink or (0.49 < p < 0.53)
        elif k == "dizzy":
            # silly woozy wobble: sway, squish, eyes loop, loose arms
            spin = now * 4.2
            dx = math.sin(spin) * 9 * env             # big side-to-side sway
            dyoff = math.sin(spin * 0.5 + 1.0) * 4 * env  # out-of-phase rock
            kx = 1 + 0.10 * math.sin(spin * 2) * env  # width wobbles
            ky = 1 - 0.05 * math.sin(spin * 2) * env
            eye_dx = math.cos(spin) * 0.9 * env       # eyes loop in a circle
            eye_dy = math.sin(spin) * 0.7 * env
            al = 0.35 + 0.3 * math.sin(spin + 0.5)    # loose balancing arms
            ar = 0.35 + 0.3 * math.sin(spin - 0.5)
            mouth = "open"
            blink = blink or (math.sin(spin) > 0.85)  # the occasional woozy blink
            emote = "~"
        elif k == "whistle":
            # calm breezy tune: slow sway, head bob, one hand resting up
            dx = math.sin(now * 1.3) * 4              # slow easy sway
            dyoff = math.sin(now * 2.6) * 1.5         # gentle head bob
            al = 0.30 + 0.06 * math.sin(now * 1.3)    # one hand resting casually up
            ar = 0.10
            mouth = "open"                            # puckered/whistling mouth
            eye_dx = 0.3 * math.sin(now * 1.3)        # eyes drift with the sway
            emote = "♪"                          # music note floats above
            blink = blink or 0.5 < p < 0.6
        elif k == "headbop":
            # rhythmic crisp nod on each downbeat, eased on/off by env
            beat = now * 4.2
            nod = abs(math.sin(beat))                 # 0..1, sharp downbeat each cycle
            dyoff = nod * 5 * env                      # head dips DOWN on the beat
            ky = 1 - 0.05 * nod * env                  # tiny squash on the dip
            dx = math.sin(beat) * 1.2 * env            # barely any sway
            al = 0.12 + 0.10 * nod * env               # arms bob a hair, stay low
            ar = 0.12 + 0.10 * nod * env
            mouth = "open" if nod > 0.6 else "smile"
            eye_dy = 0.25 * nod * env                  # eyes dip with the nod
            emote = "♫"                           # a couple of music notes
        return self._mk_pose(now, kx=kx, ky=ky, dx=dx, dyoff=dyoff,
                             arm_l=al, arm_r=ar, blink=blink, ball=None,
                             mouth=mouth, eye_dx=eye_dx, eye_dy=eye_dy, zzz=zzz,
                             emote=emote)

    def _reaction(self, now):
        p = clamp((now - self.react_t0) / REACT_T, 0.0, 1.0)
        env = math.sin(math.pi * p)
        kx = ky = 1.0
        dx = dyoff = 0.0
        k = self.react_kind
        if k == "squash":
            ky, kx = 1 - 0.22 * env, 1 + 0.14 * env
        elif k == "hop":
            dyoff, ky, kx = -26 * env, 1 + 0.05 * env, 1 - 0.03 * env
        elif k == "wiggle":
            dx = math.sin(p * math.pi * 8) * 7 * (1 - p)
        elif k == "spin":
            kx, dyoff = max(0.07, abs(math.cos(p * math.pi))), -10 * env
        return kx, ky, dx, dyoff, 0.2 + 0.8 * env

    # ---- ball physics ----------------------------------------------------
    def _ensure_ball_win(self):
        if self.ball_win is not None:
            return
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        bg = self.bg
        if self.transparent_ok:
            try:
                w.attributes("-transparentcolor", TRANSPARENT)
                bg = TRANSPARENT
            except tk.TclError:
                bg = "#e9e2cc"
        cv = tk.Canvas(w, width=BW, height=BW, bg=bg, highlightthickness=0)
        cv.pack()
        self.blit(cv, BALL_GRID, BW / 2 - 3.5 * S, BW / 2 - 3.5 * S, BALL_PAL)
        cv.bind("<Button-1>", self.on_ball_click)
        w.withdraw()                             # stay hidden until placed
        self.ball_win, self.ball_canvas = w, cv

    def _show_ball(self):
        self._ensure_ball_win()
        try:
            self.ball_win.deiconify()
        except tk.TclError:
            pass

    def _hide_ball(self):
        self.ball_loose = False
        self._holding = False                    # reset catch rising-edge tracking
        if self.ball_win is not None:
            try:
                self.ball_win.withdraw()
            except tk.TclError:
                pass

    def _launch(self, kind, vx, vy):
        px, py = self.pethead()
        self.bx, self.by = px, py
        self.vx, self.vy = vx, vy
        self.loose_kind = kind
        self.ball_loose = True
        self._phys_t = time.time()
        self._flight_bounds = self.screen_bounds()   # latch - don't change mid-air
        self._show_ball()
        if self.ball_win is not None:
            self.ball_win.geometry(
                f"{BW}x{BW}+{int(px - BW / 2)}+{int(py - BW / 2)}")

    def _loop_pos(self, now):
        """Kick out to the wall, then come back the SAME way in reverse: both
        legs share the one control point, so the return retraces the kick."""
        t = clamp((now - self._loop_t0) / self._loop_dur, 0.0, 1.0)
        if t <= 0.5:                                 # out-leg: start -> wall
            e = t * 2
            e = e * e * (3 - 2 * e)                  # ease: hangs at the top
            bx, by = self._qbez(self._loop_p0, self._loop_cout, self._loop_apex, e)
        else:                                        # in-leg: wall -> head, reversed
            e = (t - 0.5) * 2
            e = e * e * (3 - 2 * e)
            bx, by = self._qbez(self._loop_apex, self._loop_cout, self._loop_end, e)
        return bx, by, t

    def _physics_step(self, now):
        if self.loose_kind in ("wall", "frantic"):
            # pure parametric loop — no gravity, never touches the floor
            self.bx, self.by, _ = self._loop_pos(now)
            return
        dt = clamp(now - self._phys_t, 0.0, 0.04)
        self._phys_t = now
        if self.loose_kind == "return":          # homing flight back to the pet
            px, py = self.pethead()
            dxp, dyp = px - self.bx, py - self.by
            d = math.hypot(dxp, dyp) or 1.0
            self.bx += dxp / d * RET_SPEED * dt
            self.by += dyp / d * RET_SPEED * dt
            return
        # gravity physics for the serve and the kick-away
        self.vy += GRAVITY * dt
        self.bx += self.vx * dt
        self.by += self.vy * dt
        if self.loose_kind == "kickaway":
            return                               # no bounce — let it sail off-screen
        x0, y0, x1, y1 = self._flight_bounds or self.screen_bounds()
        r = self.ball_r
        if self.bx - r < x0:
            self.bx, self.vx = x0 + r, abs(self.vx) * REST
        elif self.bx + r > x1:
            self.bx, self.vx = x1 - r, -abs(self.vx) * REST
        if self.by - r < y0:
            self.by, self.vy = y0 + r, abs(self.vy) * REST
        elif self.by + r > y1:
            self.by, self.vy = y1 - r, -abs(self.vy) * REST
            self.vx *= 0.8

    def _update_loose(self, now):
        px, py = self.pethead()
        if self.loose_kind == "wall":
            _, _, t = self._loop_pos(now)
            if t >= 1.0:                         # kick complete — catch it
                self._trap(now, cheer=False)
        elif self.loose_kind == "frantic":
            pass                                 # the frantic chain drives itself
        elif self.loose_kind == "kickaway":      # waiting for it to leave the screen
            x0, y0, x1, y1 = self._flight_bounds or self.screen_bounds()
            m = 90
            if (self.bx < x0 - m or self.bx > x1 + m
                    or self.by < y0 - m or self.by > y1 + m):
                self._enter_free(now)            # it's gone — start relaxing
        elif self.loose_kind == "serve":
            if now >= self.clock_end:            # time up - it got past you
                self._rally_miss(now)
        elif self.loose_kind == "return":
            if math.hypot(self.bx - px, self.by - py) < 28:
                self._trap(now, cheer=True)

    def _trap(self, now, cheer):
        self._hide_ball()
        self.target_x = None
        self.loose_kind = None
        self.idle_phase = "juggle"               # back to ball-class actions
        self.static_queue = []
        if self.mode == "rally" and cheer:
            self._rally_success(now)
        else:                                    # back to juggling, ball at head
            self.cur, self.nxt = HEADER, self._pick_trick()
            self._arm_cycle()
            self.cycle_start = now
            self.last_ball = (self.center_x, self.head_contact)

    def _launch_loop(self, kind, start, apex, cout, duration):
        """Start a parametric kick from `start` out to the wall, back to the head."""
        cx, cy = self.pethead()
        self._loop_t0 = time.time()
        self._loop_dur = duration
        self._loop_p0 = start                    # begin exactly where the ball is
        self._loop_end = (cx, cy)                # return to the head
        self._loop_apex = apex
        self._loop_cout = cout
        self.bx, self.by = start
        self.loose_kind = kind
        self.ball_loose = True
        self._ensure_ball_win()                  # place it BEFORE showing (no flash)
        if self.ball_win is not None:
            self.ball_win.geometry(
                f"{BW}x{BW}+{int(start[0] - BW/2)}+{int(start[1] - BW/2)}")
        self._show_ball()

    def _loop_to(self, kind, start, edge, height, arc, dur):
        """Kick from `start` out toward `edge` (a wall) and back the same way.
        height = how high the apex sits; arc = control-point height of the kick."""
        cx, cy = self.pethead()
        direction = 1 if edge >= cx else -1
        reach = max(150.0, abs(edge - cx))
        apex = (edge + direction * 20, cy - height)         # far point, up high
        cout = (cx + direction * reach * 0.5, cy - arc)      # the kick's arc
        self.play(KICK_TUNE)
        self._launch_loop(kind, start, apex, cout, dur)

    def _ball_screen_pos(self):
        """Where the ball currently is, in screen pixels (juggle or loose)."""
        if self.ball_loose:
            return (self.bx, self.by)
        return (self.x + self.last_ball[0], self.y + self.last_ball[1])

    def _start_wall(self, now):
        x0, _, x1, _ = self.screen_bounds()
        cx, _ = self.pethead()
        to_right = (x1 - cx) < (cx - x0)
        edge = x1 if to_right else x0                 # nearest vertical wall
        # start the kick exactly where the ball is now, so it never "spawns"
        self._loop_to("wall", self._ball_screen_pos(), edge,
                      height=210, arc=300, dur=2.0)

    # ---- rally game ------------------------------------------------------
    def start_rally(self):
        self._hide_ball()                        # clear any loose ball first
        self.loose_kind = None
        self.target_x = None
        self.idle_phase = "juggle"
        self.static_queue = []
        self.mode = "rally"
        self.lives, self.streak, self.level = 3, 0, 1
        self.rally_state = "ready"
        self.next_serve = time.time() + 0.9
        self.show_bubble("rally! volley it back - don't miss!", 2.4)

    def stop_game(self):
        self.mode = "idle"
        self._hide_ball()
        self.loose_kind = None
        self.target_x = None
        self.idle_phase = "juggle"
        self.static_queue = []
        self.cycle_start = time.time()

    def _serve(self, now):
        spd = 250 + self.level * 16
        ang = random.uniform(-0.9, 0.9)          # mostly upward, some sideways
        vx = math.sin(ang) * spd
        vy = -(560 + self.level * 22)
        self.clock_len = max(1.15, 2.6 - (self.level - 1) * 0.13)
        self.clock_end = now + self.clock_len
        self.play(KICK_TUNE)
        self._launch("serve", vx, vy)

    def _rally_update(self, now):
        if self.rally_state == "ready" and now >= self.next_serve:
            self._serve(now)
        elif self.rally_state == "over" and now >= self.over_until:
            self.stop_game()

    def _rally_success(self, now):
        self.streak += 1
        self.level += 1
        self.best_streak = max(self.best_streak, self.streak)
        self.excited_until = now + 1.0
        self.play(HIT_TUNE)
        if self.streak % 5 == 0:
            self.show_bubble(f"{self.streak} in a row!!", 1.4)
        elif random.random() < 0.5:
            self.show_bubble(random.choice(HIT_CHEERS), 1.0)
        self.rally_state = "ready"
        self.next_serve = now + 0.7

    def _rally_miss(self, now):
        self._hide_ball()
        self.loose_kind = None
        self.lives -= 1
        self.streak = 0
        self.level = max(1, self.level - 1)
        self.play(MISS_TUNE)
        if self.lives <= 0:
            self._game_over(now)
        else:
            self.show_bubble(random.choice(MISS_CRIES), 1.2)
            self.rally_state = "ready"
            self.next_serve = now + 1.2

    def _game_over(self, now):
        self.rally_state = "over"
        self.over_until = now + 4.0
        self.play(OVER_TUNE)
        self.show_bubble(
            f"game over! streak {self.best_streak}. click me to play again",
            4)

    def on_ball_click(self, e):
        if self.ball_loose and self.loose_kind == "serve":   # caught it mid-air!
            self.loose_kind = "return"
            self.play(HIT_TUNE)

    # ---- poses while the ball is loose / in a game -----------------------
    def _loose_pose(self, now, blink):
        px, py = self.x + self.center_x, self.y + self.oy_base
        eye_dx = clamp((self.bx - px) / 130, -1, 1) * 0.9
        eye_dy = clamp((self.by - py) / 220, -1, 1) * 0.7
        if self.loose_kind == "frantic":         # panicked: hop and flail arms up
            dyoff = -abs(math.sin(now * 9)) * 16
            arm = 0.7 + 0.3 * math.sin(now * 13)
            return self._mk_pose(now, dyoff=dyoff, arm_l=arm, arm_r=arm,
                                 eye_dx=eye_dx, eye_dy=eye_dy, blink=blink,
                                 ball=None, mouth="open")
        if self.loose_kind == "kickaway":        # just booted it away, watches it go
            return self._mk_pose(now, dyoff=2, arm_l=0.15, arm_r=0.55,
                                 eye_dx=eye_dx, eye_dy=eye_dy, blink=blink,
                                 ball=None)
        dyoff = math.sin(now * 2.6) * 2
        arm = 0.3
        if self.loose_kind == "return":
            arm = 0.75
        elif self.loose_kind == "wall":
            arm = 0.4
        else:                                    # serve: a "come on!" wave
            arm = 0.3 + 0.4 * max(0.0, math.sin(now * 6))
        hud = self._hud() if self.mode == "rally" else None
        return self._mk_pose(now, dyoff=dyoff, arm_l=arm, arm_r=arm,
                             eye_dx=eye_dx, eye_dy=eye_dy, blink=blink,
                             ball=None, hud=hud)

    def _game_pose(self, now, blink):
        if self.rally_state == "over":
            slump = self._mk_pose(now, ky=0.9, dyoff=6, arm_l=-0.4, arm_r=-0.4,
                                  blink=blink, mouth="open", hud=self._hud())
            return slump
        bob = math.sin(now * 4) * 2              # ready bounce between serves
        return self._mk_pose(now, dyoff=bob, arm_l=0.4, arm_r=0.4, blink=blink,
                             hud=self._hud())

    def _hud(self):
        clock = None
        if self.ball_loose and self.loose_kind == "serve":
            clock = clamp((self.clock_end - time.time()) / self.clock_len, 0, 1)
        return dict(lives=self.lives, streak=self.streak, clock=clock)

    # ---- DVD bounce mode -------------------------------------------------
    def start_dvd(self):
        if self.mode == "rally":
            self.stop_game()
        if self.mode == "penalty":
            self.stop_penalty()
        self._hide_ball()
        self.loose_kind = None
        self.idle_phase = "juggle"
        self.static_queue = []
        self.mode = "dvd"
        ang = math.radians(random.uniform(38, 52))   # ~45deg, off-45 so corners
        self.dvd_vx = math.cos(ang) * DVD_SPEED * random.choice((-1, 1))
        self.dvd_vy = math.sin(ang) * DVD_SPEED * random.choice((-1, 1))
        self.dvd_color = random.choice(DVD_COLORS)
        self.dvd_flash_until = self.dvd_corner_until = 0.0
        self.dvd_corners = self.dvd_bounces = 0
        self.dvd_drag_grace = 0.0
        self._dvd_phys_t = time.time()
        x0, y0, x1, y1 = self.screen_bounds()
        a, b = (x1 - x0) - W, (y1 - y0) - H          # field the corner roams in
        # per-bounce corner odds: P = 4*band/(A+B) for an equidistributed glide
        odds = max(1, round((a + b) / (4 * CORNER_BAND)))
        self.show_bubble(f"DVD! corner odds ~1 in {odds} bounces", 3)

    def stop_dvd(self):
        self.mode = "idle"
        self.idle_phase = "juggle"
        self.static_queue = []
        self.cycle_start = time.time()

    def _dvd_update(self, now):
        dt = clamp(now - self._dvd_phys_t, 0.0, 0.05)
        self._dvd_phys_t = now
        if self.dragging:                            # let the user reposition him
            return
        x0, y0, x1, y1 = self.screen_bounds()
        self.x += self.dvd_vx * dt
        self.y += self.dvd_vy * dt
        hit_x = hit_y = False
        if self.x <= x0:
            self.x, self.dvd_vx, hit_x = x0, abs(self.dvd_vx), True
        elif self.x >= x1 - W:
            self.x, self.dvd_vx, hit_x = x1 - W, -abs(self.dvd_vx), True
        if self.y <= y0:
            self.y, self.dvd_vy, hit_y = y0, abs(self.dvd_vy), True
        elif self.y >= y1 - H:
            self.y, self.dvd_vy, hit_y = y1 - H, -abs(self.dvd_vy), True
        if hit_x or hit_y:
            self.dvd_bounces += 1
            self.dvd_color = random.choice(DVD_COLORS)   # new colour each bounce
            self.dvd_flash_until = now + 0.12
            # a corner = both edges at once, or one edge while hugging another
            ax = min(self.x - x0, (x1 - W) - self.x)
            ay = min(self.y - y0, (y1 - H) - self.y)
            corner = ((hit_x and hit_y) or (hit_x and ay <= CORNER_BAND)
                      or (hit_y and ax <= CORNER_BAND))
            # only credit a corner he GLIDED into - not one he was just dragged to
            if corner and now >= self.dvd_corner_until and now >= self.dvd_drag_grace:
                self.dvd_corners += 1
                self.dvd_corner_until = now + 1.8
                self.play(OVER_TUNE)
                self.show_bubble(f"CORNER!! x{self.dvd_corners}", 1.8)
            elif now >= self.dvd_corner_until:
                self.play(PAT_TUNE)                  # a little bonk
        self.root.geometry(f"+{int(self.x)}+{int(self.y)}")

    def _dvd_pose(self, now, blink):
        sp = math.hypot(self.dvd_vx, self.dvd_vy) or 1.0
        dirx, diry = self.dvd_vx / sp, self.dvd_vy / sp
        celebrating = now < self.dvd_corner_until
        kx = max(0.12, abs(math.cos(now * 12))) if celebrating else 1.0
        dyoff = math.sin(now * 9) * 1.5
        if celebrating:
            dyoff -= abs(math.sin(now * 11)) * 8     # excited little hops
        tint = "#ffffff" if now < self.dvd_flash_until else self.dvd_color
        return self._mk_pose(now, kx=kx, dx=dirx * 6, dyoff=dyoff,
                             arm_l=0.15, arm_r=0.15,
                             eye_dx=clamp(dirx, -1, 1) * 0.8,
                             eye_dy=clamp(diry, -1, 1) * 0.6,
                             blink=blink, ball=None, mouth="open",
                             tint=tint, wind=(dirx, diry))

    # ---- penalty shootout ------------------------------------------------
    def start_penalty(self):
        if self.mode == "rally":
            self.stop_game()
        self._hide_ball()
        self.idle_phase = "juggle"
        self.static_queue = []
        self.mode = "penalty"
        self._make_arena()
        self._penalty_init(time.time())
        try:
            self.root.withdraw()                 # hide the juggling pet window
        except tk.TclError:
            pass

    def stop_penalty(self):
        self.mode = "idle"
        if self.arena is not None:
            try:
                self.arena.destroy()
            except tk.TclError:
                pass
            self.arena = self.arena_canvas = None
        try:
            self.root.deiconify()
        except tk.TclError:
            pass
        self.cycle_start = time.time()
        self._was_held = False
        self.idle_phase = "juggle"
        self.static_queue = []

    def _make_arena(self):
        x0, y0, x1, y1 = self.screen_bounds()
        aw = int(min(x1 - x0 - 40, 760))
        ah = int(min(y1 - y0 - 80, 540))
        ax = x0 + ((x1 - x0) - aw) // 2
        ay = y0 + ((y1 - y0) - ah) // 2
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        # the arena is an OPAQUE panel (solid pitch). A transparent colour-key
        # window would be click-through on its empty areas, so clicks would fall
        # to the desktop (flicker + icons showing through); opaque captures them.
        bg = PITCH
        cv = tk.Canvas(w, width=aw, height=ah, bg=bg, highlightthickness=0)
        cv.pack()
        cv.bind("<ButtonPress-1>", self._arena_press)
        cv.bind("<B1-Motion>", self._arena_drag)
        cv.bind("<ButtonRelease-1>", self._arena_release)
        cv.bind("<Button-3>", self.show_menu)
        w.geometry(f"{aw}x{ah}+{ax}+{ay}")
        self.arena, self.arena_canvas = w, cv
        self.arena_w, self.arena_h = aw, ah

    def _penalty_init(self, now):
        aw, ah = self.arena_w, self.arena_h
        goal_w = aw * 0.66
        self.pen_post_l = (aw - goal_w) / 2
        self.pen_post_r = self.pen_post_l + goal_w
        self.pen_cross_y = 40
        self.pen_line_y = 150
        self.pen_spot = (aw / 2, ah - 70)
        self.keeper_y = self.pen_line_y + 8
        self.keeper_hw = GRID_W * PEN_KEEP_S / 2          # ~64 px half-width
        self.save_half = self.keeper_hw - 4
        self.k_min = self.pen_post_l + self.keeper_hw
        self.k_max = self.pen_post_r - self.keeper_hw
        self.keeper_x = aw / 2
        self.keeper_dir = 1
        self.keeper_speed = 175.0                         # ramps up per shot
        self.pen_goals = self.pen_saves = self.pen_shots = 0
        self.pen_over = False                             # sudden death: one miss ends it
        self.pen_best = getattr(self, "pen_best", 0)      # best streak, kept across rounds
        self.pen_result = ""
        self.pen_result_until = 0
        self.pen_aiming = False
        self.pen_drag = []
        self.pen_dragend = None
        self.pen_rad = 3.5 * PEN_BALL_S
        self._pen_phys_t = now
        self._reset_pen_ball()

    def _reset_pen_ball(self):
        self.pbx, self.pby = self.pen_spot
        self.pvx = self.pvy = 0.0
        self.pcurve = 0.0
        self.pen_state = "aim"

    def _penalty_update(self, now):
        dt = clamp(now - self._pen_phys_t, 0.0, 0.04)
        self._pen_phys_t = now
        # keeper patrols left<->right across the goal
        self.keeper_x += self.keeper_dir * self.keeper_speed * dt
        if self.keeper_x <= self.k_min:
            self.keeper_x, self.keeper_dir = self.k_min, 1
        elif self.keeper_x >= self.k_max:
            self.keeper_x, self.keeper_dir = self.k_max, -1

        if self.pen_state == "fly":
            sp = math.hypot(self.pvx, self.pvy)
            if sp > 1:                                    # curve = sideways swerve
                px, py = -self.pvy / sp, self.pvx / sp
                self.pvx += px * self.pcurve * dt
                self.pvy += py * self.pcurve * dt
            self.pbx += self.pvx * dt
            self.pby += self.pvy * dt
            if self.pby <= self.pen_line_y:               # reached the goal line
                self._resolve_shot(now)
            elif (self.pbx < -40 or self.pbx > self.arena_w + 40
                  or self.pby > self.arena_h + 60):
                self._pen_outcome(now, "WIDE!", goal=False, saved=False)
        elif self.pen_state == "result":
            if now >= self.pen_result_until:
                if self.pen_over:                         # missed -> game over
                    self.pen_state = "over"
                    self.play(OVER_TUNE)
                else:                                     # scored -> keep going
                    self._reset_pen_ball()

    def _resolve_shot(self, now):
        if self.pen_post_l < self.pbx < self.pen_post_r:
            if abs(self.pbx - self.keeper_x) < self.save_half:
                self._pen_outcome(now, "SAVED!", goal=False, saved=True)
            else:
                self._pen_outcome(now, "GOAL!", goal=True, saved=False)
        else:
            self._pen_outcome(now, "WIDE!", goal=False, saved=False)

    def _pen_outcome(self, now, text, goal, saved):
        self.pen_shots += 1
        if goal:
            self.pen_goals += 1
            self.pen_best = max(self.pen_best, self.pen_goals)
            self.play(HIT_TUNE)
        else:                                    # any miss = sudden death, you're out
            if saved:
                self.pen_saves += 1
            self.pen_over = True
            self.play(MISS_TUNE)
        self.keeper_speed = min(self.keeper_speed * 1.10, 720)   # faster each shot
        self.pen_result = text
        # a goal flashes briefly then resets fast; a miss waits a beat for GAME OVER
        self.pen_result_until = now + (0.45 if goal else 0.9)
        self.pen_state = "result"

    def _swipe_curve(self, path):
        if len(path) < 4:
            return 0.0
        mid = len(path) // 2
        a = (path[mid][0] - path[0][0], path[mid][1] - path[0][1])
        b = (path[-1][0] - path[mid][0], path[-1][1] - path[mid][1])
        la, lb = math.hypot(*a), math.hypot(*b)
        if la < 6 or lb < 6:
            return 0.0
        cross = (a[0] * b[1] - a[1] * b[0]) / (la * lb)   # signed sin(angle)
        return clamp(cross, -1, 1) * PEN_CURVE

    def _arena_press(self, e):
        if self.pen_state == "over":                      # click to play again
            self._penalty_init(time.time())
            return
        if self.pen_state == "aim":
            dx, dy = e.x - self.pen_spot[0], e.y - self.pen_spot[1]
            if math.hypot(dx, dy) < 70:                   # grabbed the ball
                self.pen_aiming = True
                self.pen_drag = [(e.x, e.y)]
                self.pen_dragend = (e.x, e.y)

    def _arena_drag(self, e):
        if self.pen_aiming:
            # clamp drag point within the allowed radius from the ball
            sx, sy = self.pen_spot
            dx, dy = e.x - sx, e.y - sy
            dist = math.hypot(dx, dy)
            if dist > PEN_DRAG_R:
                scale = PEN_DRAG_R / dist
                dx, dy = dx * scale, dy * scale
            clamped = (sx + dx, sy + dy)
            self.pen_drag.append(clamped)
            self.pen_dragend = clamped

    def _arena_release(self, _e):
        if not self.pen_aiming:
            return
        self.pen_aiming = False
        p0 = self.pen_drag[0]
        end = self.pen_dragend or p0
        # drag is PULLED BACK: shot direction is opposite to drag vector
        dvx, dvy = p0[0] - end[0], p0[1] - end[1]
        L = math.hypot(dvx, dvy)
        self.pen_dragend = None
        if L < 8 or dvy >= -4:                            # must pull back (upward shot)
            return
        power = clamp(L / PEN_MAXDRAG, 0.25, 1.0)
        speed = PEN_MINSPD + power * (PEN_MAXSPD - PEN_MINSPD)
        self.pvx, self.pvy = dvx / L * speed, dvy / L * speed
        self.pcurve = self._swipe_curve(self.pen_drag)
        self.pbx, self.pby = self.pen_spot
        self.pen_state = "fly"
        self.play(KICK_TUNE)

    def _penalty_draw(self):
        c = self.arena_canvas
        c.delete("all")
        aw, pl, pr = self.arena_w, self.pen_post_l, self.pen_post_r
        cy, ly = self.pen_cross_y, self.pen_line_y
        pw = 8
        # net
        for x in range(int(pl), int(pr), 24):
            c.create_line(x, cy, x, ly, fill=NET_COL)
        for y in range(int(cy), int(ly), 20):
            c.create_line(pl, y, pr, y, fill=NET_COL)
        # white goal frame (crossbar + posts)
        c.create_rectangle(pl - pw, cy - pw, pr + pw, cy, fill=GOAL_COL, outline=GOAL_COL)
        c.create_rectangle(pl - pw, cy - pw, pl, ly, fill=GOAL_COL, outline=GOAL_COL)
        c.create_rectangle(pr, cy - pw, pr + pw, ly, fill=GOAL_COL, outline=GOAL_COL)
        # keeper (Keepy), leaning toward an incoming ball
        lean = 0.0
        if self.pen_state == "fly":
            lean = clamp((self.pbx - self.keeper_x) / 40, -1, 1) * 5
        arm = 0.45 if self.pen_state == "fly" else 0.32
        self._draw_keepy(c, self.keeper_x, self.keeper_y, PEN_KEEP_S,
                        arm_lift=arm, lean=lean)
        # ball
        self.blit(c, BALL_GRID, self.pbx - 3.5 * PEN_BALL_S,
                  self.pby - 3.5 * PEN_BALL_S, BALL_PAL, s=PEN_BALL_S)
        # aim arrow while dragging - inverted (pool/kick style): arrow points
        # toward the goal (opposite of drag direction), scaled to drag power
        if self.pen_aiming and self.pen_dragend is not None:
            sx, sy = self.pen_spot
            ex, ey = self.pen_dragend
            ddx, ddy = ex - sx, ey - sy
            drag_len = math.hypot(ddx, ddy)
            if drag_len > 4:
                # arrow shoots in the opposite direction, length proportional to power
                arrow_len = drag_len * 0.55
                nx, ny = -ddx / drag_len, -ddy / drag_len
                ax, ay = sx + nx * arrow_len, sy + ny * arrow_len
                c.create_line(sx, sy, ax, ay, fill=CORAL, width=4,
                              arrow="last", arrowshape=(12, 14, 5))
        # score panel - your current streak (sudden death) + best so far
        c.create_rectangle(8, 8, 232, 36, fill=CORAL, outline=ACCENT)
        c.create_text(16, 22, anchor="w", fill="#ffffff",
                      font=("Courier New", 13, "bold"),
                      text=f"STREAK {self.pen_goals}    BEST {self.pen_best}")
        # game over screen (sudden death - one miss and you're out)
        if self.pen_state == "over":
            mx, my = aw / 2, self.arena_h * 0.5
            c.create_rectangle(mx - 150, my - 52, mx + 150, my + 52,
                               fill=CORAL, outline=ACCENT)
            c.create_text(mx, my - 22, text="GAME OVER", fill="#ffffff",
                          font=("Courier New", 26, "bold"))
            c.create_text(mx, my + 8, fill="#ffffff",
                          font=("Courier New", 13, "bold"),
                          text=f"{self.pen_goals} scored in a row")
            c.create_text(mx, my + 32, fill="#ffffff",
                          font=("Courier New", 11, "bold"),
                          text="click to play again")
        # result flash
        elif self.pen_state == "result":
            mx, my = aw / 2, self.arena_h * 0.5
            c.create_rectangle(mx - 96, my - 28, mx + 96, my + 28,
                               fill=CORAL, outline=ACCENT)
            c.create_text(mx, my, text=self.pen_result, fill="#ffffff",
                          font=("Courier New", 26, "bold"))
        elif self.pen_shots == 0 and not self.pen_aiming:
            c.create_text(aw / 2, self.arena_h - 28, fill="#ffffff",
                          font=("Courier New", 12, "bold"),
                          text="one miss and you're out - curve it past the keeper!")

    def _draw_keepy(self, c, cx, foot_y, s, arm_lift=0.3, blink=False, lean=0.0):
        bw, bh = GRID_W * s, TOTAL_H * s
        top_x = cx - bw / 2 + lean
        top_y = foot_y - bh

        def cell(col, row, wc=1, hr=1, color=BODY):
            x, y = top_x + col * s, top_y + row * s
            c.create_rectangle(x, y, x + wc * s, y + hr * s, fill=color, outline=color)

        row = 4 - 3 * arm_lift                            # wide keeper arms
        for col0 in (-4, 16):
            cell(col0, row, 4, 1, LIMB)
            cell(col0, row + 1, 4, 1, LIMB)
        for col in LEG_COLS:                              # planted legs
            cell(col, 10, 2, 2, LIMB)
        for r, rowstr in enumerate(BODY_GRID):
            ci, n = 0, len(rowstr)
            while ci < n:
                if rowstr[ci] != "B":
                    ci += 1
                    continue
                j = ci
                while j < n and rowstr[j] == "B":
                    j += 1
                cell(ci, r, j - ci, 1)
                ci = j
        eh = 1 if blink else 2
        for ecol in (3, 11):
            cell(ecol, 5, 2, eh, EYE)
        for sc, sr in [(6, 7), (9, 7), (7, 8), (8, 8)]:
            cell(sc, sr, 1, 1, SMILE)

    # ---- pet locomotion (chase the ball when booting) --------------------
    def _step_locomotion(self):
        if self.target_x is None:
            return
        cur = self.x + self.center_x
        nx = self.x + (self.target_x - cur) * 0.12
        x0, _, x1, _ = self.screen_bounds()
        self.x = clamp(nx, x0 - self.ox, x1 - W + self.ox)
        self.root.geometry(f"+{int(self.x)}+{int(self.y)}")

    # ---- pose assembly ---------------------------------------------------
    def _mk_pose(self, now, kx=1.0, ky=1.0, dx=0.0, dyoff=0.0, arm_l=0.2,
                 arm_r=0.2, eye_dx=0.0, eye_dy=0.0, blink=False, ball=None,
                 kick_idx=-1, kick_amt=0.0, ball_dir=1, mouth="smile", hud=None,
                 foot_tap=None, zzz=False, tint=None, wind=None, emote=None):
        if self.fidget_kind == "glance" and now < self.fidget_until:
            eye_dx += self.eye_glance * 0.7
        head_top = self.foot_bottom - TOTAL_H * S * ky + dyoff
        bubble = None
        if self.bubble_text is not None:          # anchor to the head so it's steady
            bubble = (self.bubble_text, CORAL, head_top - 4)
        return dict(kx=kx, ky=ky, dx=dx, dyoff=dyoff, arm_l=arm_l, arm_r=arm_r,
                    eye_dx=eye_dx, eye_dy=eye_dy, blink=blink, ball=ball,
                    kick_idx=kick_idx, kick_amt=kick_amt, ball_dir=ball_dir,
                    mouth=mouth, bubble=bubble, hud=hud,
                    foot_tap=foot_tap, zzz=zzz, tint=tint, wind=wind, emote=emote)

    # ---- drawing ---------------------------------------------------------
    def blit(self, canvas, grid, ox, oy, pal, s=None):
        s = self.scale if s is None else s
        for r, row in enumerate(grid):
            ci, n = 0, len(row)
            while ci < n:
                ch = row[ci]
                if ch not in pal:
                    ci += 1
                    continue
                j = ci
                while j < n and row[j] == ch:
                    j += 1
                col = pal[ch]
                x, y = ox + ci * s, oy + r * s
                canvas.create_rectangle(x, y, x + (j - ci) * s, y + s,
                                        fill=col, outline=col)
                ci = j

    def draw(self, now, pose):
        c = self.canvas
        c.delete("all")
        self.draw_sprite(c, pose)
        if pose.get("wind"):                     # speed streaks, drawn OVER him
            self._draw_wind(c, pose["wind"])
        if pose["ball"]:
            bx, by = pose["ball"]
            self.blit(c, BALL_GRID, bx - 3.5 * S, by - 3.5 * S, BALL_PAL)
        if pose["hud"]:
            self.draw_hud(c, pose["hud"])
        if pose["bubble"]:
            self.draw_bubble(c, *pose["bubble"])

    def _draw_wind(self, c, wind):
        dirx, diry = wind
        # Trail points OPPOSITE the glide direction; perp fans the streaks sideways.
        tx, ty = -dirx, -diry
        perpx, perpy = -ty, tx
        bx = self.center_x
        by = self.oy_base + BODY_H * S / 2          # ~(100, 175)
        col = self.dvd_color or "#ffffff"

        # --- 5 long manga speed-streaks, marching outward, fanned sideways ---
        # All begin >=48px from center so the arm silhouette never hides them.
        N = 5
        for i in range(N):
            spread = (i - (N - 1) / 2.0) * 12.0     # -24..+24 across the fan
            # marching phase: each streak whooshes outward then recycles
            phase = ((self.frame * 0.10 + i * 0.27) % 1.0)
            base = 48.0 + phase * 30.0              # 48..78 from center
            # length pulses + grows as it recedes -> reads as a whoosh
            L = 34.0 + 16.0 * math.sin(self.frame * 0.22 + i * 1.7)
            if L < 18.0:
                L = 18.0
            fade = math.sin(phase * math.pi)        # 0..1..0 over the march
            if fade <= 0.06:
                continue
            sx = bx + tx * base + perpx * spread
            sy = by + ty * base + perpy * spread
            # tapering 3 segments: thick head -> thin tail (manga character)
            mx1 = sx + tx * (L * 0.45) + perpx * spread * 0.10
            my1 = sy + ty * (L * 0.45) + perpy * spread * 0.10
            mx2 = sx + tx * (L * 0.80)
            my2 = sy + ty * (L * 0.80)
            ex = sx + tx * L
            ey = sy + ty * L
            wmain = max(1, int(round(1 + 3 * fade)))
            c.create_line(sx, sy, mx1, my1, fill="#ffffff",
                          width=wmain, capstyle="round")
            c.create_line(mx1, my1, mx2, my2, fill="#ffffff",
                          width=max(1, int(round(wmain * 0.6))), capstyle="round")
            c.create_line(mx2, my2, ex, ey, fill="#ffffff",
                          width=1, capstyle="round")
            # bright dvd-colour spark at the leading tip
            if fade > 0.45:
                r = 2.4 * fade
                c.create_oval(ex - r, ey - r, ex + r, ey + r,
                              fill=col, outline="")

        # --- streaming dust particles receding into the corner ---
        M = 7
        for i in range(M):
            ph = (self.frame * 0.05 + i / float(M)) % 1.0   # 0..1 life
            dist = 50.0 + ph * 80.0                          # 50..130 out
            lane = ((i % 3) - 1) * 13.0 * (0.5 + ph)         # fans outward
            wob = math.sin(self.frame * 0.25 + i * 1.7) * 3.0
            px = bx + tx * dist + perpx * (lane + wob)
            py = by + ty * dist + perpy * (lane + wob)
            r = max(0.8, 3.2 * (1.0 - ph))                   # shrinks as it recedes
            fill = "#ffffff" if (i % 2 == 0) else col
            c.create_oval(px - r, py - r, px + r, py + r,
                          fill=fill, outline="")
            if i % 3 == 0:                                    # tiny motion-blur dash
                dl = 6.0 * (1.0 - ph)
                c.create_line(px, py, px + tx * dl, py + ty * dl,
                              fill="#ffffff", width=1)

    def draw_sprite(self, c, pose):
        kx, ky = pose["kx"], pose["ky"]
        sxp, syp = S * kx, S * ky
        bw, bh = GRID_W * sxp, TOTAL_H * syp
        top_x = self.center_x - bw / 2 + pose["dx"]
        top_y = self.foot_bottom - bh + pose["dyoff"]

        tint = pose.get("tint")                  # DVD mode recolours him
        body = tint or BODY
        limb = tint or LIMB

        def cell(col, row, wc=1, hr=1, color=None):
            color = body if color is None else color
            x, y = top_x + col * sxp, top_y + row * syp
            c.create_rectangle(x, y, x + wc * sxp, y + hr * syp,
                               fill=color, outline=color)

        self._arm(cell, -4, pose["arm_l"], limb)
        self._arm(cell, 16, pose["arm_r"], limb)
        self._legs(cell, pose, limb)
        for r, row in enumerate(BODY_GRID):
            ci, n = 0, len(row)
            while ci < n:
                if row[ci] != "B":
                    ci += 1
                    continue
                j = ci
                while j < n and row[j] == "B":
                    j += 1
                cell(ci, r, wc=j - ci)
                ci = j
        eh = 1 if pose["blink"] else 2
        for ecol in (3, 11):
            cell(ecol + pose["eye_dx"], 5 + pose["eye_dy"], wc=2, hr=eh, color=EYE)
        if pose["mouth"] == "open":              # yawn / dismay
            cell(7, 7, wc=2, hr=2, color=EYE)
        else:                                    # white smile, corners up
            for sc, sr in [(6, 7), (9, 7), (7, 8), (8, 8)]:
                cell(sc, sr, color=SMILE)
        if pose.get("zzz"):                      # sleepy z's drifting up
            for k in range(3):
                ph = (self.frame * 0.035 + k * 0.34) % 1.0
                zx = top_x + (13 + k * 1.4) * sxp
                zy = top_y - 4 - ph * 30
                c.create_text(zx, zy, text="z", fill=CORAL,
                              font=("Courier New", 9 + k * 2, "bold"))
        if pose.get("emote"):                    # a rising stream of symbols,
            sym = pose["emote"]                  # high above his head, colourful
            trail = sym in ("♪", "♫")            # only the music notes get trails
            cx = top_x + bw / 2 + 8
            for k in range(3):
                ph = (self.frame * 0.022 + k * 0.34) % 1.0   # 0..1 rise + recycle
                rise = 18 + ph * 52                          # floats 18..70 px up
                drift = math.sin(ph * 5.0 + k * 2.1) * 8
                ex, ey = cx + drift, top_y - rise
                col = DVD_COLORS[(k * 3 + self.frame // 14) % len(DVD_COLORS)]
                size = max(9, 16 - int(ph * 6))
                fade = math.sin(ph * math.pi)                # fade in + out
                if fade <= 0.08:
                    continue
                if trail:                                    # short wind trail below
                    c.create_line(ex, ey + size * 0.5,
                                  ex - drift * 0.35, ey + size * 0.5 + 13,
                                  fill=col, width=2)
                c.create_text(ex, ey, text=sym, anchor="center", fill=col,
                              font=("Courier New", size, "bold"))

    def _arm(self, cell, col0, lift, limb=LIMB):
        row = 4 - 3 * lift
        cell(col0, row, wc=4, hr=1, color=limb)
        cell(col0, row + 1, wc=4, hr=1, color=limb)

    def _legs(self, cell, pose, limb=LIMB):
        ki, ka, bdir = pose["kick_idx"], pose["kick_amt"], pose["ball_dir"]
        ft = pose.get("foot_tap")                # (leg_index, amount) or None
        for i, col in enumerate(LEG_COLS):
            if i == ki and ka > 0.02:            # this leg extends up to kick it
                for t in (0.0, 0.45, 0.9):       # hip -> raised foot, toward ball
                    lx = col + bdir * 2.0 * ka * t
                    ly = 10 - 3.4 * ka * t
                    cell(lx, ly, wc=2, hr=1.5, color=limb)
            elif ft is not None and ft[0] == i:  # this foot taps the ground
                cell(col, 10 - ft[1] * 2.4, wc=2, hr=2, color=limb)
            else:
                ly = 10 + max(0.0, 0.12 * math.sin(self.frame * 0.5 + i))
                cell(col, ly, wc=2, hr=2, color=limb)

    def draw_hud(self, c, hud):
        # a coral-orange panel so the HUD reads as a bar, not floating bits
        ph = 30 if hud["clock"] is not None else 23
        c.create_rectangle(4, 4, W - 4, 4 + ph, fill=CORAL, outline=ACCENT)
        for i in range(3):                       # lives (red hearts)
            col = HEART if i < hud["lives"] else HEART_DK
            x = 11 + i * 13
            c.create_rectangle(x, 12, x + 9, 19, fill=col, outline=col)
            c.create_rectangle(x + 2, 10, x + 7, 12, fill=col, outline=col)
        c.create_text(W - 11, 9, text=f"x{hud['streak']}", anchor="ne",
                      font=("Courier New", 12, "bold"), fill="#ffffff")
        if hud["clock"] is not None:             # shot clock draining (white)
            full = W - 22
            c.create_rectangle(11, 25, 11 + full, 30, fill=ACCENT, outline="")
            c.create_rectangle(11, 25, 11 + full * hud["clock"], 30,
                               fill="#ffffff", outline="")

    def draw_bubble(self, c, text, color, anchor_top):
        pad, maxw = 8, W - 20
        tid = c.create_text(-1000, -1000, text=text, width=maxw - 2 * pad,
                            font=("Courier New", 10, "bold"), fill=BUBBLE_TX,
                            justify="center")
        bx1, by1, bx2, by2 = c.bbox(tid)
        bw, bh = (bx2 - bx1) + 2 * pad, (by2 - by1) + 2 * pad
        x1 = max(6, min(self.center_x - bw / 2, W - 6 - bw))
        x2 = x1 + bw
        y2 = anchor_top - 10
        y1 = y2 - bh
        if y1 < 4:
            y2 += 4 - y1
            y1 = 4
        cx = self.center_x
        c.create_polygon(cx - 6, y2, cx + 6, y2, cx, y2 + 9,
                         fill=color, outline=BUBBLE_BORDER)
        c.create_rectangle(x1 - 2, y1 - 2, x2 + 2, y2 + 2,
                           fill=BUBBLE_BORDER, outline=BUBBLE_BORDER)
        c.create_rectangle(x1, y1, x2, y2, fill=color, outline=color)
        c.coords(tid, (x1 + x2) / 2, (y1 + y2) / 2)
        c.tag_raise(tid)

    # ---- interaction -----------------------------------------------------
    def on_press(self, e):
        self.dragging = True
        self.moved = 0
        self._press = (e.x_root, e.y_root)
        self._origin = (self.x, self.y)

    def on_drag(self, e):
        dx = e.x_root - self._press[0]
        dy = e.y_root - self._press[1]
        self.moved += abs(dx) + abs(dy)
        self.x = self._origin[0] + dx
        self.y = self._origin[1] + dy
        if self.mode == "dvd":                       # keep him in the field
            x0, y0, x1, y1 = self.screen_bounds()
            self.x = clamp(self.x, x0, x1 - W)
            self.y = clamp(self.y, y0, y1 - H)
        self.root.geometry(f"+{int(self.x)}+{int(self.y)}")

    def on_release(self, e):
        self.dragging = False
        if self.mode == "dvd" and self.moved >= 6:
            # repositioned by hand: tuck him just inside and don't credit a corner
            x0, y0, x1, y1 = self.screen_bounds()
            self.x = clamp(self.x, x0 + 3, x1 - W - 3)
            self.y = clamp(self.y, y0 + 3, y1 - H - 3)
            self.root.geometry(f"+{int(self.x)}+{int(self.y)}")
            self.dvd_drag_grace = time.time() + 0.6
            return
        if self.moved >= 6:
            return
        self.excited_until = time.time() + 1.5
        if self.mode == "rally" and self.rally_state == "over":
            self.start_rally()                   # click to play again
            return
        if self.mode == "rally":
            self.show_bubble("eyes on the ball!", 1.2)
            self.play(PAT_TUNE)
            return
        if self.mode == "dvd":                   # boop mid-glide: just a cheer
            self.show_bubble(random.choice(("wheee!", "zoom!", "boing!")), 1.0)
            self.play(PAT_TUNE)
            return
        if self.idle_phase == "free" and not self.ball_loose:
            # a boop wakes him from relaxing: drop the rest and fetch the ball
            self.static_queue = []
            self.static_kind = None
            self.show_bubble(random.choice(PAT_REACTIONS), 1.2)
            self.play(PAT_TUNE)
            return
        self.show_bubble(random.choice(PAT_REACTIONS), 1.5)
        self.react_kind = random.choice(("squash", "hop", "spin", "wiggle"))
        self.react_t0 = time.time()
        self.fidget_kind = None                  # a pat interrupts any light fidget
        self.next_fidget = time.time() + random.uniform(5, 9)
        self.play(PAT_TUNE)
        if self.needs_break:
            self.needs_break = False
            self.next_break = time.time() + self.interval * 60

    # ---- wandering -------------------------------------------------------
    def step_wander(self, now):
        x0, y0, x1, y1 = self.screen_bounds()
        if self.wander_target is None or now >= self.next_wander:
            tx = random.randint(int(x0), max(int(x0), int(x1) - W))
            ty = random.randint(int(y0), max(int(y0), int(y1) - H - 50))
            self.wander_target = (tx, ty)
            self.next_wander = now + random.uniform(10, 20)
        tx, ty = self.wander_target
        self.x += (tx - self.x) * 0.01
        self.y += (ty - self.y) * 0.01
        self.root.geometry(f"+{int(self.x)}+{int(self.y)}")

    # ---- timers ----------------------------------------------------------
    def tick(self):
        now = time.time()
        if self.break_enabled and now >= self.next_break:
            self.trigger_break()
            self.next_break = now + self.interval * 60
        if self.oneoff_at and now >= self.oneoff_at:
            label = self.oneoff_label or "Timer's up"
            self.show_bubble(f"[!] {label}!", 25)
            self.play(TIMER_TUNE)
            self.oneoff_at = None
            self._frantic_kick(now)
        self.root.after(1000, self.tick)

    def _frantic_kick(self, now=None):
        """Loop the ball frantically across EVERY monitor — fires even muted.
        Big, slow, alternating left/right sweeps so it's impossible to miss."""
        if self.mode in ("penalty", "rally", "dvd"):
            return
        now = now or time.time()
        self._hide_ball()
        self.bx, self.by = self.pethead()            # first sweep starts at the head
        self.excited_until = now + 12.0
        self._frantic_n = 6                          # six big sweeps
        self._frantic_loop()

    def _frantic_loop(self):
        """Chain the frantic sweeps, alternating far walls, then fetch it home."""
        if self.mode in ("penalty", "rally", "dvd"):
            return
        n = self._frantic_n
        if n <= 0:                                   # done — go fetch the rebound
            if self.ball_loose:
                self.loose_kind = "return"
                self._phys_t = time.time()
            return
        self._frantic_n = n - 1
        vx0, _, vx1, _ = self._virtual_bounds()      # span ALL monitors
        edge = vx1 if (n % 2 == 1) else vx0          # alternate far walls
        dur = random.uniform(1.0, 1.3)               # slow enough to follow
        # each sweep starts where the last one left off, so it never jumps
        self._loop_to("frantic", (self.bx, self.by), edge,
                      height=260, arc=360, dur=dur)
        self.root.after(int(dur * 1000) + 25, self._frantic_loop)

    def trigger_break(self):
        self.show_bubble(random.choice(BREAK_MESSAGES), 25)
        self.needs_break = True
        self.play(BREAK_TUNE)
        self._frantic_kick()

    # ---- dialogs ---------------------------------------------------------
    def _dialog_open(self, flag):
        self._modal = flag
        self.root.attributes("-topmost", not flag)
        if self.ball_win is not None:
            try:
                self.ball_win.attributes("-topmost", not flag)
            except tk.TclError:
                pass

    def _ask_int(self, title, prompt, initial, lo, hi):
        self._dialog_open(True)
        v = simpledialog.askinteger(title, prompt, initialvalue=initial,
                                    minvalue=lo, maxvalue=hi, parent=self.root)
        self._dialog_open(False)
        return v

    def _ask_str(self, title, prompt):
        self._dialog_open(True)
        v = simpledialog.askstring(title, prompt, parent=self.root)
        self._dialog_open(False)
        return v

    def set_interval(self):
        v = self._ask_int("Break interval", "Minutes between breaks:",
                          self.interval, 1, 600)
        if v:
            self.interval = v
            self.next_break = time.time() + v * 60
            self.break_enabled = True
            self.show_bubble(f"Okay - every {v} min", 3)

    def set_oneoff(self):
        v = self._ask_int("Set a timer", "Remind me in how many minutes?",
                          10, 1, 1440)
        if not v:
            return
        label = self._ask_str("Set a timer", "What's it for? (optional)")
        self.oneoff_at = time.time() + v * 60
        self.oneoff_label = (label or "").strip()
        tag = f" ({self.oneoff_label})" if self.oneoff_label else ""
        self.show_bubble(f"Timer set: {v} min{tag}", 3)

    def break_now(self):
        self.needs_break = False
        self.next_break = time.time() + self.interval * 60
        self.show_bubble("Enjoy your break!", 3)

    def toggle_breaks(self):
        self.break_enabled = not self.break_enabled
        if self.break_enabled:
            self.next_break = time.time() + self.interval * 60
            self.show_bubble("Break reminders on", 3)
        else:
            self.show_bubble("Break reminders paused", 3)

    def toggle_wander(self):
        self.wander = not self.wander
        self.wander_target = None
        self.show_bubble("off for a wander!" if self.wander else "staying put",
                         2)

    def toggle_mute(self):
        self.muted = not self.muted
        self.show_bubble("sounds muted" if self.muted else "sounds on", 2)
        if not self.muted:
            self.play(TIMER_TUNE)

    # ---- menu ------------------------------------------------------------
    def toggle_rally(self):
        if self.mode == "rally":
            best = self.best_streak
            self.stop_game()
            self.show_bubble(f"good game! best streak {best}", 3)
        else:
            self.start_rally()

    def toggle_penalty(self):
        if self.mode == "penalty":
            best = self.pen_best
            self.stop_penalty()
            self.show_bubble(f"penalty over - best streak {best}", 3)
        else:
            self.start_penalty()

    def toggle_dvd(self):
        if self.mode == "dvd":
            c = self.dvd_corners
            self.stop_dvd()
            self.show_bubble(f"DVD off - {c} corner{'s' if c != 1 else ''}!", 3)
        else:
            self.start_dvd()

    def quit(self):
        for w in (self.ball_win, self.arena):
            if w is not None:
                try:
                    w.destroy()
                except tk.TclError:
                    pass
        self.ball_win = self.arena = None
        self.root.destroy()

    def show_menu(self, e):
        now = time.time()
        m = tk.Menu(self.root, tearoff=0)
        if self.mode == "rally":
            m.add_command(
                label=f"{PET_NAME} - rally x{self.streak}  lives {self.lives}",
                state="disabled")
        elif self.mode == "penalty":
            m.add_command(
                label=f"{PET_NAME} - penalty streak {self.pen_goals}",
                state="disabled")
        elif self.mode == "dvd":
            m.add_command(
                label=f"{PET_NAME} - DVD: {self.dvd_corners} corners",
                state="disabled")
        elif self.break_enabled:
            mins = max(0, math.ceil((self.next_break - now) / 60))
            m.add_command(label=f"{PET_NAME} - next break in {mins} min",
                          state="disabled")
        else:
            m.add_command(label=f"{PET_NAME} - breaks paused", state="disabled")
        if self.oneoff_at:
            mins = max(0, math.ceil((self.oneoff_at - now) / 60))
            lbl = self.oneoff_label or "timer"
            m.add_command(label=f"  {lbl}: {mins} min left", state="disabled")
        m.add_separator()
        if self.mode == "rally":
            m.add_command(label="Stop football game", command=self.toggle_rally)
        elif self.mode == "penalty":
            m.add_command(label="Stop penalty shootout", command=self.toggle_penalty)
        elif self.mode == "dvd":
            m.add_command(label="Stop DVD mode", command=self.toggle_dvd)
        else:
            m.add_command(label="Play football!", command=self.toggle_rally)
            m.add_command(label="Penalty shootout", command=self.toggle_penalty)
            m.add_command(label="DVD bounce mode", command=self.toggle_dvd)
        m.add_separator()
        m.add_command(label="Take a break now", command=self.break_now)
        m.add_command(
            label=("Pause break reminders" if self.break_enabled
                   else "Resume break reminders"),
            command=self.toggle_breaks)
        m.add_command(label="Set break interval...", command=self.set_interval)
        m.add_command(label="Set a one-off timer...", command=self.set_oneoff)
        m.add_separator()
        m.add_command(label=("Unmute sounds" if self.muted else "Mute sounds"),
                      command=self.toggle_mute)
        snd = tk.Menu(m, tearoff=0)              # Customize sounds submenu
        for action, label, _tune in SOUND_ACTIONS:
            custom = bool(self.sound_cfg.get(action))
            sub = tk.Menu(snd, tearoff=0)
            sub.add_command(label="Choose WAV file...",
                            command=lambda a=action, l=label: self.set_action_sound(a, l))
            sub.add_command(label="Reset to default beep",
                            command=lambda a=action, l=label: self.clear_action_sound(a, l))
            snd.add_cascade(label=f"{label}{'  *' if custom else ''}", menu=sub)
        snd.add_separator()
        snd.add_command(label="Reset all to default beeps", command=self.reset_sounds)
        m.add_cascade(label="Customize sounds", menu=snd)
        m.add_command(
            label=("[on] Wander mode" if self.wander else "Wander mode"),
            command=self.toggle_wander)
        m.add_separator()
        m.add_command(label="Quit", command=self.quit)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()


def main():
    root = tk.Tk()
    DesktopPet(root)
    root.mainloop()


if __name__ == "__main__":
    main()
