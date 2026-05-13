#!/usr/bin/env python3
"""
Pi Zero 2W Simple Dashboard  –  Python version
Pages   :  1 = System Stats   2 = Network Info
Controls:  Joystick Up/Down   → navigate pages
           KEY2  (GPIO 20)    → force refresh
           KEY3  (GPIO 16)    → cycle brightness  20 → 60 → 100 %
Run     :  cd python && sudo python3 monitor.py
Deps    :  sudo apt install python3-pil python3-numpy python3-gpiozero python3-spidev
"""

import os
import sys
import time
import signal
import threading
import subprocess

from PIL import Image, ImageDraw, ImageFont
from gpiozero import Button
import LCD_1in44

# ── config ────────────────────────────────────────────────────────────────────
PAGES        = 2
REFRESH_SECS = 5
BL_LEVELS    = [20, 60, 100]   # percent

# RGB colours
BLACK  = (  0,   0,   0)
WHITE  = (255, 255, 255)
GRAY   = (120, 120, 120)
GREEN  = (  0, 210,   0)
BLUE   = (  0, 120, 255)
YELLOW = (255, 220,   0)
CYAN   = (  0, 210, 210)
RED    = (220,   0,   0)
TEAL   = ( 80, 180, 255)

# ── font loading ──────────────────────────────────────────────────────────────
def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()

_BASE = "/usr/share/fonts/truetype/dejavu/"
F_SM   = _font(_BASE + "DejaVuSans.ttf",      10)
F_MD   = _font(_BASE + "DejaVuSans.ttf",      12)
F_BOLD = _font(_BASE + "DejaVuSans-Bold.ttf", 11)

# ── system data (populated by fetch_* outside of render) ─────────────────────
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
    data["uptime"] = (_run("uptime -p | sed 's/up //'") or "N/A")[:20]

def fetch_network():
    data["wip"] = _run("ip -4 addr show wlan0 2>/dev/null | grep inet | awk '{print $2}' | cut -d'/' -f1") or "N/A"
    data["uip"] = _run("ip -4 addr show usb0  2>/dev/null | grep inet | awk '{print $2}' | cut -d'/' -f1") or "N/A"
    data["tip"] = _run("tailscale ip -4 2>/dev/null") or "N/A"

# ── drawing helpers ───────────────────────────────────────────────────────────
def _bar(d, x, y, w, h, pct, color):
    d.rectangle([x, y, x + w - 1, y + h - 1], outline=GRAY)
    if pct > 0:
        fw = max(1, int((w - 2) * min(pct, 100) / 100))
        d.rectangle([x + 1, y + 1, x + fw, y + h - 2], fill=color)

def _footer(d, label):
    now = time.strftime("%H:%M")
    d.text((2, 119), now,   font=F_SM, fill=GRAY)
    d.text((104, 119), label, font=F_SM, fill=GRAY)

# ── pages ─────────────────────────────────────────────────────────────────────
def draw_system():
    img = Image.new("RGB", (128, 128), BLACK)
    d   = ImageDraw.Draw(img)

    d.rectangle([0, 0, 127, 14], fill=CYAN)
    d.text((4, 2), "SYSTEM STATS", font=F_BOLD, fill=BLACK)

    y = 18
    for label, key, color in (("CPU ", "cpu", GREEN), ("RAM ", "ram", BLUE), ("Disk", "disk", YELLOW)):
        try:   val = int(float(data[key]))
        except: val = 0
        d.text((4, y), f"{label}  {data[key]}%", font=F_SM, fill=WHITE)
        y += 11
        _bar(d, 4, y, 120, 6, val, color)
        y += 9

    try:   t = float(data["temp"])
    except: t = 0.0
    t_col = RED if t >= 70 else (YELLOW if t >= 55 else GREEN)
    d.text((4, y), f"Temp  {data['temp']} C", font=F_SM, fill=t_col)
    y += 12
    d.text((4, y), f"Up: {data['uptime']}",   font=F_SM, fill=GRAY)

    _footer(d, "1/2")
    return img

def draw_network():
    img = Image.new("RGB", (128, 128), BLACK)
    d   = ImageDraw.Draw(img)

    d.rectangle([0, 0, 127, 14], fill=(0, 180, 0))
    d.text((4, 2), "NETWORK", font=F_BOLD, fill=BLACK)

    y = 20
    for label, key, color in (("WiFi IP", "wip", YELLOW), ("USB IP", "uip", CYAN), ("Tailscale", "tip", TEAL)):
        d.text((4, y), label,      font=F_SM, fill=GRAY)
        y += 12
        d.text((4, y), data[key],  font=F_MD, fill=color)
        y += 16

    _footer(d, "2/2")
    return img

# ── LCD init ──────────────────────────────────────────────────────────────────
lcd  = LCD_1in44.LCD()
lcd.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
lcd.LCD_Clear()

_lock  = threading.Lock()   # guard concurrent SPI access from button threads
page   = 0
bl_idx = 1                  # start at 60 %

def render():
    img = draw_system() if page == 0 else draw_network()
    with _lock:
        lcd.LCD_ShowImage(img)

# ── buttons  (gpiozero handles pull-up + bounce internally) ──────────────────
btn_up   = Button(6,  pull_up=True, bounce_time=0.12)
btn_down = Button(19, pull_up=True, bounce_time=0.12)
btn_key2 = Button(20, pull_up=True, bounce_time=0.12)
btn_key3 = Button(16, pull_up=True, bounce_time=0.12)

def _navigate(direction):
    global page
    page = (page + direction) % PAGES
    if page == 0: fetch_system()
    else:         fetch_network()
    render()

def _refresh():
    if page == 0: fetch_system()
    else:         fetch_network()
    render()

def _brightness():
    global bl_idx
    bl_idx = (bl_idx + 1) % len(BL_LEVELS)
    with _lock:
        lcd.bl_DutyCycle(BL_LEVELS[bl_idx])

btn_up.when_pressed   = lambda: _navigate(-1)
btn_down.when_pressed = lambda: _navigate(+1)
btn_key2.when_pressed = _refresh
btn_key3.when_pressed = _brightness

# ── main loop ─────────────────────────────────────────────────────────────────
running = True

def _sig(s, f):
    global running
    running = False

signal.signal(signal.SIGINT,  _sig)
signal.signal(signal.SIGTERM, _sig)

print("Fetching initial data...")
fetch_system()
fetch_network()
lcd.bl_DutyCycle(BL_LEVELS[bl_idx])
render()
print("Dashboard running  –  Ctrl-C to quit")

last_sys = last_net = time.time()

try:
    while running:
        now = time.time()
        if page == 0 and now - last_sys >= REFRESH_SECS:
            fetch_system()
            last_sys = time.time()
            render()
        elif page == 1 and now - last_net >= REFRESH_SECS:
            fetch_network()
            last_net = time.time()
            render()
        time.sleep(0.1)
finally:
    print("\nShutting down...")
    with _lock:
        lcd.bl_DutyCycle(0)
        lcd.LCD_Clear()
        lcd.module_exit()
