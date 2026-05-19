from PIL import ImageFont

# ── page IDs ──────────────────────────────────────────────────────────────────
PAGES     = 7
PAGE_HOME = 0
PAGE_SYS  = 1
PAGE_NET  = 2
PAGE_SVC  = 3
PAGE_PHO  = 4
PAGE_GAMES= 5
PAGE_SET  = 6

# ── hardware / API ────────────────────────────────────────────────────────────
PHO_HOST      = "http://localhost"
WTH_URL       = "https://api.openweathermap.org/data/2.5/weather"

# ── refresh intervals (seconds) ───────────────────────────────────────────────
REFRESH       = 5
REFRESH_WTH   = 900
REFRESH_SVC   = 30
REFRESH_PHO   = 10

# ── UI config ─────────────────────────────────────────────────────────────────
SLEEP_PRESETS = [10, 20, 30, 60, 120, 300, 0]
SLEEP_LABELS  = ["10s", "20s", "30s", "1m", "2m", "5m", "Off"]
SERVICES      = [("pihole-FTL", "pihole-FTL"),
                 ("Tailscale",  "tailscaled"),
                 ("SSH",        "ssh")]
GAME_LIST     = ["SNAKE", "PONG", "FLAPPY BIRD"]
SET_APPS      = ["Brightness", "Sleep", "WiFi", "Bluetooth"]
W = H         = 128

# ── palette ───────────────────────────────────────────────────────────────────
BG       = ( 16,  16,  28)
HDR_SYS  = (  0,  55,  85)
HDR_NET  = (  0,  62,  30)
HDR_SVC  = ( 52,  25,   0)
HDR_SET  = ( 38,  15,  58)
HDR_PWR  = ( 62,   8,   8)
HDR_GAME = ( 38,  30,   0)
HDR_PHO  = ( 52,   8,  18)
ACC_SYS  = (  0, 210, 255)
ACC_NET  = (  0, 225, 115)
ACC_SVC  = (255, 150,   0)
ACC_SET  = (190,  90, 255)
ACC_PWR  = (255,  70,  70)
ACC_GAME = (255, 228,   0)
ACC_PHO  = (255,  85, 120)
TRACK    = ( 38,  42,  62)
C_CPU    = (  0, 190, 255)
C_RAM    = (145,  85, 255)
C_DISK   = (255, 170,   0)
C_OK     = (  0, 215, 105)
C_WARN   = (255, 190,   0)
C_HOT    = (255,  60,  60)
T_PRI    = (235, 238, 250)
T_SEC    = (148, 158, 185)
T_DIM    = ( 95, 105, 130)
SEP_C    = ( 48,  54,  75)
C_WIFI   = (255, 205,  55)
C_USB    = (  0, 215, 215)
C_TS     = ( 90, 162, 255)
SET_COLS  = [ACC_SET, (55, 100, 220), C_OK, (0, 185, 230)]

# ── fonts ─────────────────────────────────────────────────────────────────────
def _font(name, size):
    for d in ("/usr/share/fonts/truetype/dejavu/",
              "/usr/share/fonts/truetype/ttf-bitstream-vera/"):
        try:
            return ImageFont.truetype(d + name, size)
        except OSError:
            pass
    return ImageFont.load_default()

F_HDR    = _font("DejaVuSans-Bold.ttf",  9)
F_LABEL  = _font("DejaVuSans.ttf",       8)
F_VAL    = _font("DejaVuSans-Bold.ttf",  9)
F_IP     = _font("DejaVuSans.ttf",       9)
F_FOOT   = _font("DejaVuSans.ttf",       8)
F_MED    = _font("DejaVuSans-Bold.ttf", 14)
F_BIG    = _font("DejaVuSans-Bold.ttf", 22)
