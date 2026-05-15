import json, time, urllib.request, logging
import state
from constants import PHO_HOST

log = logging.getLogger(__name__)

_sid   = None
_sid_t = 0.0

def _auth():
    global _sid, _sid_t
    try:
        body = json.dumps({"password": state.pho_password}).encode()
        req  = urllib.request.Request(
            f"{PHO_HOST}/api/auth", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read())
        sid = j.get("session", {}).get("sid")
        if sid:
            _sid = sid; _sid_t = time.time(); return True
    except Exception as e:
        log.warning("Pi-hole auth failed: %s", e)
    _sid = None; return False

def ensure_auth():
    if not state.pho_password:
        return True
    if not _sid or (time.time() - _sid_t) > 1500:
        return _auth()
    return True

def get(path):
    sep = "&" if "?" in path else "?"
    sid_param = f"{sep}sid={_sid}" if _sid else ""
    req = urllib.request.Request(f"{PHO_HOST}{path}{sid_param}")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())

def toggle(render_fn):
    new_on = (state.data["pho_status"] != "enabled")
    try:
        body = json.dumps({"blocking": new_on}).encode()
        sid_param = f"?sid={_sid}" if _sid else ""
        req = urllib.request.Request(
            f"{PHO_HOST}/api/dns/blocking{sid_param}",
            data=body, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5).close()
        state.data["pho_status"] = "enabled" if new_on else "disabled"
    except Exception as e:
        log.warning("Pi-hole toggle failed: %s", e)
    import fetch
    fetch.fetch_pihole()
    render_fn()
