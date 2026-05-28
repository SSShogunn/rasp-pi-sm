import threading, time, os, subprocess, collections
import LCD_1in44
from constants import NIGHT_START, NIGHT_END, NIGHT_CAP

def _get_rfkill(kind):
    try:
        for entry in sorted(os.listdir("/sys/class/rfkill")):
            with open(f"/sys/class/rfkill/{entry}/type") as f:
                if f.read().strip() == kind:
                    with open(f"/sys/class/rfkill/{entry}/soft") as f2:
                        return f2.read().strip() == "0"
    except Exception:
        pass
    return True

def _get_hotspot():
    try:
        r = subprocess.run(["nmcli", "-t", "-f", "NAME", "con", "show", "--active"],
                           capture_output=True, text=True, check=False)
        return "Hotspot" in r.stdout.splitlines()
    except Exception:
        return False

# ── shared data dict ──────────────────────────────────────────────────────────
data = dict(
    cpu="--", ram_used="--", ram_cache="--",
    temp="--", disk="--", uptime="...",
    cpu_freq="--",
    wip="...", uip="...", tip="...", ssid="--",
    rssi="--", rx_speed="--", tx_speed="--",
    rx_total="--", tx_total="--",
    load_avg="--",
    pho_total="--", pho_blocked="--", pho_pct="--",
    pho_gravity="--", pho_clients="--", pho_cached="--",
    pho_status="?", pho_last="--",
    wth_temp="--", wth_feels="--", wth_humidity="--",
    wth_wind="--", wth_desc="--", wth_city="--",
    wth_icon="--",
)
wth_icon_img = None   # PIL RGBA image downloaded from OWM, or None
_prev_net     = {"rx": 0, "tx": 0, "t": 0.0}

# ── rolling history for sparklines ────────────────────────────────────────────
_HIST = 40
cpu_hist  = collections.deque(maxlen=_HIST)   # 0..100
ram_hist  = collections.deque(maxlen=_HIST)   # 0..100
rx_hist   = collections.deque(maxlen=_HIST)   # bytes/s
tx_hist   = collections.deque(maxlen=_HIST)   # bytes/s

# ── LCD ───────────────────────────────────────────────────────────────────────
lcd   = LCD_1in44.LCD()
lcd.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
lcd.LCD_Clear()
_lock = threading.Lock()

# ── app state ─────────────────────────────────────────────────────────────────
page            = 0
bl_pct          = 60
sleeping        = False
last_activity   = time.time()
set_sel:        int           = 0
set_app:        int | None    = None
wifi_on         = _get_rfkill("wlan")
bt_on           = _get_rfkill("bluetooth")
hotspot_on      = _get_hotspot()
pho_password    = ""
weather_api_key = ""
weather_city    = ""
sleep_idx:      int           = 0
power_open      = False
power_sel       = 0
hints_open      = False
game_sel        = 0
game_active     = False
running         = True
auto_dim        = True
high_scores     = {"SNAKE": 0, "PONG": 0, "FLAPPY": 0, "BREAKOUT": 0, "INVADERS": 0}
_fetch_now      = threading.Event()

# ── backlight control (sleep + auto-dim aware) ────────────────────────────────
_last_bl = -1

def is_night():
    h = time.localtime().tm_hour
    if NIGHT_START <= NIGHT_END:          # same-day window
        return NIGHT_START <= h < NIGHT_END
    return h >= NIGHT_START or h < NIGHT_END   # window wraps past midnight

def target_brightness():
    if sleeping:
        return 0
    if auto_dim and is_night():
        return min(bl_pct, NIGHT_CAP)
    return bl_pct

def apply_backlight():
    """Set the LCD backlight to the effective level. Cheap to call often —
    only touches the SPI/PWM when the computed value actually changes."""
    global _last_bl
    t = target_brightness()
    if t != _last_bl:
        _last_bl = t
        with _lock:
            lcd.bl_DutyCycle(t)
