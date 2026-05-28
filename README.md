# Pi Zero 2W LCD Dashboard

A sleek, dark-themed system dashboard for the **Raspberry Pi Zero 2W** with the **Waveshare 1.44" LCD HAT** (128×128px, ST7735S). Built entirely in Python — no frameworks, no bloat.

---

## Features

| Page | What it shows |
|---|---|
| **Home** | Live clock, date, weather + condition icon (OpenWeatherMap), uptime, load avg |
| **System** | CPU % + history graph, RAM % + history graph, Disk %, Temperature, CPU freq |
| **Network** | SSID, signal bars, WiFi/USB/Tailscale IPs, live RX/TX speed graphs |
| **Pi-hole** | Blocked queries, % blocked, gravity list size, last blocked domain |
| **Games** | Snake · Pong · Flappy · Breakout · Space Invaders (with high scores) |
| **Settings** | Brightness, sleep timer, WiFi, Bluetooth, Hotspot, Auto-Dim toggles (scrollable) |

**Power menu** (KEY1): Reboot / Power Off with confirmation.

---

## Hardware

| Component | Details |
|---|---|
| SBC | Raspberry Pi Zero 2W |
| Display | Waveshare 1.44" LCD HAT — 128×128px, SPI, ST7735S |
| OS | Raspberry Pi OS Lite (64-bit) |

### Controls

```
Joystick Left / Right  →  Navigate pages
Joystick Up / Down     →  Menu navigation / game controls
Joystick Press         →  Confirm / toggle
KEY1                   →  Power menu (reboot / shutdown)
KEY2                   →  Home (return to home page from anywhere)
KEY3                   →  Back (dismiss menus / return to previous level)
```

Press **Down on the Home page** to open the Controls overlay with the full key reference.

> **Note:** WiFi and Hotspot are mutually exclusive — enabling one automatically disables the other.

---

## Software Stack

- **Python 3** — no web frameworks
- **Pillow** — all LCD rendering (PIL draw primitives)
- **psutil** — system metrics (CPU, RAM, disk, network)
- **gpiozero** — GPIO button polling
- **spidev / numpy** — SPI display driver

Dependencies are declared in `pyproject.toml` and installed into a virtualenv by the service installer.

---

## Installation

### 1. System dependencies

```bash
sudo apt update
sudo apt install python3-venv git
```

### 2. Clone

```bash
git clone https://github.com/SSShogunn/rasp-pi-sm.git
cd rasp-pi-sm
```

### 3. Configure

Create `python/settings.json` (gitignored):

```json
{
  "bl_pct": 60,
  "sleep_idx": 2,
  "pho_password": "your-pihole-app-password",
  "weather_api_key": "your-openweathermap-key",
  "weather_city": "Pune, IN"
}
```

### 4. Install as a systemd service (auto-start on boot)

```bash
sudo bash install-service.sh
```

The script creates a `.venv` at the project root, installs all dependencies from `pyproject.toml`, writes the systemd unit, and enables it. No `--break-system-packages` needed.

### 5. Run manually (optional)

The service installer must be run first (step 4) to create the virtualenv. After that you can run the dashboard directly using the venv Python:

```bash
sudo .venv/bin/python3 python/monitor.py
```

Useful service commands:

```bash
sudo systemctl status pi-dashboard
sudo systemctl restart pi-dashboard
sudo journalctl -u pi-dashboard -f
```

---

## Project Structure

```
rasp-pi-sm/
  install-service.sh    <- systemd service installer (creates venv + enables service)
  pyproject.toml        <- project metadata and Python dependencies
  python/
    monitor.py          <- entry point
    constants.py        <- page IDs, colors, fonts, config
    state.py            <- shared mutable state + LCD init
    settings_mgr.py     <- load / save settings.json
    fetch.py            <- system / network / weather / Pi-hole fetchers + bg thread
    pihole_api.py       <- Pi-hole v6 REST API (session auth)
    draw.py             <- all page draw functions + render()
    games.py            <- Snake, Pong, Flappy, Breakout, Space Invaders
    input_handler.py    <- button polling + all action handlers
    splash.py           <- boot splash screen
    config.py           <- hardware GPIO pin map (Waveshare HAT)
    lcd_off.py          <- blanks screen on boot delay / service stop
    LCD_1in44.py        <- ST7735S display driver
```

---

## Pi-hole Integration

Requires **Pi-hole v6** with the REST API enabled. Uses **app password authentication** — the session ID is passed as a query parameter (`?sid=...`). Supports:

- Live query stats (total, blocked, cached, clients, gravity size)
- Last blocked domain
- Enable / disable blocking toggle (joystick press on the Pi-hole page)

---

## API Keys

| Service | Where to get it |
|---|---|
| Weather | [openweathermap.org](https://openweathermap.org/api) — free tier |
| Pi-hole | Admin panel -> Settings -> API -> App Password |

Store both in `python/settings.json` (never committed — in `.gitignore`).

---

## License

MIT
