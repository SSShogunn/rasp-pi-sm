#!/usr/bin/env python3
"""
Pi Zero 2W Dashboard  –  sleek dark UI
Pages: 1=System  2=Network
Keys:  Up/Down   = navigate pages (normal) / adjust value (settings)
       Left/Right = switch setting item (settings only)
       KEY2 = settings menu  KEY3 = refresh  any = wake
Run:   cd python && sudo python3 monitor.py
Deps:  sudo apt install python3-pil python3-numpy python3-gpiozero python3-spidev
"""

import time, signal, threading, subprocess
from PIL import Image, ImageDraw, ImageFont
import LCD_1in44

# ── config ────────────────────────────────────────────────────────────────────
PAGES         = 2
REFRESH       = 5
SLEEP_PRESETS = [10, 20, 30, 60, 120, 300, 0]   # seconds; 0 = never
SLEEP_LABELS  = ["10s", "20s", "30s", "1m", "2m", "5m", "Off"]
W = H         = 128

# ── palette ───────────────────────────────────────────────────────────────────
BG       = ( 10,  10,  20)
HDR_SYS  = (  0,  35,  55)
HDR_NET  = (  0,  45,  22)
HDR_SET  = ( 25,  10,  40)
ACC_SYS  = (  0, 195, 255)
ACC_NET  = (  0, 215, 105)
ACC_SET  = (180,  80, 255)
TRACK    = ( 28,  30,  45)
C_CPU    = (  0, 190, 255)
C_RAM    = (145,  85, 255)
C_DISK   = (255, 170,   0)
C_OK     = (  0, 215, 105)
C_WARN   = (255, 190,   0)
C_HOT    = (255,  60,  60)
T_PRI    = (220, 225, 238)
T_SEC    = (100, 110, 132)
T_DIM    = ( 55,  62,  80)
SEP_C    = ( 32,  36,  52)
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
    d.text((4, y), label, font=F_LABEL, fill=T_SEC)
    vx = W - _tw(d, val_str, F_VAL) - 4
    d.text((vx, y), val_str, font=F_VAL, fill=T_PRI)
    _bar(d, 4, y + 12, W - 8, 4, pct, bar_color)

def _header(d, title, accent, hdr_bg):
    d.rectangle([0, 0, W - 1, 15], fill=hdr_bg)
    d.rectangle([0, 0, 3, 15], fill=accent)
    d.text((8, 3), title, font=F_HDR, fill=T_PRI)
    pg = f"{page + 1}/{PAGES}"
    d.text((W - _tw(d, pg, F_FOOT) - 4, 4), pg, font=F_FOOT, fill=T_DIM)

def _footer(d):
    _sep(d, 112)
    d.text((4, 115), time.strftime("%H:%M"), font=F_FOOT, fill=T_DIM)

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

# ── settings page ─────────────────────────────────────────────────────────────
def draw_settings():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    # header
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=ACC_SET)
    d.text((8, 3), "SETTINGS", font=F_HDR, fill=T_PRI)
    hint = "KEY2=exit"
    d.text((W - _tw(d, hint, F_FOOT) - 4, 4), hint, font=F_FOOT, fill=T_DIM)

    n = len(SLEEP_PRESETS) - 1
    sleep_bar_pct = int(sleep_idx * 100 // n) if n else 100

    items = [
        ("BRIGHTNESS", f"{bl_pct}%",             bl_pct),
        ("SLEEP TIME",  SLEEP_LABELS[sleep_idx],  sleep_bar_pct),
    ]

    y = 20
    for i, (label, val_str, bar_pct) in enumerate(items):
        sel     = (settings_sel == i)
        lbl_col = ACC_SET if sel else T_SEC
        val_col = T_PRI   if sel else T_DIM
        bar_col = ACC_SET if sel else TRACK

        if sel:
            d.rectangle([0, y - 2, 3, y + 22], fill=ACC_SET)

        d.text((6, y), label, font=F_LABEL, fill=lbl_col)
        d.text((W - _tw(d, val_str, F_VAL) - 4, y), val_str, font=F_VAL, fill=val_col)
        _bar(d, 6, y + 13, W - 12, 4, bar_pct, bar_col)

        y += 30
        _sep(d, y)
        y += 6

    # control hints
    d.text((4, y + 4),  "UP/DN : switch", font=F_FOOT, fill=T_DIM)
    d.text((4, y + 15), "L/R   : adjust", font=F_FOOT, fill=T_DIM)

    _footer(d)
    return img

# ── LCD + state ───────────────────────────────────────────────────────────────
lcd           = LCD_1in44.LCD()
lcd.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
lcd.LCD_Clear()

_lock         = threading.Lock()
page          = 0
bl_pct        = 60          # brightness 10–100
sleeping      = False
last_activity = time.time()
settings_open = False
settings_sel  = 0           # 0 = brightness, 1 = sleep time
sleep_idx     = 0           # index into SLEEP_PRESETS

def render():
    if settings_open:
        img = draw_settings()
    elif page == 0:
        img = draw_system()
    else:
        img = draw_network()
    with _lock:
        lcd.LCD_ShowImage(img)

def _touch():
    global last_activity
    last_activity = time.time()

def _wake_if_sleeping():
    global sleeping
    _touch()
    if sleeping:
        sleeping = False
        with _lock:
            lcd.bl_DutyCycle(bl_pct)
        render()
        return True
    return False

# ── button callbacks ──────────────────────────────────────────────────────────
def _up():
    global page, settings_sel
    if _wake_if_sleeping(): return
    _touch()
    if settings_open:
        settings_sel = (settings_sel - 1) % 2
    else:
        page = (page - 1) % PAGES
        if page == 0: fetch_system()
        else:         fetch_network()
    render()

def _down():
    global page, settings_sel
    if _wake_if_sleeping(): return
    _touch()
    if settings_open:
        settings_sel = (settings_sel + 1) % 2
    else:
        page = (page + 1) % PAGES
        if page == 0: fetch_system()
        else:         fetch_network()
    render()

def _left():
    global bl_pct, sleep_idx
    if _wake_if_sleeping(): return
    _touch()
    if settings_open:
        if settings_sel == 0:
            bl_pct = max(10, bl_pct - 10)
            with _lock:
                lcd.bl_DutyCycle(bl_pct)
        else:
            sleep_idx = max(0, sleep_idx - 1)
        render()

def _right():
    global bl_pct, sleep_idx
    if _wake_if_sleeping(): return
    _touch()
    if settings_open:
        if settings_sel == 0:
            bl_pct = min(100, bl_pct + 10)
            with _lock:
                lcd.bl_DutyCycle(bl_pct)
        else:
            sleep_idx = min(len(SLEEP_PRESETS) - 1, sleep_idx + 1)
        render()

def _toggle_settings():
    global settings_open
    if _wake_if_sleeping(): return
    _touch()
    settings_open = not settings_open
    render()

def _refresh():
    if _wake_if_sleeping(): return
    _touch()
    if settings_open:
        return
    if page == 0: fetch_system()
    else:         fetch_network()
    render()

lcd.GPIO_KEY_UP_PIN.when_activated    = _up
lcd.GPIO_KEY_DOWN_PIN.when_activated  = _down
lcd.GPIO_KEY_LEFT_PIN.when_activated  = _left
lcd.GPIO_KEY_RIGHT_PIN.when_activated = _right
lcd.GPIO_KEY2_PIN.when_activated      = _toggle_settings
lcd.GPIO_KEY3_PIN.when_activated      = _refresh

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
    lcd.bl_DutyCycle(bl_pct)
render()
print("Running – Ctrl-C to quit")

last_sys = last_net = time.time()

try:
    while running:
        now = time.time()

        if not sleeping and not settings_open:
            if page == 0 and now - last_sys >= REFRESH:
                fetch_system()
                last_sys = time.time()
                render()
            elif page == 1 and now - last_net >= REFRESH:
                fetch_network()
                last_net = time.time()
                render()

        sleep_secs = SLEEP_PRESETS[sleep_idx]
        if not sleeping and sleep_secs > 0 and (now - last_activity) >= sleep_secs:
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
