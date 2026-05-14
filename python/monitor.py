#!/usr/bin/env python3
"""
Pi Zero 2W Dashboard  –  sleek dark UI
Pages: System · Network · Services · Pi-hole · Games · Settings
Keys:  Up/Down    = navigate settings hub / game menu / power select
       Left/Right = page navigate / adjust value inside settings app
       KEY1 = power  KEY2 = settings (jump/back)  KEY3 = refresh  PRESS = confirm / open / toggle
Run:   cd python && sudo python3 monitor.py
Deps:  sudo apt install python3-pil python3-numpy python3-gpiozero python3-spidev
"""

import time, signal, threading, subprocess, os, json, random, urllib.request, urllib.error
from PIL import Image, ImageDraw, ImageFont
import LCD_1in44

# ── config ────────────────────────────────────────────────────────────────────
PAGES         = 6
PAGE_SYS      = 0
PAGE_NET      = 1
PAGE_SVC      = 2
PAGE_PHO      = 3
PAGE_GAMES    = 4
PAGE_SET      = 5

REFRESH       = 5
REFRESH_SVC   = 30
REFRESH_PHO   = 10
PHO_HOST      = "http://localhost"
SLEEP_PRESETS = [10, 20, 30, 60, 120, 300, 0]
SLEEP_LABELS  = ["10s", "20s", "30s", "1m", "2m", "5m", "Off"]
SERVICES      = [("pihole-FTL", "pihole-FTL"),
                 ("Tailscale",  "tailscaled"),
                 ("SSH",        "ssh")]
GAME_LIST     = ["SNAKE", "PONG", "FLAPPY BIRD"]
W = H         = 128

# ── palette ───────────────────────────────────────────────────────────────────
BG       = ( 10,  10,  20)
HDR_SYS  = (  0,  35,  55)
HDR_NET  = (  0,  45,  22)
HDR_SVC  = ( 35,  18,   0)
HDR_SET  = ( 25,  10,  40)
HDR_PWR  = ( 45,   5,   5)
HDR_GAME = ( 25,  20,   0)
HDR_PHO  = ( 35,   5,  12)
ACC_SYS  = (  0, 195, 255)
ACC_NET  = (  0, 215, 105)
ACC_SVC  = (255, 140,   0)
ACC_SET  = (180,  80, 255)
ACC_PWR  = (255,  60,  60)
ACC_GAME = (255, 220,   0)
ACC_PHO  = (255,  75, 110)
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

F_HDR    = _font("DejaVuSans-Bold.ttf",  9)
F_LABEL  = _font("DejaVuSans.ttf",       8)
F_VAL    = _font("DejaVuSans-Bold.ttf",  9)
F_IP     = _font("DejaVuSans.ttf",       9)
F_FOOT   = _font("DejaVuSans.ttf",       8)
F_MED    = _font("DejaVuSans-Bold.ttf", 14)

# ── data ──────────────────────────────────────────────────────────────────────
data = dict(
    cpu="--", ram_used="--", ram_cache="--", ram_free="--",
    temp="--", disk="--", uptime="...",
    cpu_freq="--",
    wip="...", uip="...", tip="...",
    rssi="--", rx_speed="--", tx_speed="--",
    rx_total="--", tx_total="--",
    last_login="...", updates="--",
    pho_total="--", pho_blocked="--", pho_pct="--",
    pho_gravity="--", pho_clients="--", pho_cached="--",
    pho_status="?", pho_last="--",
)
cpu_cores    = [0, 0, 0, 0]
svc_statuses = {label: False for label, _ in SERVICES}
_prev_net    = {"rx": 0, "tx": 0, "t": 0.0}
_cpu_snap    = None   # previous /proc/stat snapshot for delta CPU calculation

_SET_APPS = ["Brightness", "Sleep", "WiFi", "Bluetooth"]
_SET_COLS = [ACC_SET, (55, 100, 220), C_OK, (0, 185, 230)]

_pho_sid   = None
_pho_sid_t = 0.0

def _get_rfkill(kind):
    try:
        for entry in sorted(os.listdir("/sys/class/rfkill")):
            with open(f"/sys/class/rfkill/{entry}/type") as f:
                if f.read().strip() == kind:
                    with open(f"/sys/class/rfkill/{entry}/soft") as f2:
                        return f2.read().strip() == "0"  # "0" = unblocked = ON
    except Exception:
        pass
    return True

def _run(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL, timeout=8
        ).decode().strip()
    except Exception:
        return ""

def _pho_auth():
    global _pho_sid, _pho_sid_t
    try:
        body = json.dumps({"password": pho_password}).encode()
        req  = urllib.request.Request(
            f"{PHO_HOST}/api/auth", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read())
        sid = j.get("session", {}).get("sid")
        if sid:
            _pho_sid = sid; _pho_sid_t = time.time(); return True
    except Exception:
        pass
    _pho_sid = None; return False

def _pho_ensure_auth():
    if not pho_password:
        return True
    if not _pho_sid or (time.time() - _pho_sid_t) > 1500:
        return _pho_auth()
    return True

def _pho_get(path):
    sep = "&" if "?" in path else "?"
    sid_param = f"{sep}sid={_pho_sid}" if _pho_sid else ""
    req = urllib.request.Request(f"{PHO_HOST}{path}{sid_param}")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())

def _fmt_gravity(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n//1000}K"
    return str(n)

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

    # CPU frequency — /sys/cpufreq
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as f:
            khz = int(f.read().strip())
        data["cpu_freq"] = f"{khz // 1000}MHz"
    except Exception:
        data["cpu_freq"] = "--"


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

def _fmt_bytes(b):
    if b < 1024:        return f"{b}B"
    if b < 1024**2:     return f"{b/1024:.0f}K"
    if b < 1024**3:     return f"{b/1048576:.1f}M"
    return f"{b/1073741824:.2f}G"

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

    # RX/TX speed + totals — /proc/net/dev
    rx, tx = _net_bytes()
    now = time.time()
    dt  = now - _prev_net["t"]
    if _prev_net["t"] > 0 and dt > 0:
        data["rx_speed"] = _fmt_rate((rx - _prev_net["rx"]) / dt)
        data["tx_speed"] = _fmt_rate((tx - _prev_net["tx"]) / dt)
    data["rx_total"] = _fmt_bytes(rx)
    data["tx_total"] = _fmt_bytes(tx)
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

def fetch_pihole():
    if not _pho_ensure_auth():
        data["pho_status"] = "auth err"; return
    try:
        s = _pho_get("/api/stats/summary")
        q = s.get("queries", {})
        g = s.get("gravity", {})
        c = s.get("clients", {})
        data["pho_total"]   = f"{q.get('total',   0):,}"
        data["pho_blocked"] = f"{q.get('blocked', 0):,}"
        data["pho_pct"]     = f"{q.get('percent_blocked', 0.0):.1f}"
        data["pho_cached"]  = f"{q.get('cached',  0):,}"
        data["pho_clients"] = str(c.get("active", "--"))
        data["pho_gravity"] = _fmt_gravity(g.get("domains_being_blocked", 0))
    except Exception:
        data["pho_status"] = "error"; return
    try:
        b = _pho_get("/api/dns/blocking")
        data["pho_status"] = b.get("blocking", "?")
    except Exception:
        data["pho_status"] = "?"
    try:
        r = _pho_get("/api/stats/recent_blocked?count=1")
        doms = r.get("blocked", [])
        data["pho_last"] = doms[0] if doms else "--"
    except Exception:
        data["pho_last"] = "--"

# ── settings persistence ───────────────────────────────────────────────────────
_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

def _load_settings():
    global bl_pct, sleep_idx, pho_password
    try:
        with open(_SETTINGS_FILE) as f:
            s = json.load(f)
        bl_pct       = max(10, min(100, int(s.get("bl_pct",   60))))
        sleep_idx    = max(0,  min(len(SLEEP_PRESETS) - 1, int(s.get("sleep_idx", 0))))
        pho_password = s.get("pho_password", "")
    except Exception:
        pass

def _save_settings():
    try:
        with open(_SETTINGS_FILE, "w") as f:
            json.dump({"bl_pct": bl_pct, "sleep_idx": sleep_idx,
                       "pho_password": pho_password}, f)
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
    d.text((4, 115), f"up {data['uptime']}", font=F_FOOT, fill=T_DIM)
    t = time.strftime("%H:%M")
    d.text((W - _tw(d, t, F_FOOT) - 4, 115), t, font=F_FOOT, fill=T_DIM)

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

    try:   t = float(data["temp"])
    except: t = 0.0
    tc = C_HOT if t >= 70 else (C_WARN if t >= 55 else C_OK)

    # TEMP (left) + CPU freq (right)
    d.text((4,  82), "TEMP", font=F_LABEL, fill=T_SEC)
    d.text((30, 82), f"{data['temp']}C", font=F_VAL, fill=tc)
    d.text((W - _tw(d, data["cpu_freq"], F_LABEL) - 4, 82),
           data["cpu_freq"], font=F_LABEL, fill=T_DIM)

    # total data in / out
    rx_s = f"IN  {data['rx_total']}"
    tx_s = f"OUT {data['tx_total']}"
    d.text((4,  95), rx_s, font=F_FOOT, fill=C_USB)
    d.text((W - _tw(d, tx_s, F_FOOT) - 4, 95), tx_s, font=F_FOOT, fill=C_WIFI)

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

# ── page 4 – pi-hole ─────────────────────────────────────────────────────────
def draw_pihole():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    status = data["pho_status"]
    if status == "enabled":   acc = C_OK
    elif status == "disabled": acc = C_HOT
    else:                      acc = T_DIM
    _header(d, "PI-HOLE", acc, HDR_PHO)

    # Blocked count + percent
    pct_s = f"{data['pho_pct']}%"
    d.text((4,  18), "BLOCKED", font=F_LABEL, fill=T_SEC)
    d.text((54, 18), data["pho_blocked"], font=F_VAL,   fill=C_HOT)
    d.text((W - _tw(d, pct_s, F_VAL) - 4, 18), pct_s,  font=F_VAL, fill=C_WARN)

    # Total queries
    d.text((4,  30), "QUERIES", font=F_LABEL, fill=T_SEC)
    d.text((54, 30), data["pho_total"],   font=F_VAL, fill=T_PRI)

    # Cached
    d.text((4,  42), "CACHED",  font=F_LABEL, fill=T_SEC)
    d.text((54, 42), data["pho_cached"],  font=F_VAL, fill=C_CPU)

    # Clients + gravity on one row
    cl_s = f"CLNTS {data['pho_clients']}"
    gv_s = f"GRV {data['pho_gravity']}"
    d.text((4,  54), cl_s, font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, gv_s, F_LABEL) - 4, 54), gv_s, font=F_LABEL, fill=T_DIM)

    _sep(d, 66)

    # Last blocked domain (auto-truncate to fit)
    d.text((4, 69), "LAST BLOCK", font=F_LABEL, fill=T_SEC)
    last = data["pho_last"]
    while last and _tw(d, last + ("…" if len(last) < len(data["pho_last"]) else ""), F_LABEL) > W - 8:
        last = last[:-1]
    if len(last) < len(data["pho_last"]): last += "…"
    d.text((4, 79), last, font=F_LABEL, fill=ACC_PHO)

    _sep(d, 92)
    hint = "PRESS:toggle  K3:refresh"
    d.text((4, 95), hint, font=F_FOOT, fill=T_DIM)

    _footer(d)
    return img

# ── page 5 – games hub ───────────────────────────────────────────────────────
def draw_games():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_GAME)
    d.rectangle([0, 0, 3, 15], fill=ACC_GAME)
    d.text((8, 3), "GAMES", font=F_HDR, fill=T_PRI)
    pg = f"{page + 1}/{PAGES}"
    d.text((W - _tw(d, pg, F_FOOT) - 4, 4), pg, font=F_FOOT, fill=T_DIM)

    y = 24
    for i, name in enumerate(GAME_LIST):
        sel = (game_sel == i)
        if sel:
            d.rectangle([0, y - 3, W - 1, y + 17], fill=(40, 35, 0))
            d.rectangle([0, y - 3, 3,     y + 17], fill=ACC_GAME)
        d.text((10, y + 3), name, font=F_VAL,
               fill=ACC_GAME if sel else T_DIM)
        y += 26

    _sep(d, 100)
    d.text((4, 103), "UP/DN: pick   PRESS: play", font=F_FOOT, fill=T_DIM)
    d.text((4, 113), "L/R  : exit",               font=F_FOOT, fill=T_DIM)
    return img

# ── page 5 – settings hub + sub-screens ──────────────────────────────────────
def draw_set_hub():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "SETTINGS", ACC_SET, HDR_SET)

    vals = [f"{bl_pct}%", SLEEP_LABELS[sleep_idx],
            "ON" if wifi_on else "OFF", "ON" if bt_on else "OFF"]
    y = 18
    for i, (name, col, val) in enumerate(zip(_SET_APPS, _SET_COLS, vals)):
        sel = (set_sel == i)
        if sel:
            d.rectangle([0, y, W-1, y+22],
                        fill=(col[0]//5, col[1]//5, col[2]//5))
            d.rectangle([0, y, 3, y+22], fill=col)
        d.rectangle([6, y+6, 16, y+16], fill=col if sel else T_DIM)
        d.text((20, y+6), name, font=F_LABEL, fill=T_PRI if sel else T_SEC)
        d.text((W - _tw(d, val, F_VAL) - 4, y+6), val,
               font=F_VAL, fill=T_PRI if sel else T_DIM)
        y += 23

    _sep(d, 112)
    d.text((4, 115), "PRESS:open  KEY2:exit", font=F_FOOT, fill=T_DIM)
    return img

def draw_set_bright():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W-1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15],   fill=ACC_SET)
    d.text((8, 3), "BRIGHTNESS", font=F_HDR, fill=T_PRI)

    val = f"{bl_pct}%"
    d.text(((W - _tw(d, val, F_MED)) // 2, 33), val, font=F_MED, fill=ACC_SET)
    _bar(d, 14, 57, W-28, 7, bl_pct, ACC_SET)

    _sep(d, 74)
    d.text((4,  77), "L / R : adjust", font=F_FOOT, fill=T_DIM)
    d.text((4,  89), "KEY2  : back",   font=F_FOOT, fill=T_DIM)
    _footer(d)
    return img

def draw_set_sleep():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    SL_COL = (55, 100, 220)
    d.rectangle([0, 0, W-1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15],   fill=SL_COL)
    d.text((8, 3), "SLEEP TIMER", font=F_HDR, fill=T_PRI)

    val = SLEEP_LABELS[sleep_idx]
    d.text(((W - _tw(d, val, F_MED)) // 2, 33), val, font=F_MED, fill=SL_COL)

    cols = 4; sw = (W - 8) // cols
    for j, lbl in enumerate(SLEEP_LABELS):
        gx = 4 + (j % cols) * sw
        gy = 60 + (j // cols) * 14
        sel = (j == sleep_idx)
        d.rectangle([gx, gy, gx+sw-3, gy+11],
                    fill=(25, 40, 80) if sel else BG,
                    outline=SL_COL if sel else T_DIM)
        d.text((gx + (sw-3 - _tw(d, lbl, F_FOOT)) // 2, gy+1),
               lbl, font=F_FOOT, fill=T_PRI if sel else T_DIM)

    _sep(d, 102)
    d.text((4, 105), "L/R: change  KEY2: back", font=F_FOOT, fill=T_DIM)
    return img

def draw_set_wifi():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W-1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15],   fill=C_OK)
    d.text((8, 3), "WiFi", font=F_HDR, fill=T_PRI)

    dot_col = C_OK if wifi_on else C_HOT
    status  = "ON" if wifi_on else "OFF"
    d.ellipse([14, 26, 28, 40], fill=dot_col)
    d.text((35, 25), status, font=F_MED, fill=dot_col)

    y = 50
    if wifi_on:
        d.text((4, y), data["wip"], font=F_IP, fill=C_WIFI); y += 13
        if data["rssi"] != "--":
            d.text((4, y), f"Signal: {data['rssi']}dBm", font=F_LABEL, fill=T_SEC)

    _sep(d, 88)
    d.text((4,  91), "PRESS : toggle", font=F_FOOT, fill=T_PRI)
    d.text((4, 103), "KEY2  : back",   font=F_FOOT, fill=T_DIM)
    _footer(d)
    return img

def draw_set_bt():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    BT_COL = (0, 185, 230)
    d.rectangle([0, 0, W-1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15],   fill=BT_COL)
    d.text((8, 3), "Bluetooth", font=F_HDR, fill=T_PRI)

    dot_col = BT_COL if bt_on else C_HOT
    status  = "ON" if bt_on else "OFF"
    d.ellipse([14, 26, 28, 40], fill=dot_col)
    d.text((35, 25), status, font=F_MED, fill=dot_col)

    _sep(d, 88)
    d.text((4,  91), "PRESS : toggle", font=F_FOOT, fill=T_PRI)
    d.text((4, 103), "KEY2  : back",   font=F_FOOT, fill=T_DIM)
    _footer(d)
    return img

def draw_settings_page():
    if   set_app == 0: return draw_set_bright()
    elif set_app == 1: return draw_set_sleep()
    elif set_app == 2: return draw_set_wifi()
    elif set_app == 3: return draw_set_bt()
    else:              return draw_set_hub()

# ── power page ────────────────────────────────────────────────────────────────
def draw_power():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_PWR)
    d.rectangle([0, 0, 3, 15], fill=ACC_PWR)
    d.text((8, 3), "POWER", font=F_HDR, fill=T_PRI)
    d.text((W - _tw(d, "KEY1=back", F_FOOT) - 4, 4), "KEY1=back", font=F_FOOT, fill=T_DIM)

    labels = [("REBOOT",    (255, 140, 40)),
              ("POWER OFF", (255,  60, 60))]
    y0, row_h = 20, 32
    for i, (label, col) in enumerate(labels):
        y   = y0 + i * row_h
        sel = (power_sel == i)
        if sel:
            d.rectangle([0, y, W - 1, y + row_h - 2],
                        fill=(col[0] // 6, col[1] // 6, col[2] // 6))
            d.rectangle([0, y, 3, y + row_h - 2], fill=col)
        cx = (W - _tw(d, label, F_VAL)) // 2
        d.text((cx, y + (row_h - 12) // 2), label, font=F_VAL,
               fill=col if sel else T_DIM)

    _sep(d, 88)
    d.text((4,  91), "UP/DN: select  K1/K2: back", font=F_FOOT, fill=T_DIM)
    d.text((4, 102), "PRESS : confirm",             font=F_FOOT, fill=ACC_PWR)
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
set_sel       = 0      # selected row in settings hub
set_app       = None   # None=hub, 0=Brightness, 1=Sleep, 2=WiFi, 3=BT
wifi_on       = _get_rfkill("wlan")
bt_on         = _get_rfkill("bluetooth")
pho_password  = ""     # loaded from settings.json
sleep_idx     = 0
power_open    = False
power_sel     = 0   # 0=Reboot  1=Power Off
game_sel      = 0   # selected game in hub menu
game_active   = False

_load_settings()

def render():
    if power_open:              img = draw_power()
    elif page == PAGE_SYS:      img = draw_system()
    elif page == PAGE_NET:      img = draw_network()
    elif page == PAGE_SVC:      img = draw_services()
    elif page == PAGE_PHO:      img = draw_pihole()
    elif page == PAGE_GAMES:    img = draw_games()
    elif page == PAGE_SET:      img = draw_settings_page()
    else:                       img = draw_system()
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
    last = [0.0, 0.0, 0.0, 0.0]
    ivs  = [REFRESH, REFRESH, REFRESH_SVC, REFRESH_PHO]
    fns  = [fetch_system, fetch_network, fetch_services, fetch_pihole]

    while running:
        now = time.time()
        cur = page

        if not game_active:
            fetched = False
            for i, (fn, iv) in enumerate(zip(fns, ivs)):
                if now - last[i] >= iv:
                    fn(); last[i] = time.time()
                    if i == cur: fetched = True
            if fetched and not sleeping and not power_open:
                render()

        _fetch_now.wait(timeout=1.0)
        if _fetch_now.is_set():
            _fetch_now.clear()
            if not game_active:
                p = page
                if p < len(fns):
                    fns[p](); last[p] = time.time()
                if not sleeping and not power_open:
                    render()

# ── button callbacks ──────────────────────────────────────────────────────────
def _up():
    global set_sel, power_sel, game_sel
    if _wake_if_sleeping(): return
    _touch()
    if power_open:
        power_sel = (power_sel - 1) % 2; render()
    elif page == PAGE_GAMES:
        game_sel = (game_sel - 1) % len(GAME_LIST); render()
    elif page == PAGE_SET and set_app is None:
        set_sel = (set_sel - 1) % len(_SET_APPS); render()

def _down():
    global set_sel, power_sel, game_sel
    if _wake_if_sleeping(): return
    _touch()
    if power_open:
        power_sel = (power_sel + 1) % 2; render()
    elif page == PAGE_GAMES:
        game_sel = (game_sel + 1) % len(GAME_LIST); render()
    elif page == PAGE_SET and set_app is None:
        set_sel = (set_sel + 1) % len(_SET_APPS); render()

def _left():
    global bl_pct, sleep_idx, power_open, page
    if _wake_if_sleeping(): return
    _touch()
    if power_open:
        power_open = False; render(); return
    if page == PAGE_SET and set_app is not None:
        if set_app == 0:
            bl_pct = max(10, bl_pct - 10)
            with _lock: lcd.bl_DutyCycle(bl_pct)
            _save_settings()
        elif set_app == 1:
            sleep_idx = max(0, sleep_idx - 1)
            _save_settings()
        render(); return
    page = (page - 1) % PAGES
    render()

def _right():
    global bl_pct, sleep_idx, power_open, page
    if _wake_if_sleeping(): return
    _touch()
    if power_open:
        power_open = False; render(); return
    if page == PAGE_SET and set_app is not None:
        if set_app == 0:
            bl_pct = min(100, bl_pct + 10)
            with _lock: lcd.bl_DutyCycle(bl_pct)
            _save_settings()
        elif set_app == 1:
            sleep_idx = min(len(SLEEP_PRESETS) - 1, sleep_idx + 1)
            _save_settings()
        render(); return
    page = (page + 1) % PAGES
    render()

def _key2():
    global set_app, page, power_open
    if _wake_if_sleeping(): return
    _touch()
    if power_open:
        power_open = False; render(); return
    if set_app is not None:
        set_app = None; render(); return
    if page == PAGE_SET:
        page = PAGE_SYS; render(); return
    page = PAGE_SET; render()

def _refresh():
    global power_open
    if _wake_if_sleeping(): return
    _touch()
    if power_open:
        power_open = False; render(); return
    _fetch_now.set()

def _toggle_power():
    global power_open, power_sel
    if _wake_if_sleeping(): return
    _touch()
    if game_active: return
    power_open = not power_open
    power_sel  = 0
    render()

def _toggle_pihole():
    new_on = (data["pho_status"] != "enabled")
    try:
        body = json.dumps({"blocking": new_on}).encode()
        sid_param = f"?sid={_pho_sid}" if _pho_sid else ""
        req = urllib.request.Request(
            f"{PHO_HOST}/api/dns/blocking{sid_param}",
            data=body, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5).close()
        data["pho_status"] = "enabled" if new_on else "disabled"
    except Exception:
        pass
    fetch_pihole(); render()

def _press():
    global game_active, wifi_on, bt_on, set_app
    if _wake_if_sleeping(): return
    _touch()
    if game_active: return
    if not power_open and page == PAGE_PHO:
        threading.Thread(target=_toggle_pihole, daemon=True).start(); return
    if not power_open and page == PAGE_GAMES:
        _launch_game(game_sel); return
    if not power_open and page == PAGE_SET:
        if set_app is None:
            set_app = set_sel; render(); return
        elif set_app == 2:
            wifi_on = not wifi_on
            subprocess.run(["rfkill", "unblock" if wifi_on else "block", "wlan"], check=False)
            render(); return
        elif set_app == 3:
            bt_on = not bt_on
            subprocess.run(["rfkill", "unblock" if bt_on else "block", "bluetooth"], check=False)
            render(); return
    if not power_open:
        return
    msg = "REBOOTING..." if power_sel == 0 else "SHUTTING DOWN..."
    img = Image.new("RGB", (W, H), (25, 0, 0))
    d   = ImageDraw.Draw(img)
    d.text(((W - _tw(d, msg, F_VAL)) // 2, H // 2 - 5), msg, font=F_VAL, fill=ACC_PWR)
    with _lock:
        lcd.LCD_ShowImage(img)
    time.sleep(0.8)
    subprocess.run(["reboot"] if power_sel == 0 else ["poweroff"])

def _launch_game(idx):
    global game_active
    game_active = True
    fns = [_game_snake, _game_pong, _game_flappy]
    threading.Thread(target=fns[idx], daemon=True).start()

# ── games ────────────────────────────────────────────────────────────────────
_SN_CELL = 5
_SN_COLS = W // _SN_CELL   # 25
_SN_ROWS = H // _SN_CELL   # 25

def _sn_food(body):
    while True:
        c, r = random.randint(0, _SN_COLS-1), random.randint(0, _SN_ROWS-1)
        if (c, r) not in body:
            return (c, r)

def _game_snake():
    global game_active
    BG_G = (5, 18, 5); SNKC = (0, 190, 80); HEAD = (0, 255, 110); FOOD = (255, 50, 50)
    snake  = [(12, 12), (11, 12), (10, 12)]
    direc  = (1, 0);  pend = (1, 0)
    food   = _sn_food(snake)
    score  = 0;  step = 0.18
    last_step = last_inp = time.time()

    while running:
        now = time.time()
        if now - last_inp >= 0.08:
            if   lcd.GPIO_KEY_UP_PIN.value    and direc != (0,  1): pend = (0, -1); last_inp = now
            elif lcd.GPIO_KEY_DOWN_PIN.value  and direc != (0, -1): pend = (0,  1); last_inp = now
            elif lcd.GPIO_KEY_LEFT_PIN.value  and direc != (1,  0): pend = (-1, 0); last_inp = now
            elif lcd.GPIO_KEY_RIGHT_PIN.value and direc != (-1, 0): pend = (1,  0); last_inp = now
        if lcd.GPIO_KEY2_PIN.value: break

        if now - last_step >= step:
            direc = pend
            hx = snake[0][0] + direc[0]
            hy = snake[0][1] + direc[1]
            if hx < 0 or hx >= _SN_COLS or hy < 0 or hy >= _SN_ROWS or (hx, hy) in snake:
                break
            snake.insert(0, (hx, hy))
            if (hx, hy) == food:
                score += 1; food = _sn_food(snake); step = max(0.07, step - 0.008)
            else:
                snake.pop()
            last_step = now

            img = Image.new("RGB", (W, H), BG_G); d = ImageDraw.Draw(img)
            fx, fy = food
            d.ellipse([fx*_SN_CELL+1, fy*_SN_CELL+1,
                       fx*_SN_CELL+_SN_CELL-2, fy*_SN_CELL+_SN_CELL-2], fill=FOOD)
            for i, (cx, cy) in enumerate(snake):
                d.rectangle([cx*_SN_CELL, cy*_SN_CELL,
                             cx*_SN_CELL+_SN_CELL-2, cy*_SN_CELL+_SN_CELL-2],
                            fill=HEAD if i == 0 else SNKC)
            d.text((2, 2), str(score), font=F_VAL, fill=T_PRI)
            with _lock: lcd.LCD_ShowImage(img)
        time.sleep(0.02)

    img = Image.new("RGB", (W, H), (15, 0, 0)); d = ImageDraw.Draw(img)
    d.text(((W-_tw(d,"GAME OVER",F_VAL))//2, 50), "GAME OVER", font=F_VAL, fill=C_HOT)
    d.text(((W-_tw(d,f"Score: {score}",F_LABEL))//2, 66), f"Score: {score}", font=F_LABEL, fill=T_PRI)
    d.text(((W-_tw(d,"KEY2 to exit",F_FOOT))//2, 86), "KEY2 to exit", font=F_FOOT, fill=T_DIM)
    with _lock: lcd.LCD_ShowImage(img)
    while running and not lcd.GPIO_KEY2_PIN.value: time.sleep(0.1)
    time.sleep(0.3)
    game_active = False; render()

def _game_pong():
    global game_active
    PAD_W=4; PAD_H=22; PL_SPD=3; AI_SPD=2; BALL=4
    PL_X=5; AI_X=W-5-PAD_W
    ball=[W//2, H//2]; bvx=2; bvy=2
    pl_y=H//2-PAD_H//2; ai_y=H//2-PAD_H//2
    p_sc=0; a_sc=0
    BG_P=(5,5,20); PLCOL=(0,200,255); AICOL=(255,80,50); BCOL=(255,220,0)
    FRAME=1.0/30

    while running:
        t0 = time.time()
        if lcd.GPIO_KEY_UP_PIN.value:   pl_y = max(0, pl_y - PL_SPD)
        if lcd.GPIO_KEY_DOWN_PIN.value: pl_y = min(H-PAD_H, pl_y + PL_SPD)
        if lcd.GPIO_KEY2_PIN.value: break

        ball[0]+=bvx; ball[1]+=bvy
        if ball[1]<=0:          ball[1]=0;       bvy=abs(bvy)
        if ball[1]>=H-BALL:     ball[1]=H-BALL;  bvy=-abs(bvy)

        if bvx<0 and ball[0]<=PL_X+PAD_W and pl_y<=ball[1]+BALL and ball[1]<=pl_y+PAD_H:
            bvx=abs(bvx); rel=(ball[1]+BALL//2-pl_y)/PAD_H; bvy=int((rel-0.5)*5) or 1
        if bvx>0 and ball[0]+BALL>=AI_X and ball[0]<=AI_X+PAD_W and ai_y<=ball[1]+BALL and ball[1]<=ai_y+PAD_H:
            bvx=-abs(bvx); rel=(ball[1]+BALL//2-ai_y)/PAD_H; bvy=int((rel-0.5)*5) or -1

        if ball[0]<0:  a_sc+=1; ball=[W//2,H//2]; bvx=-2; bvy=random.choice([-2,2])
        if ball[0]>W:  p_sc+=1; ball=[W//2,H//2]; bvx=2;  bvy=random.choice([-2,2])

        ac=ai_y+PAD_H//2; bc=ball[1]+BALL//2
        if ac<bc: ai_y=min(H-PAD_H, ai_y+AI_SPD)
        elif ac>bc: ai_y=max(0, ai_y-AI_SPD)

        img=Image.new("RGB",(W,H),BG_P); d=ImageDraw.Draw(img)
        for y in range(0,H,8): d.rectangle([W//2-1,y,W//2,y+4],fill=(25,25,50))
        d.rectangle([PL_X,pl_y,PL_X+PAD_W-1,pl_y+PAD_H-1],fill=PLCOL)
        d.rectangle([AI_X,ai_y,AI_X+PAD_W-1,ai_y+PAD_H-1],fill=AICOL)
        d.rectangle([ball[0],ball[1],ball[0]+BALL-1,ball[1]+BALL-1],fill=BCOL)
        ps=str(p_sc); as_=str(a_sc)
        d.text((W//4-_tw(d,ps,F_VAL)//2,2),ps,font=F_VAL,fill=PLCOL)
        d.text((3*W//4-_tw(d,as_,F_VAL)//2,2),as_,font=F_VAL,fill=AICOL)
        with _lock: lcd.LCD_ShowImage(img)
        time.sleep(max(0, FRAME-(time.time()-t0)))

    game_active=False; render()

def _game_flappy():
    global game_active
    GRAVITY=0.35; FLAP=-3.5; PIPE_W=14; GAP=40; SCROLL=2; BIRD_X=28; BIRD_S=6
    bird_y=float(H//2); bird_v=0.0; pipes=[]; score=0; ticks=0
    prev_up=prev_pr=prev_k3=False
    BG_F=(5,8,28); PCOL=(30,160,50); BCOL=(255,220,0); GCOL=(30,20,8)
    FRAME=1.0/30

    while running:
        t0=time.time(); ticks+=1
        if ticks%55==0 or not pipes:
            pipes.append([W+PIPE_W, random.randint(15, H-GAP-15)])

        up_now=lcd.GPIO_KEY_UP_PIN.value
        pr_now=lcd.GPIO_KEY_PRESS_PIN.value
        k3_now=lcd.GPIO_KEY3_PIN.value
        flap=(up_now and not prev_up)or(pr_now and not prev_pr)or(k3_now and not prev_k3)
        prev_up=up_now; prev_pr=pr_now; prev_k3=k3_now
        if lcd.GPIO_KEY2_PIN.value: break

        if flap: bird_v=FLAP
        bird_v+=GRAVITY; bird_y+=bird_v
        for p in pipes: p[0]-=SCROLL
        for p in pipes:
            if p[0]+PIPE_W==BIRD_X: score+=1
        pipes=[p for p in pipes if p[0]>-PIPE_W]

        bx1=BIRD_X-BIRD_S//2; bx2=BIRD_X+BIRD_S//2
        by1=int(bird_y-BIRD_S//2); by2=int(bird_y+BIRD_S//2)
        dead=bird_y<BIRD_S//2 or bird_y>H-BIRD_S//2
        for px,gy in pipes:
            if bx2>px and bx1<px+PIPE_W and (by1<gy or by2>gy+GAP): dead=True

        img=Image.new("RGB",(W,H),BG_F); d=ImageDraw.Draw(img)
        d.rectangle([0,H-5,W-1,H-1],fill=GCOL)
        for px,gy in pipes:
            d.rectangle([px,0,px+PIPE_W-1,gy-1],fill=PCOL)
            d.rectangle([px,gy+GAP,px+PIPE_W-1,H-6],fill=PCOL)
        d.rectangle([bx1,by1,bx2-1,by2-1],fill=BCOL)
        sc=str(score); d.text(((W-_tw(d,sc,F_VAL))//2,3),sc,font=F_VAL,fill=T_PRI)
        if dead:
            d.text(((W-_tw(d,"DEAD!",F_VAL))//2,H//2-8),"DEAD!",font=F_VAL,fill=C_HOT)
            with _lock: lcd.LCD_ShowImage(img)
            time.sleep(1.5); break
        with _lock: lcd.LCD_ShowImage(img)
        time.sleep(max(0, FRAME-(time.time()-t0)))

    game_active=False; render()

# ── button polling (replaces when_activated — works on all HAT GPIO pins) ─────
_BTN_HANDLERS = [
    (lcd.GPIO_KEY_UP_PIN,    _up),
    (lcd.GPIO_KEY_DOWN_PIN,  _down),
    (lcd.GPIO_KEY_LEFT_PIN,  _left),
    (lcd.GPIO_KEY_RIGHT_PIN, _right),
    (lcd.GPIO_KEY_PRESS_PIN, _press),
    (lcd.GPIO_KEY1_PIN,      _toggle_power),
    (lcd.GPIO_KEY2_PIN,      _key2),
    (lcd.GPIO_KEY3_PIN,      _refresh),
]
_DEBOUNCE = 0.15  # seconds between repeated fires for the same button

def _poll_buttons():
    prev      = [pin.value for pin, _ in _BTN_HANDLERS]
    last_fire = [0.0]       * len(_BTN_HANDLERS)
    while running:
        time.sleep(0.05)
        if game_active:
            for i, (pin, _) in enumerate(_BTN_HANDLERS):
                prev[i] = pin.value   # keep prev fresh so no burst on exit
            continue
        now = time.time()
        for i, (pin, handler) in enumerate(_BTN_HANDLERS):
            curr = pin.value
            if curr and not prev[i] and (now - last_fire[i]) >= _DEBOUNCE:
                last_fire[i] = now
                threading.Thread(target=handler, daemon=True).start()
            prev[i] = curr

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
fetch_pihole()
with _lock:
    lcd.bl_DutyCycle(bl_pct)
render()
print("Running – Ctrl-C to quit")

_fetch_thread  = threading.Thread(target=_bg_fetch,      daemon=True)
_button_thread = threading.Thread(target=_poll_buttons,  daemon=True)
_fetch_thread.start()
_button_thread.start()

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
