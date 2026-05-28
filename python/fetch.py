import time, subprocess, os, json, io, socket, urllib.request, urllib.parse, logging
from PIL import Image as _PILImage
import state, pihole_api
from constants import (REFRESH, REFRESH_WTH, REFRESH_PHO,
                       WTH_URL, PAGE_HOME, PAGE_SYS, PAGE_NET, PAGE_PHO)

log = logging.getLogger(__name__)

# psutil is convenient but adds ~6-8 MB resident. The /proc + os fallbacks
# below cover every metric we need, so default to those. Set DASH_USE_PSUTIL=1
# to opt back into psutil.
_PSUTIL = False
if os.environ.get("DASH_USE_PSUTIL", "0") == "1":
    try:
        import psutil
        _PSUTIL = True
    except ImportError:
        log.warning("DASH_USE_PSUTIL=1 but psutil not installed — using /proc fallback")

# ── helpers ───────────────────────────────────────────────────────────────────
def _run(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL, timeout=8
        ).decode().strip()
    except Exception:
        return ""

def _fmt_rate(bps):
    if bps < 1024:       return f"{int(bps)}B/s"
    if bps < 1024*1024:  return f"{bps/1024:.0f}K/s"
    return f"{bps/1048576:.1f}M/s"

def _fmt_bytes(b):
    if b < 1024:      return f"{b}B"
    if b < 1024**2:   return f"{b/1024:.0f}K"
    if b < 1024**3:   return f"{b/1048576:.1f}M"
    return f"{b/1073741824:.2f}G"

def _fmt_gravity(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n//1000}K"
    return str(n)

# ── system ────────────────────────────────────────────────────────────────────
def fetch_system():
    if _PSUTIL:
        _sys_psutil()
    else:
        _sys_proc()

    # load average (was on the old Services page; Home + System use it now)
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            state.data["load_avg"] = f"{parts[0]} / {parts[1]}"
    except Exception:
        state.data["load_avg"] = "--"

    # push into rolling history for sparklines
    try:    state.cpu_hist.append(int(state.data["cpu"]))
    except (ValueError, TypeError): pass
    try:    state.ram_hist.append(int(state.data["ram_used"]))
    except (ValueError, TypeError): pass

def _sys_psutil():
    try:
        state.data["cpu"] = str(int(psutil.cpu_percent(interval=0.1)))
    except Exception:
        state.data["cpu"] = "--"

    try:
        m = psutil.virtual_memory()
        used_pct  = int(m.percent)
        cache     = getattr(m, "cached", 0) + getattr(m, "buffers", 0)
        cache_pct = min(100 - used_pct, int(cache * 100 / m.total)) if m.total else 0
        state.data["ram_used"]  = str(used_pct)
        state.data["ram_cache"] = str(cache_pct)
    except Exception:
        state.data["ram_used"] = state.data["ram_cache"] = "--"

    try:
        temps = psutil.sensors_temperatures()
        zone  = temps.get("cpu_thermal") or temps.get("cpu-thermal") or []
        if zone:
            state.data["temp"] = f"{zone[0].current:.1f}"
        else:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                state.data["temp"] = f"{int(f.read().strip()) / 1000:.1f}"
    except Exception:
        state.data["temp"] = "--"

    try:
        state.data["disk"] = str(int(psutil.disk_usage("/").percent))
    except Exception:
        state.data["disk"] = "--"

    try:
        secs = int(time.time() - psutil.boot_time())
        d, r = divmod(secs, 86400); h, r = divmod(r, 3600); m = r // 60
        if d:   state.data["uptime"] = f"{d}d {h}h {m}m"
        elif h: state.data["uptime"] = f"{h}h {m}m"
        else:   state.data["uptime"] = f"{m}m"
    except Exception:
        state.data["uptime"] = "N/A"

    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as f:
            state.data["cpu_freq"] = f"{int(f.read().strip()) // 1000}MHz"
    except Exception:
        state.data["cpu_freq"] = "--"

_cpu_snap = None

def _cpu_stat():
    cores = []
    try:
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("cpu") and len(line) > 3 and line[3].isdigit():
                    v = [int(x) for x in line.split()[1:8]]
                    cores.append((v[3] + v[4], sum(v)))
    except Exception:
        pass
    return cores

def _sys_proc():
    global _cpu_snap
    snap2 = _cpu_stat()
    if _cpu_snap and snap2:
        pcts = []
        for (i1, t1), (i2, t2) in zip(_cpu_snap, snap2):
            dt = t2 - t1
            pcts.append(max(0, min(100, int((1 - (i2 - i1) / dt) * 100))) if dt else 0)
        state.data["cpu"] = str(sum(pcts) // max(len(pcts), 1))
    _cpu_snap = _cpu_stat()

    try:
        mi = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mi[k.strip()] = int(v.split()[0])
        total = mi["MemTotal"]; free = mi["MemFree"]
        cache = mi.get("Cached", 0) + mi.get("Buffers", 0) + mi.get("SReclaimable", 0)
        used  = max(0, total - free - cache)
        state.data["ram_used"]  = str(used  * 100 // total)
        state.data["ram_cache"] = str(min(100 - used * 100 // total, cache * 100 // total))
    except Exception:
        state.data["ram_used"] = state.data["ram_cache"] = "--"

    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            state.data["temp"] = f"{int(f.read().strip()) / 1000:.1f}"
    except Exception:
        state.data["temp"] = "--"

    try:
        s = os.statvfs("/")
        state.data["disk"] = str((s.f_blocks - s.f_bfree) * 100 // s.f_blocks)
    except Exception:
        state.data["disk"] = "--"

    try:
        with open("/proc/uptime") as f:
            secs = int(float(f.read().split()[0]))
        d, r = divmod(secs, 86400); h, r = divmod(r, 3600); m = r // 60
        if d:   state.data["uptime"] = f"{d}d {h}h {m}m"
        elif h: state.data["uptime"] = f"{h}h {m}m"
        else:   state.data["uptime"] = f"{m}m"
    except Exception:
        state.data["uptime"] = "N/A"

    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as f:
            state.data["cpu_freq"] = f"{int(f.read().strip()) // 1000}MHz"
    except Exception:
        state.data["cpu_freq"] = "--"

# ── network ───────────────────────────────────────────────────────────────────
def _net_bytes():
    if _PSUTIL:
        try:
            c = psutil.net_io_counters(pernic=True).get("wlan0")
            if c:
                return c.bytes_recv, c.bytes_sent
        except Exception:
            pass
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if "wlan0:" in line:
                    c = line.split(); return int(c[1]), int(c[9])
    except Exception:
        pass
    return 0, 0

def fetch_network():
    if _PSUTIL:
        try:
            addrs = psutil.net_if_addrs()
            def _ipv4(iface):
                for a in addrs.get(iface, []):
                    if a.family == socket.AF_INET:
                        return a.address
                return "N/A"
            state.data["wip"] = _ipv4("wlan0")
            state.data["uip"] = _ipv4("usb0")
        except Exception:
            state.data["wip"] = state.data["uip"] = "N/A"
    else:
        state.data["wip"] = (_run("ip -4 addr show wlan0 2>/dev/null | grep inet | awk '{print $2}' | cut -d'/' -f1") or "N/A")
        state.data["uip"] = (_run("ip -4 addr show usb0  2>/dev/null | grep inet | awk '{print $2}' | cut -d'/' -f1") or "N/A")

    state.data["tip"]  = _run("tailscale ip -4 2>/dev/null") or "N/A"
    state.data["ssid"] = _run("iwgetid -r 2>/dev/null") or "--"

    try:
        with open("/proc/net/wireless") as f:
            for line in f:
                if "wlan0:" in line:
                    v = int(line.split()[3].rstrip("."))
                    state.data["rssi"] = str(v - 256 if v > 0 else v)
                    break
    except Exception:
        state.data["rssi"] = "--"

    rx, tx = _net_bytes()
    now = time.time()
    dt  = now - state._prev_net["t"]
    if state._prev_net["t"] > 0 and dt > 0:
        rx_rate = (rx - state._prev_net["rx"]) / dt
        tx_rate = (tx - state._prev_net["tx"]) / dt
        state.data["rx_speed"] = _fmt_rate(rx_rate)
        state.data["tx_speed"] = _fmt_rate(tx_rate)
        state.rx_hist.append(max(0.0, rx_rate))
        state.tx_hist.append(max(0.0, tx_rate))
    state.data["rx_total"] = _fmt_bytes(rx)
    state.data["tx_total"] = _fmt_bytes(tx)
    state._prev_net.update({"rx": rx, "tx": tx, "t": now})

# ── weather ───────────────────────────────────────────────────────────────────
_icon_cache: str | None = None   # last downloaded icon code

def fetch_weather():
    if not state.weather_api_key or not state.weather_city:
        return
    try:
        city_enc = urllib.parse.quote(state.weather_city)
        url = f"{WTH_URL}?q={city_enc}&appid={state.weather_api_key}&units=metric"
        with urllib.request.urlopen(url, timeout=10) as r:
            j = json.loads(r.read())
        m = j["main"]
        state.data["wth_temp"]     = f"{m['temp']:.1f}"
        state.data["wth_feels"]    = f"{m['feels_like']:.1f}"
        state.data["wth_humidity"] = str(m["humidity"])
        state.data["wth_wind"]     = f"{j['wind']['speed']:.1f}"
        state.data["wth_desc"]     = j["weather"][0]["description"].title()
        state.data["wth_city"]     = j["name"]
        state.data["wth_icon"]     = j["weather"][0]["icon"]
    except Exception as e:
        log.warning("Weather fetch failed: %s", e)
        return

    _fetch_weather_icon(state.data["wth_icon"])

def _fetch_weather_icon(icon_code: str):
    global _icon_cache
    if icon_code == _icon_cache:
        return
    try:
        url = f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
        with urllib.request.urlopen(url, timeout=8) as r:
            raw = r.read()
        img = _PILImage.open(io.BytesIO(raw)).convert("RGBA")
        try:
            resample = _PILImage.Resampling.LANCZOS
        except AttributeError:
            resample = _PILImage.LANCZOS
        state.wth_icon_img = img.resize((26, 26), resample)
        _icon_cache = icon_code
        log.info("Weather icon %s fetched", icon_code)
    except Exception as e:
        log.warning("Weather icon fetch failed: %s", e)

# ── pi-hole ───────────────────────────────────────────────────────────────────
def fetch_pihole():
    if not pihole_api.ensure_auth():
        state.data["pho_status"] = "auth err"; return
    try:
        s = pihole_api.get("/api/stats/summary")
        q = s.get("queries", {})
        g = s.get("gravity", {})
        c = s.get("clients", {})
        state.data["pho_total"]   = f"{q.get('total',   0):,}"
        state.data["pho_blocked"] = f"{q.get('blocked', 0):,}"
        state.data["pho_pct"]     = f"{q.get('percent_blocked', 0.0):.1f}"
        state.data["pho_cached"]  = f"{q.get('cached',  0):,}"
        state.data["pho_clients"] = str(c.get("active", "--"))
        state.data["pho_gravity"] = _fmt_gravity(g.get("domains_being_blocked", 0))
    except Exception as e:
        log.warning("Pi-hole stats failed: %s", e)
        state.data["pho_status"] = "error"; return
    try:
        b = pihole_api.get("/api/dns/blocking")
        state.data["pho_status"] = b.get("blocking", "?")
    except Exception:
        state.data["pho_status"] = "?"
    try:
        r = pihole_api.get("/api/stats/recent_blocked?count=1")
        doms = r.get("blocked", [])
        state.data["pho_last"] = doms[0] if doms else "--"
    except Exception:
        state.data["pho_last"] = "--"

# ── background fetch thread ───────────────────────────────────────────────────
#   index:        0              1            2             3
_FNS = [fetch_weather, fetch_system, fetch_network, fetch_pihole]
_IVS = [REFRESH_WTH,   REFRESH,      REFRESH,       REFRESH_PHO]
_PAGE_FETCH_MAP = {
    PAGE_HOME: 0,   # fetch_weather
    PAGE_SYS:  1,   # fetch_system
    PAGE_NET:  2,   # fetch_network
    PAGE_PHO:  3,   # fetch_pihole
}

def run_bg(render_fn):
    last       = [0.0] * len(_FNS)
    last_clock = 0.0

    while state.running:
        now = time.time()
        cur = state.page

        if not state.game_active:
            fetched_for_page = False
            for i, (fn, iv) in enumerate(zip(_FNS, _IVS)):
                if now - last[i] >= iv:
                    fn(); last[i] = time.time()
                    if _PAGE_FETCH_MAP.get(cur) == i:
                        fetched_for_page = True
            if fetched_for_page and not state.sleeping and not state.power_open:
                render_fn()
            if cur == PAGE_HOME and not state.sleeping and (now - last_clock) >= 30:
                last_clock = now
                render_fn()

        state._fetch_now.wait(timeout=1.0)
        if state._fetch_now.is_set():
            state._fetch_now.clear()
            if not state.game_active:
                idx = _PAGE_FETCH_MAP.get(state.page)
                if idx is not None:
                    _FNS[idx](); last[idx] = time.time()
                if not state.sleeping and not state.power_open:
                    render_fn()
