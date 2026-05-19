import time
from PIL import Image, ImageDraw
import state
from constants import *

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
    _bar(d, 4, y + 11, W - 8, 6, pct, bar_color)

def _header(d, title, accent, hdr_bg):
    d.rectangle([0, 0, W - 1, 15], fill=hdr_bg)
    d.rectangle([0, 0, 3, 15], fill=accent)
    d.line([(4, 15), (W - 1, 15)], fill=accent)
    d.text((8, 3), title, font=F_HDR, fill=T_PRI)

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

    # ── clock + date ──────────────────────────────────────────────────────────
    clk = time.strftime("%H:%M")
    d.text(((W - _tw(d, clk, F_BIG)) // 2, 2), clk, font=F_BIG, fill=T_PRI)

    date_s = time.strftime("%a, %d %b %Y")
    d.text(((W - _tw(d, date_s, F_LABEL)) // 2, 30), date_s, font=F_LABEL, fill=T_SEC)

    mx = W // 2
    d.line([(mx - 22, 42), (mx + 22, 42)], fill=ACC_SYS)

    # ── weather ───────────────────────────────────────────────────────────────
    city_s = state.data["wth_city"]
    if city_s in ("--", ""):
        city_s = state.weather_city or "—"
    city_s = city_s[:14]

    temp_w = f"{state.data['wth_temp']}C"
    tc     = _temp_color(state.data["wth_temp"], hot=35, warn=25)
    d.text((W - _tw(d, temp_w, F_MED) - 4, 44), temp_w, font=F_MED, fill=tc)
    d.text((4, 47), city_s, font=F_LABEL, fill=T_SEC)

    desc_s = state.data["wth_desc"]
    if _tw(d, desc_s, F_FOOT) > W - 8:
        while desc_s and _tw(d, desc_s + "…", F_FOOT) > W - 8:
            desc_s = desc_s[:-1]
        desc_s += "…"
    d.text((4, 60), desc_s, font=F_FOOT, fill=T_DIM)

    # ── quick system glance ───────────────────────────────────────────────────
    _sep(d, 73)

    try:   cpu_p = int(state.data["cpu"])
    except: cpu_p = 0
    cpu_s = f"{state.data['cpu']}%"
    tc2   = _temp_color(state.data["temp"], hot=70, warn=55)

    d.text((4, 76),  "CPU", font=F_FOOT, fill=T_DIM)
    d.text((28, 76), cpu_s, font=F_FOOT, fill=C_CPU)
    _bar(d, 60, 78, 38, 5, cpu_p, C_CPU)
    d.text((W - _tw(d, f"{state.data['temp']}C", F_FOOT) - 4, 76),
           f"{state.data['temp']}C", font=F_FOOT, fill=tc2)

    _sep(d, 89)
    d.text((4, 92), f"up {state.data['uptime']}", font=F_FOOT, fill=T_DIM)

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
    d.rectangle([4, 50, 4 + bw - 1, 55], fill=TRACK)
    fu = max(0, int((bw - 2) * ru / 100))
    fc = max(0, int((bw - 2) * rc / 100))
    if fu > 0: d.rectangle([5, 51, 5 + fu - 1, 54], fill=C_RAM)
    if fc > 0: d.rectangle([5 + fu, 51, 5 + fu + fc - 1, 54], fill=(90, 50, 150))

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
    _bar(d, 4, y, W - 8, 5, quality, bcol)
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
        d.rectangle([3, y + 2, 9, y + 8], fill=dot_col)
        d.text((14, y), label, font=F_LABEL, fill=T_PRI)
        d.text((W - _tw(d, status, F_LABEL) - 4, y), status, font=F_LABEL, fill=dot_col)
        y += 14; _sep(d, y); y += 5

    d.text((4, y), "LAST LOGIN", font=F_LABEL, fill=T_DIM)
    y += 10
    d.text((4, y), state.data["last_login"], font=F_LABEL, fill=T_SEC)
    y += 10; _sep(d, y); y += 4

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
    _sep(d, 92)
    d.text((4, 95), "PRESS:toggle  K3:refresh", font=F_FOOT, fill=T_DIM)

    _footer(d)
    return img

# ── games hub ─────────────────────────────────────────────────────────────────
def draw_games():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_GAME)
    d.rectangle([0, 0, 3, 15], fill=ACC_GAME)
    d.line([(4, 15), (W - 1, 15)], fill=ACC_GAME)
    d.text((8, 3), "GAMES", font=F_HDR, fill=T_PRI)

    y = 24
    for i, name in enumerate(GAME_LIST):
        sel = (state.game_sel == i)
        if sel:
            d.rectangle([0, y - 3, W - 1, y + 17], fill=(40, 35, 0))
            d.rectangle([0, y - 3, 3,     y + 17], fill=ACC_GAME)
        d.text((10, y + 3), name, font=F_VAL, fill=ACC_GAME if sel else T_DIM)
        y += 26

    _sep(d, 100)
    d.text((4, 103), "UP/DN: pick   PRESS: play", font=F_FOOT, fill=T_DIM)
    d.text((4, 113), "L/R  : exit",               font=F_FOOT, fill=T_DIM)
    return img

# ── settings ──────────────────────────────────────────────────────────────────
def draw_set_hub():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    _header(d, "SETTINGS", ACC_SET, HDR_SET)

    vals = [f"{state.bl_pct}%", SLEEP_LABELS[state.sleep_idx],
            "ON" if state.wifi_on else "OFF", "ON" if state.bt_on else "OFF"]
    y = 18
    for i, (name, col, val) in enumerate(zip(SET_APPS, SET_COLS, vals)):
        sel = (state.set_sel == i)
        if sel:
            d.rectangle([0, y, W - 1, y + 22],
                        fill=(col[0] // 4, col[1] // 4, col[2] // 4))
            d.rectangle([0, y, 3, y + 22], fill=col)
        d.rectangle([6, y + 6, 16, y + 16], fill=col if sel else T_DIM)
        d.text((20, y + 6), name, font=F_LABEL, fill=T_PRI if sel else T_SEC)
        d.text((W - _tw(d, val, F_VAL) - 4, y + 6), val,
               font=F_VAL, fill=T_PRI if sel else T_DIM)
        y += 23

    _sep(d, 112)
    d.text((4, 115), "PRESS:open  KEY2:exit", font=F_FOOT, fill=T_DIM)
    return img

def draw_set_bright():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=ACC_SET)
    d.line([(4, 15), (W - 1, 15)], fill=ACC_SET)
    d.text((8, 3), "BRIGHTNESS", font=F_HDR, fill=T_PRI)
    val = f"{state.bl_pct}%"
    d.text(((W - _tw(d, val, F_MED)) // 2, 33), val, font=F_MED, fill=ACC_SET)
    _bar(d, 14, 57, W - 28, 7, state.bl_pct, ACC_SET)
    _sep(d, 74)
    d.text((4, 77), "L / R : adjust", font=F_FOOT, fill=T_DIM)
    d.text((4, 89), "KEY2  : back",   font=F_FOOT, fill=T_DIM)
    _footer(d)
    return img

def draw_set_sleep():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    SL_COL = (55, 100, 220)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=SL_COL)
    d.line([(4, 15), (W - 1, 15)], fill=SL_COL)
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
    _sep(d, 102)
    d.text((4, 105), "L/R: change  KEY2: back", font=F_FOOT, fill=T_DIM)
    return img

def draw_set_wifi():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=C_OK)
    d.line([(4, 15), (W - 1, 15)], fill=C_OK)
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
    _sep(d, 88)
    d.text((4,  91), "PRESS : toggle", font=F_FOOT, fill=T_PRI)
    d.text((4, 103), "KEY2  : back",   font=F_FOOT, fill=T_DIM)
    _footer(d)
    return img

def draw_set_bt():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    BT_COL = (0, 185, 230)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_SET)
    d.rectangle([0, 0, 3, 15], fill=BT_COL)
    d.line([(4, 15), (W - 1, 15)], fill=BT_COL)
    d.text((8, 3), "Bluetooth", font=F_HDR, fill=T_PRI)
    dot_col = BT_COL if state.bt_on else C_HOT
    status  = "ON" if state.bt_on else "OFF"
    d.ellipse([14, 26, 28, 40], fill=dot_col)
    d.text((35, 25), status, font=F_MED, fill=dot_col)
    _sep(d, 88)
    d.text((4,  91), "PRESS : toggle", font=F_FOOT, fill=T_PRI)
    d.text((4, 103), "KEY2  : back",   font=F_FOOT, fill=T_DIM)
    _footer(d)
    return img

def draw_settings_page():
    if   state.set_app == 0: return draw_set_bright()
    elif state.set_app == 1: return draw_set_sleep()
    elif state.set_app == 2: return draw_set_wifi()
    elif state.set_app == 3: return draw_set_bt()
    else:                    return draw_set_hub()

# ── power ─────────────────────────────────────────────────────────────────────
def draw_power():
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, 15], fill=HDR_PWR)
    d.rectangle([0, 0, 3, 15], fill=ACC_PWR)
    d.line([(4, 15), (W - 1, 15)], fill=ACC_PWR)
    d.text((8, 3), "POWER", font=F_HDR, fill=T_PRI)
    d.text((W - _tw(d, "KEY1=back", F_FOOT) - 4, 4), "KEY1=back", font=F_FOOT, fill=T_DIM)

    labels = [("REBOOT",    (255, 140, 40)),
              ("POWER OFF", (255,  60, 60))]
    y0, row_h = 20, 32
    for i, (label, col) in enumerate(labels):
        y   = y0 + i * row_h
        sel = (state.power_sel == i)
        if sel:
            d.rectangle([0, y, W - 1, y + row_h - 2],
                        fill=(col[0] // 6, col[1] // 6, col[2] // 6))
            d.rectangle([0, y, 3, y + row_h - 2], fill=col)
        cx = (W - _tw(d, label, F_VAL)) // 2
        d.text((cx, y + (row_h - 12) // 2), label, font=F_VAL, fill=col if sel else T_DIM)

    _sep(d, 88)
    d.text((4,  91), "UP/DN: select  K1/K2: back", font=F_FOOT, fill=T_DIM)
    d.text((4, 102), "PRESS : confirm",             font=F_FOOT, fill=ACC_PWR)
    _footer(d)
    return img

# ── render dispatcher ─────────────────────────────────────────────────────────
def render():
    if   state.power_open:           img = draw_power()
    elif state.page == PAGE_HOME:    img = draw_home()
    elif state.page == PAGE_SYS:     img = draw_system()
    elif state.page == PAGE_NET:     img = draw_network()
    elif state.page == PAGE_SVC:     img = draw_services()
    elif state.page == PAGE_PHO:     img = draw_pihole()
    elif state.page == PAGE_GAMES:   img = draw_games()
    elif state.page == PAGE_SET:     img = draw_settings_page()
    else:                            img = draw_system()
    with state._lock:
        state.lcd.LCD_ShowImage(img)
