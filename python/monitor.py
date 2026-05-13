#!/usr/bin/env python3
"""
Pi Zero 2W Dashboard  –  sleek dark UI
Pages: 1=System  2=Network
Keys:  Up/Down = navigate  KEY2 = refresh  KEY3 = brightness  any = wake
Run:   cd python && sudo python3 monitor.py
Deps:  sudo apt install python3-pil python3-numpy python3-gpiozero python3-spidev
"""

import time, signal, threading, subprocess
from PIL import Image, ImageDraw, ImageFont
import LCD_1in44

# ── config ────────────────────────────────────────────────────────────────────
PAGES      = 2
REFRESH    = 5          # seconds between auto-refresh
SLEEP_SECS = 10         # seconds idle before backlight off
BL_LEVELS  = [20, 60, 100]
W = H      = 128

# ── palette ───────────────────────────────────────────────────────────────────
BG       = ( 10,  10,  20)   # near-black navy canvas
HDR_SYS  = (  0,  35,  55)   # dark teal header
HDR_NET  = (  0,  45,  22)   # dark green header
ACC_SYS  = (  0, 195, 255)   # electric cyan accent
ACC_NET  = (  0, 215, 105)   # electric green accent
TRACK    = ( 28,  30,  45)   # bar background track
C_CPU    = (  0, 190, 255)
C_RAM    = (145,  85, 255)
C_DISK   = (255, 170,   0)
C_OK     = (  0, 215, 105)
C_WARN   = (255, 190,   0)
C_HOT    = (255,  60,  60)
T_PRI    = (220, 225, 238)   # primary text
T_SEC    = (100, 110, 132)   # secondary label
T_DIM    = ( 55,  62,  80)   # very dim (footer, minor labels)
SEP_C    = ( 32,  36,  52)   # separator line
C_WIFI   = (255, 205,  55)
C_USB    = (  0, 215, 215)
C_TS     = ( 90, 162, 255)

# ── fonts ─────────────────────────────────────────────────────────────────────
def _font(name, size):
    for d in ("/usr/share/fonts/truetype/dejavu/",
              "/usr/share/fonts/truetype/ttf-bitstream-vera/"):
        try:
            return ImageFont.truetype(d + name, size)
        except OSError:
            pass
    return ImageFont.load_default()

F_HDR   = _font("DejaVuSans-Bold.ttf",  9)
F_LABEL = _font("DejaVuSans.ttf",       8)
F_VAL   = _font("DejaVuSans-Bold.ttf",  9)
F_IP    = _font("DejaVuSans.ttf",       9)
F_FOOT  = _font("DejaVuSans.ttf",       8)

# ── data ──────────────────────────────────────────────────────────────────────
data = dict(cpu="--", ram="--", temp="--", disk="--", uptime="...",
            wip="...", uip="...", tip="...")

def _run(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL, timeout=8
        ).decode().strip()
    except Exception:
        return ""

def fetch_system():
    data["cpu"]    = _run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1") or "--"
    data["ram"]    = _run("free | grep Mem | awk '{printf \"%.0f\", $3/$2*100}'") or "--"
    data["temp"]   = _run("vcgencmd measure_temp | cut -d'=' -f2 | tr -d \"'C\"") or "--"
    data["disk"]   = _run("df / | tail -1 | awk '{print $5}' | tr -d '%'") or "--"
    data["uptime"] = (_run("uptime -p | sed 's/up //'") or "N/A")[:18]

def fetch_network():
    data["wip"] = _run("ip -4 addr show wlan0 2>/dev/null | grep inet | awk '{print $2}' | cut -d'/' -f1") or "N/A"
    data["uip"] = _run("ip -4 addr show usb0  2>/dev/null | grep inet | awk '{print $2}' | cut -d'/' -f1") or "N/A"
    data["tip"] = _run("tailscale ip -4 2>/dev/null") or "N/A"

# ── draw primitives ───────────────────────────────────────────────────────────
def _tw(d, text, font):
    try:
        return int(d.textlength(text, font=font))
    except AttributeError:
        return font.getsize(text)[0]

def _sep(d, y):
    d.line([(0, y), (W - 1, y)], fill=SEP_C)

def _bar(d, x, y, w, h, pct, color):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=TRACK)
    if pct > 0:
        fw = max(2, int((w - 2) * min(pct, 100) / 100))
        d.rectangle([x + 1, y + 1, x + fw, y + h - 2], fill=color)

def _bar_row(d, y, label, val_str, pct, bar_color):
    """Label left + value right-aligned on same line, then thin bar below."""
    d.text((4, y), label, font=F_LABEL, fill=T_SEC)
    vx = W - _tw(d, val_str, F_VAL) - 4
    d.text((vx, y), val_str, font=F_VAL, fill=T_PRI)
    _bar(d, 4, y + 12, W - 8, 4, pct, bar_color)

def _header(d, title, accent, hdr_bg):
    d.rectangle([0, 0, W - 1, 15], fill=hdr_bg)
    d.rectangle([0, 0, 3, 15], fill=accent)          # left accent stripe
    d.text((8, 3), title, font=F_HDR, fill=T_PRI)
    pg = f"{page + 1}/{PAGES}"
    d.text((W - _tw(d, pg, F_FOOT) - 4, 4), pg, font=F_FOOT, fill=T_DIM)

def _footer(d):
    _sep(d, 112)
    now = time.strftime("%H:%M")
    d.text((4, 115), now, font=F_FOOT, fill=T_DIM)

# ── page 1 – system ───────────────────────────────────────────────────────────
def draw_system():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "SYSTEM", ACC_SYS, HDR_SYS)

    y = 18
    for label, key, bar_col in (("CPU",  "cpu",  C_CPU),
                                  ("RAM",  "ram",  C_RAM),
                                  ("DISK", "disk", C_DISK)):
        try:   pct = int(float(data[key]))
        except: pct = 0
        _bar_row(d, y, label, f"{data[key]}%", pct, bar_col)
        y += 21

    _sep(d, y)
    y += 4

    try:   t = float(data["temp"])
    except: t = 0.0
    t_col = C_HOT if t >= 70 else (C_WARN if t >= 55 else C_OK)
    d.text((4, y), "TEMP", font=F_LABEL, fill=T_SEC)
    d.text((30, y), f"{data['temp']} C", font=F_VAL, fill=t_col)
    y += 13

    d.text((4, y), data["uptime"], font=F_LABEL, fill=T_DIM)

    _footer(d)
    return img

# ── page 2 – network ──────────────────────────────────────────────────────────
def draw_network():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "NETWORK", ACC_NET, HDR_NET)

    y = 19
    for label, key, col in (("WIFI",      "wip", C_WIFI),
                              ("USB",       "uip", C_USB),
                              ("TAILSCALE", "tip", C_TS)):
        d.text((4, y), label, font=F_LABEL, fill=T_DIM)
        y += 12
        d.text((4, y), data[key], font=F_IP, fill=col)
        y += 14
        _sep(d, y + 1)
        y += 5

    _footer(d)
    return img

# ── LCD + state ───────────────────────────────────────────────────────────────
lcd           = LCD_1in44.LCD()
lcd.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
lcd.LCD_Clear()

_lock         = threading.Lock()
page          = 0
bl_idx        = 1
sleeping      = False
last_activity = time.time()

def render():
    img = draw_system() if page == 0 else draw_network()
    with _lock:
        lcd.LCD_ShowImage(img)

def _touch():
    global last_activity
    last_activity = time.time()

def _wake_if_sleeping():
    """Returns True if display was asleep (caller should skip its action)."""
    global sleeping
    _touch()
    if sleeping:
        sleeping = False
        with _lock:
            lcd.bl_DutyCycle(BL_LEVELS[bl_idx])
        render()
        return True
    return False

# ── button callbacks ──────────────────────────────────────────────────────────
def _navigate(direction):
    global page
    if _wake_if_sleeping(): return
    _touch()
    page = (page + direction) % PAGES
    if page == 0: fetch_system()
    else:         fetch_network()
    render()

def _refresh():
    if _wake_if_sleeping(): return
    _touch()
    if page == 0: fetch_system()
    else:         fetch_network()
    render()

def _brightness():
    global bl_idx
    if _wake_if_sleeping(): return
    _touch()
    bl_idx = (bl_idx + 1) % len(BL_LEVELS)
    with _lock:
        lcd.bl_DutyCycle(BL_LEVELS[bl_idx])

lcd.GPIO_KEY_UP_PIN.when_activated   = lambda: _navigate(-1)
lcd.GPIO_KEY_DOWN_PIN.when_activated = lambda: _navigate(+1)
lcd.GPIO_KEY2_PIN.when_activated     = _refresh
lcd.GPIO_KEY3_PIN.when_activated     = _brightness

# ── signal + main loop ────────────────────────────────────────────────────────
running = True

def _sig(s, f):
    global running
    running = False

signal.signal(signal.SIGINT,  _sig)
signal.signal(signal.SIGTERM, _sig)

print("Fetching initial data...")
fetch_system()
fetch_network()
with _lock:
    lcd.bl_DutyCycle(BL_LEVELS[bl_idx])
render()
print("Running – Ctrl-C to quit")

last_sys = last_net = time.time()

try:
    while running:
        now = time.time()

        if not sleeping:
            if page == 0 and now - last_sys >= REFRESH:
                fetch_system()
                last_sys = time.time()
                render()
            elif page == 1 and now - last_net >= REFRESH:
                fetch_network()
                last_net = time.time()
                render()

            if (now - last_activity) >= SLEEP_SECS:
                sleeping = True
                with _lock:
                    lcd.bl_DutyCycle(0)

        time.sleep(0.1)
finally:
    print("\nShutting down...")
    with _lock:
        lcd.bl_DutyCycle(0)
        lcd.LCD_Clear()
        lcd.module_exit()
