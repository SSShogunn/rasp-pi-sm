import time
from PIL import Image, ImageDraw
import state
from constants import *

_last_img = None  # cached last rendered frame for slide transitions

# ── primitives ────────────────────────────────────────────────────────────────
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

def _spark(d, x, y, w, h, hist, color, vmax=None):
    """Draw a filled sparkline of `hist` (iterable of numbers) in a w×h box."""
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=TRACK)
    vals = list(hist)
    if not vals:
        return
    top = vmax if vmax is not None else max(vals)
    if top <= 0:
        return
    n = len(vals)
    # right-align: newest sample at the right edge
    for i, v in enumerate(vals):
        bh = max(0, min(h - 1, int((v / top) * (h - 1))))
        px = x + w - n + i
        if px < x:
            continue
        d.line([(px, y + h - 1), (px, y + h - 1 - bh)], fill=color)

def _signal_bars(d, x, y, quality):
    """4 ascending bars representing wifi quality 0..100."""
    heights = [3, 5, 7, 9]
    filled  = 0 if quality <= 0 else min(4, quality // 25 + 1)
    bcol    = C_OK if quality >= 60 else (C_WARN if quality >= 30 else C_HOT)
    for i, bh in enumerate(heights):
        bx = x + i * 4
        on = i < filled
        d.rectangle([bx, y + 9 - bh, bx + 2, y + 9],
                    fill=bcol if on else TRACK)

def _header(d, title, accent, hdr_bg):
    d.rectangle([0, 0, W - 1, 15], fill=hdr_bg)
    d.rectangle([0, 0, 3, 15], fill=accent)
    d.text((8, 3), title, font=F_HDR, fill=T_PRI)
    pg = f"{state.page + 1}/{PAGES}"
    d.text((W - _tw(d, pg, F_FOOT) - 4, 4), pg, font=F_FOOT, fill=T_DIM)

def _footer(d):
    _sep(d, 112)
    d.text((4, 115), f"up {state.data['uptime']}", font=F_FOOT, fill=T_DIM)
    t = time.strftime("%H:%M")
    d.text((W - _tw(d, t, F_FOOT) - 4, 115), t, font=F_FOOT, fill=T_DIM)

def _temp_color(t_str, hot=35, warn=28):
    try:
        t = float(t_str)
        return C_HOT if t >= hot else (C_WARN if t >= warn else C_OK)
    except Exception:
        return T_DIM

# ── home (system overview) ──────────────────────────────────────────────────
def draw_home():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    now    = time.localtime()
    clk    = time.strftime("%H:%M", now)
    date_s = time.strftime("%a %d %b", now)

    # ── top bar: hostname · page ────────────────────────────────────────────────
    d.text((4, 2), state.data.get("host", "pi"), font=F_FOOT, fill=ACC_NET)
    pg = f"{state.page + 1}/{PAGES}"
    d.text((W - _tw(d, pg, F_FOOT) - 4, 2), pg, font=F_FOOT, fill=T_DIM)

    # ── big clock + date ────────────────────────────────────────────────────────
    d.text(((W - _tw(d, clk, F_BIG)) // 2, 12), clk, font=F_BIG, fill=T_PRI)
    d.text(((W - _tw(d, date_s, F_LABEL)) // 2, 36), date_s, font=F_LABEL, fill=T_DIM)
    _sep(d, 50)

    # ── CPU + RAM bars ──────────────────────────────────────────────────────────
    def _val_int(key):
        try:    return int(state.data[key])
        except (ValueError, TypeError): return 0

    d.text((4, 53), "CPU", font=F_FOOT, fill=T_SEC)
    d.text((W - _tw(d, f"{state.data['cpu']}%", F_FOOT) - 4, 53),
           f"{state.data['cpu']}%", font=F_FOOT, fill=C_CPU)
    _bar(d, 4, 62, W - 8, 3, _val_int("cpu"), C_CPU)

    d.text((4, 68), "RAM", font=F_FOOT, fill=T_SEC)
    d.text((W - _tw(d, f"{state.data['ram_used']}%", F_FOOT) - 4, 68),
           f"{state.data['ram_used']}%", font=F_FOOT, fill=C_RAM)
    _bar(d, 4, 77, W - 8, 3, _val_int("ram_used"), C_RAM)
    _sep(d, 83)

    # ── temp + disk ─────────────────────────────────────────────────────────────
    tc = _temp_color(state.data["temp"], hot=70, warn=55)
    d.text((4, 86), "TEMP", font=F_FOOT, fill=T_DIM)
    d.text((32, 86), f"{state.data['temp']}°C", font=F_FOOT, fill=tc)
    disk_s = f"DISK {state.data['disk']}%"
    d.text((W - _tw(d, disk_s, F_FOOT) - 4, 86), disk_s, font=F_FOOT, fill=C_DISK)

    # ── network: SSID + IP ──────────────────────────────────────────────────────
    ssid = state.data["ssid"]
    if not ssid or ssid == "--":
        ssid = "offline"
    d.text((4, 98), ssid[:10], font=F_FOOT, fill=C_WIFI)
    d.text((W - _tw(d, state.data["wip"], F_IP) - 4, 97),
           state.data["wip"], font=F_IP, fill=C_WIFI)
    _sep(d, 110)

    # ── uptime + load ───────────────────────────────────────────────────────────
    d.text((4, 113), f"up {state.data['uptime']}", font=F_FOOT, fill=T_DIM)
    d.text((W - _tw(d, state.data["load_avg"], F_FOOT) - 4, 113),
           state.data["load_avg"], font=F_FOOT, fill=T_SEC)
    return img

# ── system ────────────────────────────────────────────────────────────────────
def draw_system():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "SYSTEM", ACC_SYS, HDR_SYS)

    # CPU: label + value + history sparkline
    try:   avg = int(state.data["cpu"])
    except: avg = 0
    d.text((4, 18), "CPU", font=F_LABEL, fill=T_SEC)
    d.text((W - _tw(d, f"{state.data['cpu']}%", F_VAL) - 4, 18),
           f"{state.data['cpu']}%", font=F_VAL, fill=T_PRI)
    _spark(d, 4, 30, W - 8, 12, state.cpu_hist, C_CPU, vmax=100)

    # RAM: label + value + history sparkline
    try:   ru = int(state.data["ram_used"])
    except: ru = 0
    d.text((4, 46), "RAM", font=F_LABEL, fill=T_SEC)
    d.text((W - _tw(d, f"{state.data['ram_used']}%", F_VAL) - 4, 46),
           f"{state.data['ram_used']}%", font=F_VAL, fill=T_PRI)
    _spark(d, 4, 58, W - 8, 12, state.ram_hist, C_RAM, vmax=100)

    # DISK bar
    try:   dp = int(state.data["disk"])
    except: dp = 0
    _bar_row(d, 74, "DISK", f"{state.data['disk']}%", dp, C_DISK)

    # TEMP + freq
    try:   t = float(state.data["temp"])
    except: t = 0.0
    tc = C_HOT if t >= 70 else (C_WARN if t >= 55 else C_OK)
    d.text((4,  92), "TEMP", font=F_LABEL, fill=T_SEC)
    d.text((30, 92), f"{state.data['temp']}C", font=F_VAL, fill=tc)
    d.text((W - _tw(d, state.data["cpu_freq"], F_LABEL) - 4, 92),
           state.data["cpu_freq"], font=F_LABEL, fill=T_DIM)

    _footer(d)
    return img

# ── network ───────────────────────────────────────────────────────────────────
def draw_network():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "NETWORK", ACC_NET, HDR_NET)

    try:
        quality = max(0, min(100, 2 * (int(state.data["rssi"]) + 100)))
    except Exception:
        quality = 0

    # WIFI row: label · dBm · signal bars
    y = 19
    d.text((4, y), "WIFI", font=F_LABEL, fill=T_DIM)
    _signal_bars(d, W - 20, y, quality)
    if state.data["rssi"] != "--":
        rs = f"{state.data['rssi']}dBm"
        d.text((W - 24 - _tw(d, rs, F_FOOT), y + 2), rs, font=F_FOOT, fill=T_SEC)

    # SSID
    y += 12
    ssid = state.data["ssid"]
    if ssid and ssid != "--":
        s = ssid
        while s and _tw(d, s, F_LABEL) > W - 8:
            s = s[:-1]
        d.text((4, y), s, font=F_LABEL, fill=C_WIFI)
    else:
        d.text((4, y), "not connected", font=F_LABEL, fill=T_DIM)

    # wlan IP
    y += 12
    d.text((4, y), state.data["wip"], font=F_IP, fill=C_WIFI)
    y += 14; _sep(d, y); y += 5

    # USB + Tailscale rows
    d.text((4, y), "USB", font=F_FOOT, fill=T_DIM)
    d.text((W - _tw(d, state.data["uip"], F_IP) - 4, y - 1), state.data["uip"], font=F_IP, fill=C_USB)
    y += 13
    d.text((4, y), "TS", font=F_FOOT, fill=T_DIM)
    d.text((W - _tw(d, state.data["tip"], F_IP) - 4, y - 1), state.data["tip"], font=F_IP, fill=C_TS)
    y += 14; _sep(d, y); y += 5

    # live throughput: speeds + tall dual sparklines filling the rest
    rx_s = state.data["rx_speed"] if state.data["rx_speed"] != "--" else "..."
    tx_s = state.data["tx_speed"] if state.data["tx_speed"] != "--" else "..."
    d.text((4, y), f"RX {rx_s}", font=F_FOOT, fill=C_USB)
    d.text((W - _tw(d, f"TX {tx_s}", F_FOOT) - 4, y), f"TX {tx_s}", font=F_FOOT, fill=C_WIFI)
    y += 11
    half = (W - 10) // 2
    sh   = H - y - 2          # stretch to the bottom edge
    _spark(d, 4,        y, half, sh, state.rx_hist, C_USB)
    _spark(d, 6 + half, y, half, sh, state.tx_hist, C_WIFI)

    return img

# ── pi-hole ───────────────────────────────────────────────────────────────────
def draw_pihole():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    status = state.data["pho_status"]
    if status == "enabled":    acc = C_OK
    elif status == "disabled": acc = C_HOT
    else:                      acc = T_DIM
    _header(d, "PI-HOLE", acc, HDR_PHO)

    # status dot in header
    d.ellipse([W - 26, 5, W - 20, 11], fill=acc)

    # ── block rate: big % + bar ─────────────────────────────────────────────────
    pct_s = f"{state.data['pho_pct']}%"
    try:    pctf = float(state.data["pho_pct"])
    except Exception: pctf = 0.0
    d.text((4, 19), "BLOCK RATE", font=F_LABEL, fill=T_SEC)
    d.text((W - _tw(d, pct_s, F_MED) - 4, 18), pct_s, font=F_MED, fill=C_WARN)
    _bar(d, 4, 36, W - 8, 6, pctf, C_HOT)
    _sep(d, 47)

    # ── stat grid ───────────────────────────────────────────────────────────────
    def stat(y, label, val, col):
        d.text((4, y), label, font=F_LABEL, fill=T_DIM)
        d.text((W - _tw(d, val, F_VAL) - 4, y), val, font=F_VAL, fill=col)

    stat(52, "Queries", state.data["pho_total"],   T_PRI)
    stat(66, "Blocked", state.data["pho_blocked"], C_HOT)
    stat(80, "Cached",  state.data["pho_cached"],  C_CPU)

    cl_s = f"{state.data['pho_clients']}"
    gv_s = f"{state.data['pho_gravity']}"
    d.text((4, 94), "Clients", font=F_LABEL, fill=T_DIM)
    d.text((44, 94), cl_s, font=F_VAL, fill=T_SEC)
    d.text((W // 2 + 6, 94), "Gravity", font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, gv_s, F_VAL) - 4, 94), gv_s, font=F_VAL, fill=T_SEC)
    _sep(d, 108)

    # ── last blocked domain ──────────────────────────────────────────────────────
    d.text((4, 112), "LAST", font=F_FOOT, fill=T_SEC)
    last = state.data["pho_last"]
    full = last
    while last and _tw(d, last + ("…" if len(last) < len(full) else ""), F_FOOT) > W - 34:
        last = last[:-1]
    if len(last) < len(full): last += "…"
    d.text((30, 112), last, font=F_FOOT, fill=ACC_PHO)
    return img

# ── games hub ─────────────────────────────────────────────────────────────────
_GAME_HS_KEYS = ["SNAKE", "PONG", "FLAPPY", "BREAKOUT", "INVADERS"]

def draw_games():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_GAME)
    d.rectangle([0, 0, 3, 15], fill=ACC_GAME)
    d.text((8, 3), "GAMES", font=F_HDR, fill=T_PRI)
    pg = f"{state.page + 1}/{PAGES}"
    d.text((W - _tw(d, pg, F_FOOT) - 4, 4), pg, font=F_FOOT, fill=T_DIM)

    n       = len(GAME_LIST)
    visible = 4
    offset  = max(0, state.game_sel - (visible - 1))
    row_h   = 26

    y = 18
    for i in range(offset, min(offset + visible, n)):
        name = GAME_LIST[i]
        sel  = (state.game_sel == i)
        hi   = state.high_scores.get(_GAME_HS_KEYS[i], 0)
        if sel:
            d.rectangle([0, y, W - 1, y + row_h - 2], fill=(40, 35, 0))
            d.rectangle([0, y, 3,     y + row_h - 2], fill=ACC_GAME)
        d.text((8, y + 5), name, font=F_VAL, fill=ACC_GAME if sel else T_DIM)
        hs_s = f"HI:{hi}"
        d.text((W - _tw(d, hs_s, F_FOOT) - 6, y + 7),
               hs_s, font=F_FOOT, fill=(180, 150, 0) if sel else T_DIM)
        y += row_h

    # show ▼ arrow only when more items exist below visible window
    if offset + visible < n:
        arrow = "▼ more"
        d.text(((W - _tw(d, arrow, F_FOOT)) // 2, H - 10),
               arrow, font=F_FOOT, fill=T_DIM)

    return img

# ── settings ──────────────────────────────────────────────────────────────────
def draw_set_hub():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "SETTINGS", ACC_SET, HDR_SET)

    vals = [f"{state.bl_pct}%", SLEEP_LABELS[state.sleep_idx],
            "ON" if state.wifi_on else "OFF",
            "ON" if state.bt_on else "OFF",
            "ON" if state.auto_dim else "OFF"]

    n       = len(SET_APPS)
    visible = 4
    offset  = max(0, state.set_sel - (visible - 1))

    y = 18
    for i in range(offset, min(offset + visible, n)):
        name, col, val = SET_APPS[i], SET_COLS[i], vals[i]
        sel = (state.set_sel == i)
        if sel:
            d.rectangle([0, y, W - 1, y + 22],
                        fill=(col[0] // 5, col[1] // 5, col[2] // 5))
            d.rectangle([0, y, 3, y + 22], fill=col)
        d.rectangle([6, y + 6, 16, y + 16], fill=col if sel else T_DIM)
        d.text((20, y + 6), name, font=F_LABEL, fill=T_PRI if sel else T_SEC)
        d.text((W - _tw(d, val, F_VAL) - 14, y + 6), val,
               font=F_VAL, fill=T_PRI if sel else T_DIM)
        y += 23

    # scroll arrows in the right gutter (only when there's more in that direction)
    if offset > 0:
        d.text((W - 9, 19),     "▲", font=F_FOOT, fill=ACC_SET)
    if offset + visible < n:
        d.text((W - 9, H - 11), "▼", font=F_FOOT, fill=ACC_SET)

    return img

def draw_set_bright():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=ACC_SET)
    d.text((8, 3), "BRIGHTNESS", font=F_HDR, fill=T_PRI)
    val = f"{state.bl_pct}%"
    d.text(((W - _tw(d, val, F_MED)) // 2, 33), val, font=F_MED, fill=ACC_SET)
    _bar(d, 14, 57, W - 28, 7, state.bl_pct, ACC_SET)
    _footer(d)
    return img

def draw_set_sleep():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    SL_COL = (55, 100, 220)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=SL_COL)
    d.text((8, 3), "SLEEP TIMER", font=F_HDR, fill=T_PRI)
    val = SLEEP_LABELS[state.sleep_idx]
    d.text(((W - _tw(d, val, F_MED)) // 2, 33), val, font=F_MED, fill=SL_COL)
    cols = 4; sw = (W - 8) // cols
    for j, lbl in enumerate(SLEEP_LABELS):
        gx = 4 + (j % cols) * sw
        gy = 60 + (j // cols) * 14
        sel = (j == state.sleep_idx)
        d.rectangle([gx, gy, gx + sw - 3, gy + 11],
                    fill=(25, 40, 80) if sel else BG,
                    outline=SL_COL if sel else T_DIM)
        d.text((gx + (sw - 3 - _tw(d, lbl, F_FOOT)) // 2, gy + 1),
               lbl, font=F_FOOT, fill=T_PRI if sel else T_DIM)
    return img

def draw_set_wifi():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=C_OK)
    d.text((8, 3), "WiFi", font=F_HDR, fill=T_PRI)
    dot_col = C_OK if state.wifi_on else C_HOT
    status  = "ON" if state.wifi_on else "OFF"
    d.ellipse([14, 26, 28, 40], fill=dot_col)
    d.text((35, 25), status, font=F_MED, fill=dot_col)
    y = 50
    if state.wifi_on:
        d.text((4, y), state.data["wip"], font=F_IP, fill=C_WIFI); y += 13
        if state.data["rssi"] != "--":
            d.text((4, y), f"Signal: {state.data['rssi']}dBm", font=F_LABEL, fill=T_SEC)
    _footer(d)
    return img

def draw_set_bt():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    BT_COL = (0, 185, 230)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=BT_COL)
    d.text((8, 3), "Bluetooth", font=F_HDR, fill=T_PRI)
    dot_col = BT_COL if state.bt_on else C_HOT
    status  = "ON" if state.bt_on else "OFF"
    d.ellipse([14, 26, 28, 40], fill=dot_col)
    d.text((35, 25), status, font=F_MED, fill=dot_col)
    _footer(d)
    return img

def draw_set_autodim():
    img    = Image.new("RGB", (W, H), BG)
    d      = ImageDraw.Draw(img)
    AD_COL = (255, 200, 0)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=AD_COL)
    d.text((8, 3), "AUTO-DIM", font=F_HDR, fill=T_PRI)
    dot_col = AD_COL if state.auto_dim else C_HOT
    status  = "ON" if state.auto_dim else "OFF"
    d.ellipse([14, 26, 28, 40], fill=dot_col)
    d.text((35, 25), status, font=F_MED, fill=dot_col)
    y = 50
    d.text((4, y), f"Night {NIGHT_START:02d}:00-{NIGHT_END:02d}:00", font=F_LABEL, fill=T_SEC)
    y += 13
    d.text((4, y), f"Caps brightness {NIGHT_CAP}%", font=F_LABEL, fill=T_DIM)
    y += 13
    night = "now: NIGHT" if state.is_night() else "now: DAY"
    d.text((4, y), night, font=F_LABEL, fill=AD_COL if state.is_night() else T_DIM)
    _footer(d)
    return img

def draw_settings_page():
    if   state.set_app == 0: return draw_set_bright()
    elif state.set_app == 1: return draw_set_sleep()
    elif state.set_app == 2: return draw_set_wifi()
    elif state.set_app == 3: return draw_set_bt()
    elif state.set_app == 4: return draw_set_autodim()
    else:                    return draw_set_hub()

# ── power ─────────────────────────────────────────────────────────────────────
def draw_power():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_PWR)
    d.rectangle([0, 0, 3, 15], fill=ACC_PWR)
    d.text((8, 3), "POWER", font=F_HDR, fill=T_PRI)
    labels = [("REBOOT",    (255, 140, 40)),
              ("POWER OFF", (255,  60, 60))]
    y0, row_h = 24, 36
    for i, (label, col) in enumerate(labels):
        y   = y0 + i * row_h
        sel = (state.power_sel == i)
        if sel:
            d.rectangle([0, y, W - 1, y + row_h - 2],
                        fill=(col[0] // 6, col[1] // 6, col[2] // 6))
            d.rectangle([0, y, 3, y + row_h - 2], fill=col)
        cx = (W - _tw(d, label, F_VAL)) // 2
        d.text((cx, y + (row_h - 12) // 2), label, font=F_VAL, fill=col if sel else T_DIM)

    _footer(d)
    return img

# ── hints ─────────────────────────────────────────────────────────────────────
def draw_hints():
    HNT_BG  = (18, 14, 30)
    HNT_ACC = (130, 100, 200)
    img = Image.new("RGB", (W, H), HNT_BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=(30, 24, 48))
    d.rectangle([0, 0, 3, 15], fill=HNT_ACC)
    d.text((8, 3), "CONTROLS", font=F_HDR, fill=T_PRI)

    def row(y, label, val, col=T_SEC):
        d.text((6, y), label, font=F_FOOT, fill=T_DIM)
        d.text((W - _tw(d, val, F_FOOT) - 4, y), val, font=F_FOOT, fill=col)

    y = 19
    row(y, "L / R",   "pages");          y += 12
    row(y, "UP / DN", "scroll / select"); y += 12
    row(y, "PRESS",   "confirm / toggle"); y += 12
    _sep(d, y); y += 4
    row(y, "KEY1",    "power",   ACC_PWR); y += 12
    row(y, "KEY2",    "home",    ACC_NET); y += 12
    row(y, "KEY3",    "back",    ACC_SYS); y += 12
    _sep(d, y); y += 4
    row(y, "Games",   "PRESS: launch",  ACC_GAME); y += 12
    row(y, "Settings", "PRESS: open",   ACC_SET)

    return img

# ── render dispatcher ─────────────────────────────────────────────────────────
def _build():
    if   state.power_open:           return draw_power()
    elif state.hints_open:           return draw_hints()
    elif state.page == PAGE_HOME:    return draw_home()
    elif state.page == PAGE_SYS:     return draw_system()
    elif state.page == PAGE_NET:     return draw_network()
    elif state.page == PAGE_PHO:     return draw_pihole()
    elif state.page == PAGE_GAMES:   return draw_games()
    elif state.page == PAGE_SET:     return draw_settings_page()
    else:                            return draw_system()

def render():
    global _last_img
    img = _build()
    _last_img = img
    with state._lock:
        state.lcd.LCD_ShowImage(img)

def slide_render(direction):
    """Slide to the current page from left (direction=-1) or right (direction=1)."""
    global _last_img
    from_img = _last_img
    to_img   = _build()
    _last_img = to_img
    if from_img is None:
        with state._lock:
            state.lcd.LCD_ShowImage(to_img)
        return
    steps = 4
    wide  = Image.new("RGB", (W * 2, H))
    if direction > 0:   # new page slides in from right
        wide.paste(from_img, (0, 0))
        wide.paste(to_img,   (W, 0))
        xs = [W * i // steps for i in range(1, steps + 1)]
    else:               # new page slides in from left
        wide.paste(to_img,   (0, 0))
        wide.paste(from_img, (W, 0))
        xs = [W - W * i // steps for i in range(1, steps + 1)]
    for x in xs:
        frame = wide.crop((x, 0, x + W, H))
        with state._lock:
            state.lcd.LCD_ShowImage(frame)
