import asyncio, logging
import state
from constants import ESP_ADDRESS, ESP_CHAR_UUID, PAGE_HOME, PAGE_ESP

log = logging.getLogger(__name__)

try:
    from bleak import BleakClient as _BleakClient
    _BLEAK_OK = True
except ImportError:
    _BLEAK_OK = False
    log.warning("bleak not installed — BLE disabled. Run: sudo pip3 install bleak --break-system-packages")

_render_fn = None

def set_render(fn):
    global _render_fn
    _render_fn = fn

def _notify(sender, raw):
    try:
        parts = raw.decode().strip().split(",")
        state.data["esp_temp"]     = parts[0]
        state.data["esp_humidity"] = parts[1]
        state.esp_connected = True
        if state.page in (PAGE_HOME, PAGE_ESP) and not state.sleeping and not state.power_open:
            if _render_fn:
                _render_fn()
    except Exception as e:
        log.debug("BLE notify parse error: %s", e)

async def _run():
    while state.running:
        try:
            state.esp_connected = False
            async with _BleakClient(ESP_ADDRESS, timeout=15.0) as client:
                state.esp_connected = True
                if state.page in (PAGE_HOME, PAGE_ESP) and _render_fn:
                    _render_fn()
                await client.start_notify(ESP_CHAR_UUID, _notify)
                while state.running and client.is_connected:
                    await asyncio.sleep(0.5)
        except Exception as e:
            log.debug("BLE connection error: %s", e)
        state.esp_connected = False
        if state.page in (PAGE_HOME, PAGE_ESP) and _render_fn:
            _render_fn()
        if state.running:
            await asyncio.sleep(5)

def thread_fn():
    if not _BLEAK_OK:
        return
    asyncio.run(_run())
