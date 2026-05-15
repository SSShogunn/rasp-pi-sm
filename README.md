# Pi Zero 2W LCD Dashboard

A sleek, dark-themed system dashboard for the **Raspberry Pi Zero 2W** with the **Waveshare 1.44" LCD HAT** (128×128px, ST7735S). Built entirely in Python — no frameworks, no bloat.

---

## Features

| Page | What it shows |
|---|---|
| **Home** | Live clock, date, weather (OpenWeatherMap), ESP32 room sensor summary |
| **System** | CPU %, RAM bar, Disk %, Temperature, CPU freq, total network I/O |
| **Network** | WiFi/USB/Tailscale IPs, signal strength, live RX/TX speed |
| **Services** | pihole-FTL, Tailscale, SSH status · last login · pending updates |
| **Pi-hole** | Blocked queries, % blocked, gravity list size, last blocked domain, toggle |
| **Sensor** | ESP32-DHT11 room temperature & humidity via BLE (live) |
| **Games** | Snake · Pong · Flappy Bird |
| **Settings** | Brightness, sleep timer, WiFi toggle, Bluetooth toggle |

**Power menu** (KEY1): Reboot / Power Off with confirmation.

---

## Hardware

| Component | Details |
|---|---|
| SBC | Raspberry Pi Zero 2W |
| Display | Waveshare 1.44" LCD HAT — 128×128px, SPI, ST7735S |
| Sensor | ESP32 + DHT11 module (BLE, GATT notify) |
| OS | Raspberry Pi OS Lite (64-bit) |

### Controls

```
Joystick Left / Right  →  Navigate pages
Joystick Up / Down     →  Menu navigation / game controls
Joystick Press         →  Confirm / toggle
KEY1                   →  Power menu (reboot / shutdown)
KEY2                   →  Settings hub (back from sub-screens)
KEY3                   →  Force refresh current page
```

---

## Software Stack

- **Python 3** — no web frameworks
- **Pillow** — all LCD rendering (PIL draw primitives)
- **psutil** — system metrics (CPU, RAM, disk, network)
- **bleak** — BLE client for ESP32 sensor
- **gpiozero** — GPIO button polling
- **spidev / numpy** — SPI display driver

---

## Installation

### 1. System dependencies

```bash
sudo apt update
sudo apt install python3-pil python3-numpy python3-gpiozero python3-spidev
```

### 2. Python packages

```bash
sudo pip3 install bleak psutil --break-system-packages
```

### 3. Clone and configure

```bash
git clone https://github.com/SSShogunn/rasp-pi-sm.git
cd rasp-pi-sm/python
```

Create `settings.json` (gitignored):

```json
{
  "bl_pct": 60,
  "sleep_idx": 2,
  "pho_password": "your-pihole-app-password",
  "weather_api_key": "your-openweathermap-key",
  "weather_city": "Pune, IN"
}
```

### 4. Run manually

```bash
cd python
sudo python3 monitor.py
```

### 5. Install as a systemd service (auto-start on boot)

```bash
bash python/install-service.sh
```

---

## Project Structure

```
python/
  monitor.py          ← entry point (~65 lines)
  constants.py        ← page IDs, colors, fonts, config
  state.py            ← shared mutable state + LCD init
  settings_mgr.py     ← load / save settings.json
  fetch.py            ← system / network / weather / Pi-hole fetchers + bg thread
  pihole_api.py       ← Pi-hole v6 REST API (session auth)
  ble.py              ← BLE client thread (ESP32-DHT11)
  draw.py             ← all page draw functions + render()
  games.py            ← Snake, Pong, Flappy Bird
  input_handler.py    ← button polling + all action handlers
  config.py           ← hardware GPIO pin map (Waveshare HAT)

sample-files/
  RaspberryPi/python/ ← original Waveshare SDK Python samples (reference)
```

---

## ESP32 Sensor

The room sensor runs on an **ESP32 with a DHT11** wired in. It advertises over BLE and notifies temperature + humidity every 2 seconds in the format `"temp,humidity"` (e.g. `"28.5,62.1"`).

The dashboard auto-reconnects every 5 seconds if the connection drops. BLE status is shown live on both the Home and Sensor pages.

---

## Pi-hole Integration

Requires **Pi-hole v6** with the REST API enabled. Uses **app password authentication** (2FA compatible) — the session ID is passed as a query parameter (`?sid=...`). Supports:

- Live query stats (total, blocked, cached, clients, gravity size)
- Last blocked domain
- Enable / disable blocking toggle (joystick press on the Pi-hole page)

---

## API Keys

| Service | Where to get it |
|---|---|
| Weather | [openweathermap.org](https://openweathermap.org/api) — free tier |
| Pi-hole | Admin panel → Settings → API → App Password |

Store both in `python/settings.json` (never committed — in `.gitignore`).

---

## License

MIT
