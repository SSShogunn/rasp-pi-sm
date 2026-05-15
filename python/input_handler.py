import time, threading, subprocess, logging
from PIL import Image, ImageDraw
import state, settings_mgr, pihole_api, games
import draw
from constants import (PAGES, PAGE_SYS, PAGE_SET, PAGE_PHO, PAGE_GAMES,
                       SLEEP_PRESETS, GAME_LIST, W, H, F_VAL, ACC_PWR, T_PRI)

log = logging.getLogger(__name__)

# ── sleep helpers ─────────────────────────────────────────────────────────────
def _touch():
    state.last_activity = time.time()

def _wake_if_sleeping():
    _touch()
    if state.sleeping:
        state.sleeping = False
        with state._lock:
            state.lcd.bl_DutyCycle(state.bl_pct)
        draw.render()
        return True
    return False

# ── button actions ────────────────────────────────────────────────────────────
def _up():
    if _wake_if_sleeping(): return
    _touch()
    if state.power_open:
        state.power_sel = (state.power_sel - 1) % 2; draw.render()
    elif state.page == PAGE_GAMES:
        state.game_sel = (state.game_sel - 1) % len(GAME_LIST); draw.render()
    elif state.page == PAGE_SET and state.set_app is None:
        state.set_sel = (state.set_sel - 1) % 4; draw.render()

def _down():
    if _wake_if_sleeping(): return
    _touch()
    if state.power_open:
        state.power_sel = (state.power_sel + 1) % 2; draw.render()
    elif state.page == PAGE_GAMES:
        state.game_sel = (state.game_sel + 1) % 3; draw.render()
    elif state.page == PAGE_SET and state.set_app is None:
        state.set_sel = (state.set_sel + 1) % 4; draw.render()

def _left():
    if _wake_if_sleeping(): return
    _touch()
    if state.power_open:
        state.power_open = False; draw.render(); return
    if state.page == PAGE_SET and state.set_app is not None:
        if state.set_app == 0:
            state.bl_pct = max(10, state.bl_pct - 10)
            with state._lock: state.lcd.bl_DutyCycle(state.bl_pct)
            settings_mgr.save()
        elif state.set_app == 1:
            state.sleep_idx = max(0, state.sleep_idx - 1)
            settings_mgr.save()
        draw.render(); return
    state.page = (state.page - 1) % PAGES
    draw.render()

def _right():
    if _wake_if_sleeping(): return
    _touch()
    if state.power_open:
        state.power_open = False; draw.render(); return
    if state.page == PAGE_SET and state.set_app is not None:
        if state.set_app == 0:
            state.bl_pct = min(100, state.bl_pct + 10)
            with state._lock: state.lcd.bl_DutyCycle(state.bl_pct)
            settings_mgr.save()
        elif state.set_app == 1:
            state.sleep_idx = min(len(SLEEP_PRESETS) - 1, state.sleep_idx + 1)
            settings_mgr.save()
        draw.render(); return
    state.page = (state.page + 1) % PAGES
    draw.render()

def _key2():
    if _wake_if_sleeping(): return
    _touch()
    if state.power_open:
        state.power_open = False; draw.render(); return
    if state.set_app is not None:
        state.set_app = None; draw.render(); return
    if state.page == PAGE_SET:
        state.page = PAGE_SYS; draw.render(); return
    state.page = PAGE_SET; draw.render()

def _refresh():
    if _wake_if_sleeping(): return
    _touch()
    if state.power_open:
        state.power_open = False; draw.render(); return
    state._fetch_now.set()

def _toggle_power():
    if _wake_if_sleeping(): return
    _touch()
    if state.game_active: return
    state.power_open = not state.power_open
    state.power_sel  = 0
    draw.render()

def _toggle_pihole():
    pihole_api.toggle(draw.render)

def _press():
    if _wake_if_sleeping(): return
    _touch()
    if state.game_active: return
    if not state.power_open and state.page == PAGE_PHO:
        threading.Thread(target=_toggle_pihole, daemon=True).start(); return
    if not state.power_open and state.page == PAGE_GAMES:
        games.launch(state.game_sel); return
    if not state.power_open and state.page == PAGE_SET:
        if state.set_app is None:
            state.set_app = state.set_sel; draw.render(); return
        elif state.set_app == 2:
            state.wifi_on = not state.wifi_on
            subprocess.run(["rfkill", "unblock" if state.wifi_on else "block", "wlan"], check=False)
            draw.render(); return
        elif state.set_app == 3:
            state.bt_on = not state.bt_on
            subprocess.run(["rfkill", "unblock" if state.bt_on else "block", "bluetooth"], check=False)
            draw.render(); return
    if not state.power_open:
        return
    msg = "REBOOTING..." if state.power_sel == 0 else "SHUTTING DOWN..."
    img = Image.new("RGB", (W, H), (25, 0, 0))
    d   = ImageDraw.Draw(img)
    tw  = lambda t, f: int(d.textlength(t, font=f))
    d.text(((W - tw(msg, F_VAL)) // 2, H // 2 - 5), msg, font=F_VAL, fill=ACC_PWR)
    with state._lock:
        state.lcd.LCD_ShowImage(img)
    time.sleep(0.8)
    subprocess.run(["reboot"] if state.power_sel == 0 else ["poweroff"])

# ── button polling ────────────────────────────────────────────────────────────
_DEBOUNCE = 0.15

def start_polling():
    lcd = state.lcd
    handlers = [
        (lcd.GPIO_KEY_UP_PIN,    _up),
        (lcd.GPIO_KEY_DOWN_PIN,  _down),
        (lcd.GPIO_KEY_LEFT_PIN,  _left),
        (lcd.GPIO_KEY_RIGHT_PIN, _right),
        (lcd.GPIO_KEY_PRESS_PIN, _press),
        (lcd.GPIO_KEY1_PIN,      _toggle_power),
        (lcd.GPIO_KEY2_PIN,      _key2),
        (lcd.GPIO_KEY3_PIN,      _refresh),
    ]
    prev      = [pin.value for pin, _ in handlers]
    last_fire = [0.0] * len(handlers)

    while state.running:
        time.sleep(0.05)
        if state.game_active:
            for i, (pin, _) in enumerate(handlers):
                prev[i] = pin.value
            continue
        now = time.time()
        for i, (pin, handler) in enumerate(handlers):
            curr = pin.value
            if curr and not prev[i] and (now - last_fire[i]) >= _DEBOUNCE:
                last_fire[i] = now
                threading.Thread(target=handler, daemon=True).start()
            prev[i] = curr
