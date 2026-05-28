#!/usr/bin/env python3
"""
Pi Zero 2W Dashboard
Pages: Home · System · Network · Pi-hole · Games · Settings
Keys:  Up/Down    = navigate menus
       Left/Right = change pages / adjust values
       KEY1 = power  KEY2 = home  KEY3 = back  PRESS = confirm / toggle
Run:   cd python && sudo python3 monitor.py
"""

import time, signal, threading, logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("monitor")

# ── init hardware + load settings before anything else ───────────────────────
import state
import settings_mgr
settings_mgr.load()

# ── boot splash while the heavier modules import ──────────────────────────────
import splash
state.apply_backlight()
splash.show(state.lcd)

# ── imports that depend on state being ready ──────────────────────────────────
import fetch, draw, games, input_handler
from draw import render
from constants import SLEEP_PRESETS

# ── wire up cross-module references ──────────────────────────────────────────
games.init(state.lcd, state._lock, render)

# ── light up immediately, all data fetched in background ─────────────────────
log.info("Starting dashboard...")
state.apply_backlight()
render()
log.info("Dashboard running — Ctrl-C to quit")

# ── start background threads ──────────────────────────────────────────────────
_fetch_thread  = threading.Thread(target=fetch.run_bg,               args=(render,), daemon=True)
_button_thread = threading.Thread(target=input_handler.start_polling,              daemon=True)
_fetch_thread.start()
state._fetch_now.set()   # kick off first fetch immediately
_button_thread.start()

# ── signal handler ────────────────────────────────────────────────────────────
def _sig(s, f):
    state.running = False

signal.signal(signal.SIGINT,  _sig)
signal.signal(signal.SIGTERM, _sig)

# ── main loop: sleep timeout only ─────────────────────────────────────────────
try:
    while state.running:
        now        = time.time()
        sleep_secs = SLEEP_PRESETS[state.sleep_idx]
        if not state.sleeping and not state.game_active and sleep_secs > 0 and (now - state.last_activity) >= sleep_secs:
            state.sleeping = True
        # one place owns the backlight: handles sleep + night auto-dim
        if not state.game_active:
            state.apply_backlight()
        time.sleep(0.1)
finally:
    log.info("Shutting down...")
    from PIL import Image
    with state._lock:
        state.lcd.bl_DutyCycle(0)
        state.lcd.LCD_ShowImage(Image.new("RGB", (128, 128), (0, 0, 0)))
        state.lcd.module_exit()
