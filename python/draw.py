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

# ── home ──────────────────────────────────────────────────────────────────────
def draw_home():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    pg = f"{state.page + 1}/{PAGES}"
    d.text((W - _tw(d, pg, F_FOOT) - 4, 4), pg, font=F_FOOT, fill=T_DIM)

    now    = time.localtime()
    clk    = time.strftime("%H:%M", now)
    date_s = time.strftime("%a, %d %b %Y", now)
    d.text(((W - _tw(d, clk, F_BIG)) // 2, 2), clk, font=F_BIG, fill=T_PRI)
    d.text(((W - _tw(d, date_s, F_LABEL)) // 2, 32), date_s, font=F_LABEL, fill=T_DIM)
    _sep(d, 44)

    city_s = state.data["wth_city"] if state.data["wth_city"] != "--" else state.weather_city
    temp_w = f"{state.data['wth_temp']}C"
    d.text((4, 47), (city_s[:13] if city_s else "No city set"), font=F_LABEL, fill=T_SEC)
    d.text((W - _tw(d, temp_w, F_VAL) - 4, 47), temp_w, font=F_VAL,
           fill=_temp_color(state.data["wth_temp"], hot=35, warn=28))

    desc_s = state.data["wth_desc"]
    if _tw(d, desc_s, F_LABEL) > W - 8:
        while desc_s and _tw(d, desc_s + "…", F_LABEL) > W - 8:
            desc_s = desc_s[:-1]
        desc_s += "…"
    d.text((4, 59), desc_s, font=F_LABEL, fill=T_DIM)
    d.text((4, 70),
           f"FL:{state.data['wth_feels']}C  W:{state.data['wth_wind']}m/s  H:{state.data['wth_humidity']}%",
           font=F_FOOT, fill=T_DIM)

    _sep(d, 84)
    d.text((4, 87), f"up {state.data['uptime']}", font=F_FOOT, fill=T_DIM)
    d.text((W - _tw(d, clk, F_FOOT) - 4, 87), clk, font=F_FOOT, fill=T_DIM)
    _sep(d, 99)
    hint = "▼ controls"
    d.text(((W - _tw(d, hint, F_FOOT)) // 2, 103), hint, font=F_FOOT, fill=T_DIM)
    return img

# ── system ────────────────────────────────────────────────────────────────────
def draw_system():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "SYSTEM", ACC_SYS, HDR_SYS)

    try:   avg = int(state.data["cpu"])
    except: avg = 0
    _bar_row(d, 18, "CPU", f"{state.data['cpu']}%", avg, C_CPU)

    try:   ru = int(state.data["ram_used"])
    except: ru = 0
    try:   rc = int(state.data["ram_cache"])
    except: rc = 0
    d.text((4, 38), "RAM", font=F_LABEL, fill=T_SEC)
    d.text((W - _tw(d, f"{state.data['ram_used']}%", F_VAL) - 4, 38),
           f"{state.data['ram_used']}%", font=F_VAL, fill=T_PRI)
    bw = W - 10
    d.rectangle([4, 50, 4 + bw - 1, 53], fill=TRACK)
    fu = max(0, int((bw - 2) * ru / 100))
    fc = max(0, int((bw - 2) * rc / 100))
    if fu > 0: d.rectangle([5, 51, 5 + fu - 1, 52], fill=C_RAM)
    if fc > 0: d.rectangle([5 + fu, 51, 5 + fu + fc - 1, 52], fill=(70, 40, 120))

    try:   dp = int(state.data["disk"])
    except: dp = 0
    _bar_row(d, 58, "DISK", f"{state.data['disk']}%", dp, C_DISK)

    try:   t = float(state.data["temp"])
    except: t = 0.0
    tc = C_HOT if t >= 70 else (C_WARN if t >= 55 else C_OK)
    d.text((4,  76), "TEMP", font=F_LABEL, fill=T_SEC)
    d.text((30, 76), f"{state.data['temp']}C", font=F_VAL, fill=tc)
    d.text((W - _tw(d, state.data["cpu_freq"], F_LABEL) - 4, 76),
           state.data["cpu_freq"], font=F_LABEL, fill=T_DIM)

    rx_s = f"IN  {state.data['rx_total']}"
    tx_s = f"OUT {state.data['tx_total']}"
    d.text((4,  90), rx_s, font=F_FOOT, fill=C_USB)
    d.text((W - _tw(d, tx_s, F_FOOT) - 4, 90), tx_s, font=F_FOOT, fill=C_WIFI)

    _footer(d)
    return img

# ── network ───────────────────────────────────────────────────────────────────
def draw_network():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "NETWORK", ACC_NET, HDR_NET)

    y = 18
    d.text((4, y), "WIFI", font=F_LABEL, fill=T_DIM)
    if state.data["rssi"] != "--":
        rs = f"{state.data['rssi']}dBm"
        d.text((W - _tw(d, rs, F_LABEL) - 4, y), rs, font=F_LABEL, fill=C_WIFI)
    y += 11
    try:
        quality = max(0, min(100, 2 * (int(state.data["rssi"]) + 100)))
        bcol = C_OK if quality >= 60 else (C_WARN if quality >= 30 else C_HOT)
    except Exception:
        quality, bcol = 0, TRACK
    _bar(d, 4, y, W - 8, 3, quality, bcol)
    y += 6
    d.text((4, y), state.data["wip"], font=F_IP, fill=C_WIFI)
    y += 13; _sep(d, y); y += 5

    d.text((4, y), "USB", font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, state.data["uip"], F_IP) - 4, y), state.data["uip"], font=F_IP, fill=C_USB)
    y += 12; _sep(d, y); y += 5

    d.text((4, y), "TS", font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, state.data["tip"], F_IP) - 4, y), state.data["tip"], font=F_IP, fill=C_TS)
    y += 12; _sep(d, y); y += 5

    rx_s = state.data["rx_speed"] if state.data["rx_speed"] != "--" else "..."
    tx_s = state.data["tx_speed"] if state.data["tx_speed"] != "--" else "..."
    d.text((4, y), f"RX {rx_s}", font=F_FOOT, fill=C_USB)
    d.text((W - _tw(d, f"TX {tx_s}", F_FOOT) - 4, y), f"TX {tx_s}", font=F_FOOT, fill=C_WIFI)

    _footer(d)
    return img

# ── services ──────────────────────────────────────────────────────────────────
def draw_services():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "SERVICES", ACC_SVC, HDR_SVC)

    y = 18
    for label, _ in SERVICES:
        active  = state.svc_statuses.get(label, False)
        dot_col = C_OK if active else C_HOT
        status  = "ACTIVE" if active else "STOPPED"
        d.rectangle([4, y + 2, 8, y + 6], fill=dot_col)
        d.text((12, y), label, font=F_LABEL, fill=T_PRI)
        d.text((W - _tw(d, status, F_LABEL) - 4, y), status, font=F_LABEL, fill=dot_col)
        y += 14; _sep(d, y); y += 5

    d.text((4, y), "LOAD", font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, state.data["load_avg"], F_LABEL) - 4, y),
           state.data["load_avg"], font=F_LABEL, fill=T_SEC)
    y += 13; _sep(d, y); y += 5

    upd     = state.data["updates"]
    upd_col = C_WARN if "pending" in upd else (C_OK if "up to date" in upd else T_SEC)
    d.text((4, y), "UPDATES", font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, upd, F_LABEL) - 4, y), upd, font=F_LABEL, fill=upd_col)

    _footer(d)
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

    pct_s = f"{state.data['pho_pct']}%"
    d.text((4,  18), "BLOCKED", font=F_LABEL, fill=T_SEC)
    d.text((54, 18), state.data["pho_blocked"], font=F_VAL, fill=C_HOT)
    d.text((W - _tw(d, pct_s, F_VAL) - 4, 18), pct_s, font=F_VAL, fill=C_WARN)

    d.text((4,  30), "QUERIES", font=F_LABEL, fill=T_SEC)
    d.text((54, 30), state.data["pho_total"], font=F_VAL, fill=T_PRI)

    d.text((4,  42), "CACHED", font=F_LABEL, fill=T_SEC)
    d.text((54, 42), state.data["pho_cached"], font=F_VAL, fill=C_CPU)

    cl_s = f"CLNTS {state.data['pho_clients']}"
    gv_s = f"GRV {state.data['pho_gravity']}"
    d.text((4,  54), cl_s, font=F_LABEL, fill=T_DIM)
    d.text((W - _tw(d, gv_s, F_LABEL) - 4, 54), gv_s, font=F_LABEL, fill=T_DIM)
    _sep(d, 66)

    d.text((4, 69), "LAST BLOCK", font=F_LABEL, fill=T_SEC)
    last = state.data["pho_last"]
    while last and _tw(d, last + ("…" if len(last) < len(state.data["pho_last"]) else ""), F_LABEL) > W - 8:
        last = last[:-1]
    if len(last) < len(state.data["pho_last"]): last += "…"
    d.text((4, 79), last, font=F_LABEL, fill=ACC_PHO)
    _footer(d)
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
            "ON" if state.hotspot_on else "OFF"]

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
        d.text((W - _tw(d, val, F_VAL) - 8, y + 6), val,
               font=F_VAL, fill=T_PRI if sel else T_DIM)
        y += 23

    # scroll indicator (right edge dots)
    if n > visible:
        dot_h  = (visible * 23) // n
        dot_y  = 18 + offset * (visible * 23) // n
        d.rectangle([W - 3, 18, W - 1, 18 + visible * 23 - 1], fill=T_DIM)
        d.rectangle([W - 3, dot_y, W - 1, dot_y + dot_h - 1], fill=ACC_SET)

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

def draw_set_hotspot():
    img    = Image.new("RGB", (W, H), BG)
    d      = ImageDraw.Draw(img)
    HS_COL = (255, 120, 30)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=HS_COL)
    d.text((8, 3), "HOTSPOT", font=F_HDR, fill=T_PRI)
    dot_col = HS_COL if state.hotspot_on else C_HOT
    status  = "ON" if state.hotspot_on else "OFF"
    d.ellipse([14, 26, 28, 40], fill=dot_col)
    d.text((35, 25), status, font=F_MED, fill=dot_col)
    y = 50
    if state.hotspot_on:
        d.text((4, y), "SSID: Pi-Dash",  font=F_LABEL, fill=T_SEC); y += 13
        d.text((4, y), "IP:   10.42.0.1", font=F_LABEL, fill=HS_COL)
    else:
        d.text((4, y), "Disables WiFi", font=F_LABEL, fill=T_DIM)
    _footer(d)
    return img

def draw_settings_page():
    if   state.set_app == 0: return draw_set_bright()
    elif state.set_app == 1: return draw_set_sleep()
    elif state.set_app == 2: return draw_set_wifi()
    elif state.set_app == 3: return draw_set_bt()
    elif state.set_app == 4: return draw_set_hotspot()
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
    row(y, "Pi-hole", "PRESS: toggle",  ACC_PHO); y += 12
    row(y, "Games",   "PRESS: launch",  ACC_GAME)

    return img

# ── render dispatcher ─────────────────────────────────────────────────────────
def _build():
    if   state.power_open:           return draw_power()
    elif state.hints_open:           return draw_hints()
    elif state.page == PAGE_HOME:    return draw_home()
    elif state.page == PAGE_SYS:     return draw_system()
    elif state.page == PAGE_NET:     return draw_network()
    elif state.page == PAGE_SVC:     return draw_services()
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
