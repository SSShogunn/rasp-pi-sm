#!/usr/bin/env python3
"""
Pi Zero 2W Dashboard  –  sleek dark UI
Pages: 1=System  2=Network  3=Services
Keys:  Up/Down   = navigate pages (normal) / switch setting (settings)
       Left/Right = adjust value (settings)
       KEY2 = settings  KEY3 = refresh  any = wake
Run:   cd python && sudo python3 monitor.py
Deps:  sudo apt install python3-pil python3-numpy python3-gpiozero python3-spidev
"""

import time, signal, threading, subprocess, os, json
from PIL import Image, ImageDraw, ImageFont
import LCD_1in44

# ── config ────────────────────────────────────────────────────────────────────
PAGES         = 3
REFRESH       = 5          # seconds between system/network refresh
REFRESH_SVC   = 30         # seconds between services refresh (apt is slow)
SLEEP_PRESETS = [10, 20, 30, 60, 120, 300, 0]
SLEEP_LABELS  = ["10s", "20s", "30s", "1m", "2m", "5m", "Off"]
SERVICES      = [("pihole-FTL", "pihole-FTL"),
                 ("Tailscale",  "tailscaled"),
                 ("SSH",        "ssh")]
W = H         = 128

# ── palette ───────────────────────────────────────────────────────────────────
BG       = ( 10,  10,  20)
HDR_SYS  = (  0,  35,  55)
HDR_NET  = (  0,  45,  22)
HDR_SVC  = ( 35,  18,   0)
HDR_SET  = ( 25,  10,  40)
ACC_SYS  = (  0, 195, 255)
ACC_NET  = (  0, 215, 105)
ACC_SVC  = (255, 140,   0)
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
data = dict(
    cpu="--", ram_used="--", ram_cache="--", ram_free="--",
    temp="--", disk="--", uptime="...",
    wip="...", uip="...", tip="...",
    rssi="--", rx_speed="--", tx_speed="--",
    last_login="...", updates="--",
)
cpu_cores    = [0, 0, 0, 0]
svc_statuses = {label: False for label, _ in SERVICES}
_prev_net    = {"rx": 0, "tx": 0, "t": 0.0}
_cpu_snap    = None   # previous /proc/stat snapshot for delta CPU calculation

def _run(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL, timeout=8
        ).decode().strip()
    except Exception:
        return ""

# ── fetch (all /proc+/sys reads — no subprocess where avoidable) ──────────────
def _cpu_stat():
    cores = []
    try:
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("cpu") and len(line) > 3 and line[3].isdigit():
                    v = [int(x) for x in line.split()[1:8]]
                    cores.append((v[3] + v[4], sum(v)))  # (idle+iowait, total)
    except Exception:
        pass
    return cores

def fetch_system():
    global _cpu_snap
    # CPU: compare against last snapshot (no sleep needed after first call)
    snap = _cpu_stat()
    if _cpu_snap is None:
        # First call — do one quick sample so we have data immediately
        time.sleep(0.1)
        snap2 = _cpu_stat()
    else:
        snap2, snap = snap, _cpu_snap
        snap2 = _cpu_stat()
    if snap and snap2:
        pcts = []
        for (i1, t1), (i2, t2) in zip(snap, snap2):
            dt = t2 - t1
            pcts.append(max(0, min(100, int((1 - (i2-i1)/dt)*100))) if dt else 0)
        cpu_cores[:] = (pcts + [0]*4)[:4]
        data["cpu"] = str(sum(cpu_cores) // 4)
    _cpu_snap = _cpu_stat()

    # RAM — /proc/meminfo
    try:
        mi = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mi[k.strip()] = int(v.split()[0])
        total = mi["MemTotal"]
        free  = mi["MemFree"]
        cache = mi.get("Cached", 0) + mi.get("Buffers", 0) + mi.get("SReclaimable", 0)
        used  = max(0, total - free - cache)
        data["ram_used"]  = str(used  * 100 // total)
        data["ram_cache"] = str(min(100 - used*100//total, cache * 100 // total))
    except Exception:
        data["ram_used"] = data["ram_cache"] = "--"

    # Temp — /sys thermal zone (no subprocess)
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            data["temp"] = f"{int(f.read().strip()) / 1000:.1f}"
    except Exception:
        data["temp"] = "--"

    # Disk — os.statvfs (no subprocess)
    try:
        s = os.statvfs("/")
        data["disk"] = str((s.f_blocks - s.f_bfree) * 100 // s.f_blocks)
    except Exception:
        data["disk"] = "--"

    # Uptime — /proc/uptime (no subprocess)
    try:
        with open("/proc/uptime") as f:
            secs = int(float(f.read().split()[0]))
        d, r  = divmod(secs, 86400)
        h, r  = divmod(r, 3600)
        m     = r // 60
        if d:       data["uptime"] = f"{d}d {h}h {m}m"
        elif h:     data["uptime"] = f"{h}h {m}m"
        else:       data["uptime"] = f"{m}m"
    except Exception:
        data["uptime"] = "N/A"

def _net_bytes():
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if "wlan0:" in line:
                    c = line.split(); return int(c[1]), int(c[9])
    except Exception:
        pass
    return 0, 0

def _fmt_rate(bps):
    if bps < 1024:       return f"{int(bps)}B/s"
    if bps < 1024*1024:  return f"{bps/1024:.0f}K/s"
    return f"{bps/1048576:.1f}M/s"

def fetch_network():
    global _prev_net
    data["wip"] = _run("ip -4 addr show wlan0 2>/dev/null | grep inet | awk '{print $2}' | cut -d'/' -f1") or "N/A"
    data["uip"] = _run("ip -4 addr show usb0  2>/dev/null | grep inet | awk '{print $2}' | cut -d'/' -f1") or "N/A"
    data["tip"] = _run("tailscale ip -4 2>/dev/null") or "N/A"

    # RSSI — /proc/net/wireless (no subprocess)
    try:
        with open("/proc/net/wireless") as f:
            for line in f:
                if "wlan0:" in line:
                    v = int(line.split()[3].rstrip("."))
                    data["rssi"] = str(v - 256 if v > 0 else v)
                    break
    except Exception:
        data["rssi"] = "--"

    # RX/TX speed — /proc/net/dev delta
    rx, tx = _net_bytes()
    now = time.time()
    dt  = now - _prev_net["t"]
    if _prev_net["t"] > 0 and dt > 0:
        data["rx_speed"] = _fmt_rate((rx - _prev_net["rx"]) / dt)
        data["tx_speed"] = _fmt_rate((tx - _prev_net["tx"]) / dt)
    _prev_net.update({"rx": rx, "tx": tx, "t": now})

def fetch_services():
    for label, svc in SERVICES:
        svc_statuses[label] = (_run(f"systemctl is-active {svc}") == "active")
    login = _run("last -w 2>/dev/null | head -1")
    if login and not login.startswith("wtmp") and login.strip():
        parts = login.split()
        user  = parts[0] if parts else "?"
        host  = parts[2] if len(parts) > 2 else ""
        data["last_login"] = f"{user} {host}"[:20]
    else:
        data["last_login"] = "no record"
    try:
        n = int(_run("apt list --upgradable 2>/dev/null | grep -c '/'"))
        data["updates"] = f"{n} pending" if n > 0 else "up to date"
    except Exception:
        data["updates"] = "--"

# ── settings persistence ───────────────────────────────────────────────────────
_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

def _load_settings():
    global bl_pct, sleep_idx
    try:
        with open(_SETTINGS_FILE) as f:
            s = json.load(f)
        bl_pct    = max(10, min(100, int(s.get("bl_pct",   60))))
        sleep_idx = max(0,  min(len(SLEEP_PRESETS) - 1, int(s.get("sleep_idx", 0))))
    except Exception:
        pass

def _save_settings():
    try:
        with open(_SETTINGS_FILE, "w") as f:
            json.dump({"bl_pct": bl_pct, "sleep_idx": sleep_idx}, f)
    except Exception:
        pass

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
    d.text((W - _tw(d, val_str, F_VAL) - 4, y), val_str, font=F_VAL, fill=T_PRI)
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

    try:   avg = int(data["cpu"])
    except: avg = 0
    _bar_row(d, 18, "CPU", f"{data['cpu']}%", avg, C_CPU)

    cw = (W - 8 - 9) // 4
    for i, cp in enumerate(cpu_cores):
        cc = C_HOT if cp >= 90 else (C_WARN if cp >= 70 else C_CPU)
        _bar(d, 4 + i*(cw+3), 35, cw, 3, cp, cc)

    try:   ru = int(data["ram_used"])
    except: ru = 0
    try:   rc = int(data["ram_cache"])
    except: rc = 0
    d.text((4, 44), "RAM", font=F_LABEL, fill=T_SEC)
    d.text((W - _tw(d, f"{data['ram_used']}%", F_VAL) - 4, 44),
           f"{data['ram_used']}%", font=F_VAL, fill=T_PRI)
    bw = W - 10
    d.rectangle([4, 56, 4 + bw - 1, 59], fill=TRACK)
    fu = max(0, int((bw - 2) * ru / 100))
    fc = max(0, int((bw - 2) * rc / 100))
    if fu > 0: d.rectangle([5, 57, 5 + fu - 1, 58], fill=C_RAM)
    if fc > 0: d.rectangle([5 + fu, 57, 5 + fu + fc - 1, 58], fill=(70, 40, 120))

    try:   dp = int(data["disk"])
    except: dp = 0
    _bar_row(d, 63, "DISK", f"{data['disk']}%", dp, C_DISK)

    _sep(d, 80)
    try:   t = float(data["temp"])
    except: t = 0.0
    tc = C_HOT if t >= 70 else (C_WARN if t >= 55 else C_OK)
    d.text((4,  84), "TEMP", font=F_LABEL, fill=T_SEC)
    d.text((30, 84), f"{data['temp']} C", font=F_VAL, fill=tc)
    d.text((4,  97), data["uptime"], font=F_LABEL, fill=T_DIM)

    _footer(d)
    return img

# ── page 2 – network ──────────────────────────────────────────────────────────
def draw_network():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "NETWORK", ACC_NET, HDR_NET)

    y = 18
    d.text((4, y), "WIFI", font=F_LABEL, fill=T_DIM)
    if data["rssi"] != "--":
        rs = f"{data['rssi']}dBm"
        d.text((W - _tw(d, rs, F_LABEL) - 4, y), rs, font=F_LABEL, fill=C_WIFI)
    y += 11
    try:
        quality = max(0, min(100, 2 * (int(data["rssi"]) + 100)))
        bcol = C_OK if quality >= 60 else (C_WARN if quality >= 30 else C_HOT)
    except Exception:
        quality, bcol = 0, TRACK
    _bar(d, 4, y, W - 8, 3, quality, bcol)
    y += 6
    d.text((4, y), data["wip"], font=F_IP, fill=C_WIFI)
    y += 13; _sep(d, y); y += 5

    d.text((4, y), "USB", font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, data["uip"], F_IP) - 4, y), data["uip"], font=F_IP, fill=C_USB)
    y += 12; _sep(d, y); y += 5

    d.text((4, y), "TS", font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, data["tip"], F_IP) - 4, y), data["tip"], font=F_IP, fill=C_TS)
    y += 12; _sep(d, y); y += 5

    rx_s = data["rx_speed"] if data["rx_speed"] != "--" else "..."
    tx_s = data["tx_speed"] if data["tx_speed"] != "--" else "..."
    d.text((4, y), f"RX {rx_s}", font=F_FOOT, fill=C_USB)
    d.text((W - _tw(d, f"TX {tx_s}", F_FOOT) - 4, y), f"TX {tx_s}", font=F_FOOT, fill=C_WIFI)

    _footer(d)
    return img

# ── page 3 – services ─────────────────────────────────────────────────────────
def draw_services():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "SERVICES", ACC_SVC, HDR_SVC)

    y = 18
    for label, _ in SERVICES:
        active  = svc_statuses.get(label, False)
        dot_col = C_OK if active else C_HOT
        status  = "ACTIVE" if active else "STOPPED"
        d.rectangle([4, y + 2, 8, y + 6], fill=dot_col)
        d.text((12, y), label, font=F_LABEL, fill=T_PRI)
        d.text((W - _tw(d, status, F_LABEL) - 4, y), status, font=F_LABEL, fill=dot_col)
        y += 14; _sep(d, y); y += 5

    d.text((4, y), "LAST LOGIN", font=F_LABEL, fill=T_DIM)
    y += 10
    d.text((4, y), data["last_login"], font=F_LABEL, fill=T_SEC)
    y += 10; _sep(d, y); y += 4

    upd     = data["updates"]
    upd_col = C_WARN if "pending" in upd else (C_OK if "up to date" in upd else T_SEC)
    d.text((4, y), "UPDATES", font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, upd, F_LABEL) - 4, y), upd, font=F_LABEL, fill=upd_col)

    _footer(d)
    return img

# ── settings page ─────────────────────────────────────────────────────────────
def draw_settings():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=ACC_SET)
    d.text((8, 3), "SETTINGS", font=F_HDR, fill=T_PRI)
    d.text((W - _tw(d, "KEY2=exit", F_FOOT) - 4, 4), "KEY2=exit", font=F_FOOT, fill=T_DIM)

    n = len(SLEEP_PRESETS) - 1
    items = [
        ("BRIGHTNESS", f"{bl_pct}%",            bl_pct),
        ("SLEEP TIME",  SLEEP_LABELS[sleep_idx], sleep_idx * 100 // n if n else 100),
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
        y += 30; _sep(d, y); y += 6

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
bl_pct        = 60
sleeping      = False
last_activity = time.time()
settings_open = False
settings_sel  = 0
sleep_idx     = 0

_load_settings()

def render():
    if settings_open:       img = draw_settings()
    elif page == 0:         img = draw_system()
    elif page == 1:         img = draw_network()
    else:                   img = draw_services()
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

# ── background fetch thread ───────────────────────────────────────────────────
running      = True
_fetch_now   = threading.Event()   # set by KEY3 or page change to trigger immediate fetch

def _bg_fetch():
    last = [0.0, 0.0, 0.0]                         # last fetch time: sys, net, svc
    ivs  = [REFRESH, REFRESH, REFRESH_SVC]
    fns  = [fetch_system, fetch_network, fetch_services]

    while running:
        now     = time.time()
        cur     = page
        fetched = False

        for i, (fn, iv) in enumerate(zip(fns, ivs)):
            if now - last[i] >= iv:
                fn()
                last[i] = time.time()
                if i == cur:
                    fetched = True

        if fetched and not sleeping and not settings_open:
            render()

        # Wait up to 1 s, or wake immediately on _fetch_now
        _fetch_now.wait(timeout=1.0)
        if _fetch_now.is_set():
            _fetch_now.clear()
            p = page
            fns[p]()
            last[p] = time.time()
            if not sleeping and not settings_open:
                render()

# ── button callbacks ──────────────────────────────────────────────────────────
def _up():
    global page, settings_sel
    if _wake_if_sleeping(): return
    _touch()
    if settings_open:
        settings_sel = (settings_sel - 1) % 2
    else:
        page = (page - 1) % PAGES
    render()   # instant — uses cached data

def _down():
    global page, settings_sel
    if _wake_if_sleeping(): return
    _touch()
    if settings_open:
        settings_sel = (settings_sel + 1) % 2
    else:
        page = (page + 1) % PAGES
    render()

def _left():
    global bl_pct, sleep_idx
    if _wake_if_sleeping(): return
    _touch()
    if settings_open:
        if settings_sel == 0:
            bl_pct = max(10, bl_pct - 10)
            with _lock: lcd.bl_DutyCycle(bl_pct)
        else:
            sleep_idx = max(0, sleep_idx - 1)
        _save_settings()
        render()

def _right():
    global bl_pct, sleep_idx
    if _wake_if_sleeping(): return
    _touch()
    if settings_open:
        if settings_sel == 0:
            bl_pct = min(100, bl_pct + 10)
            with _lock: lcd.bl_DutyCycle(bl_pct)
        else:
            sleep_idx = min(len(SLEEP_PRESETS) - 1, sleep_idx + 1)
        _save_settings()
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
    if not settings_open:
        _fetch_now.set()   # wake background thread to fetch current page

lcd.GPIO_KEY_UP_PIN.when_activated    = _up
lcd.GPIO_KEY_DOWN_PIN.when_activated  = _down
lcd.GPIO_KEY_LEFT_PIN.when_activated  = _left
lcd.GPIO_KEY_RIGHT_PIN.when_activated = _right
lcd.GPIO_KEY2_PIN.when_activated      = _toggle_settings
lcd.GPIO_KEY3_PIN.when_activated      = _refresh

# ── signal handler ────────────────────────────────────────────────────────────
def _sig(s, f):
    global running
    running = False

signal.signal(signal.SIGINT,  _sig)
signal.signal(signal.SIGTERM, _sig)

# ── startup ───────────────────────────────────────────────────────────────────
print("Fetching initial data...")
fetch_system()
fetch_network()
fetch_services()
with _lock:
    lcd.bl_DutyCycle(bl_pct)
render()
print("Running – Ctrl-C to quit")

_fetch_thread = threading.Thread(target=_bg_fetch, daemon=True)
_fetch_thread.start()

# ── main loop (sleep timeout only — rendering driven by background thread) ────
try:
    while running:
        now        = time.time()
        sleep_secs = SLEEP_PRESETS[sleep_idx]
        if not sleeping and sleep_secs > 0 and (now - last_activity) >= sleep_secs:
            sleeping = True
            with _lock: lcd.bl_DutyCycle(0)
        time.sleep(0.1)
finally:
    print("\nShutting down...")
    with _lock:
        lcd.bl_DutyCycle(0)
        lcd.LCD_Clear()
        lcd.module_exit()
