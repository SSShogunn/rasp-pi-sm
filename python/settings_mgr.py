import json, os, logging
import state
from constants import SLEEP_PRESETS

log = logging.getLogger(__name__)

_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

def load():
    try:
        with open(_SETTINGS_FILE) as f:
            s = json.load(f)
        state.bl_pct          = max(10, min(100, int(s.get("bl_pct",      60))))
        state.sleep_idx       = max(0,  min(len(SLEEP_PRESETS) - 1,
                                            int(s.get("sleep_idx",        0))))
        state.pho_password    = s.get("pho_password",    "")
        state.weather_api_key = s.get("weather_api_key", "")
        state.weather_city    = s.get("weather_city",    "")
        state.auto_dim        = bool(s.get("auto_dim", True))
        hs = s.get("high_scores", {})
        for k in state.high_scores:
            state.high_scores[k] = int(hs.get(k, 0))
    except FileNotFoundError:
        pass
    except Exception as e:
        log.warning("Failed to load settings: %s", e)

def save():
    try:
        with open(_SETTINGS_FILE, "w") as f:
            json.dump({
                "bl_pct":          state.bl_pct,
                "sleep_idx":       state.sleep_idx,
                "pho_password":    state.pho_password,
                "weather_api_key": state.weather_api_key,
                "weather_city":    state.weather_city,
                "auto_dim":        state.auto_dim,
                "high_scores":     state.high_scores,
            }, f)
    except Exception as e:
        log.warning("Failed to save settings: %s", e)
