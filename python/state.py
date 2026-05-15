import threading, time, os
import LCD_1in44
from constants import SERVICES, SLEEP_PRESETS

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

# ── shared data dict ──────────────────────────────────────────────────────────
data = dict(
    cpu="--", ram_used="--", ram_cache="--",
    temp="--", disk="--", uptime="...",
    cpu_freq="--",
    wip="...", uip="...", tip="...",
    rssi="--", rx_speed="--", tx_speed="--",
    rx_total="--", tx_total="--",
    last_login="...", updates="--",
    pho_total="--", pho_blocked="--", pho_pct="--",
    pho_gravity="--", pho_clients="--", pho_cached="--",
    pho_status="?", pho_last="--",
    esp_temp="--", esp_humidity="--",
    wth_temp="--", wth_feels="--", wth_humidity="--",
    wth_wind="--", wth_desc="--", wth_city="--",
)
svc_statuses  = {label: False for label, _ in SERVICES}
_prev_net     = {"rx": 0, "tx": 0, "t": 0.0}
esp_connected = False

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
set_sel         = 0
set_app         = None
wifi_on         = _get_rfkill("wlan")
bt_on           = _get_rfkill("bluetooth")
pho_password    = ""
weather_api_key = ""
weather_city    = ""
sleep_idx       = 0
power_open      = False
power_sel       = 0
game_sel        = 0
game_active     = False
running         = True
_fetch_now      = threading.Event()
