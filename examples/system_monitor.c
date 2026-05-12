/*
 * system_monitor.c  –  Interactive 5-page dashboard for Pi Zero 2W
 * Display : Waveshare 1.44" LCD HAT  128×128  ST7735S (SPI)
 *
 * IMPORTANT – before running, add pull-ups to /boot/config.txt:
 *   echo "gpio=6,19,5,26,13,21,20,16=pu" | sudo tee -a /boot/config.txt
 *   sudo reboot
 *
 * Controls : Up/Down joystick  → navigate pages
 *            KEY1 (GPIO 21)    → toggle Pi-hole blocking
 *            KEY2 (GPIO 20)    → force refresh
 *            KEY3 (GPIO 16)    → cycle brightness
 *
 * NOTE – Paint_DrawString_EN colour convention (Waveshare library quirk):
 *   arg5 = background / non-text colour
 *   arg6 = foreground / text colour
 *   e.g. WHITE text on BLACK bg → Paint_DrawString_EN(x,y,s,font, BLACK, WHITE)
 *
 * Build : make clean && make
 * Run   : sudo ./system_monitor
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include "DEV_Config.h"
#include "GUI_Paint.h"
#include "LCD_1in44.h"

/* ═══════════════════════════════════════════════════════════════════════
   Configuration
   ═══════════════════════════════════════════════════════════════════════ */
#define TOTAL_PAGES   5
#define REFRESH_SECS  3       /* seconds between auto-refresh              */
#define DEBOUNCE_MS   100     /* key debounce window in ms                 */
#define DIM_SECS      45      /* dim backlight after this many seconds idle */
#define SLEEP_SECS    60      /* blank display after this many seconds idle */
#define PIHOLE_HOST   "http://localhost"
#define PIHOLE_PASS   "I7IUjMRb"
#define MAX_TOP       5
#define SID_LEN       128
#define RSP_SZ        8192
#define CMD_SZ        640

#define W  LCD_WIDTH   /* 128 */
#define H  LCD_HEIGHT  /* 128 */

/* ═══════════════════════════════════════════════════════════════════════
   Global state
   ═══════════════════════════════════════════════════════════════════════ */
static UWORD *g_img    = NULL;
static int    g_page   = 0;
static int    g_bl_idx = 1;
static volatile int g_run = 1;

static const int BL_VALS[3] = { 200, 600, 1024 }; /* lgpio PWM: 0-1024 = 0-100% duty */

/* Pi-hole ─────────────────────────────────────────────────────────────── */
static char  g_sid[SID_LEN] = {0};
static int   g_ph_blocking  = 1;
static long  g_ph_total     = -1;
static long  g_ph_blocked   = -1;
static float g_ph_pct       = 0.0f;
static long  g_ph_list      = 0;
static int   g_ph_clients   = 0;

static char g_dom[MAX_TOP][64];
static long g_dom_cnt[MAX_TOP];
static int  g_dom_n = 0;

static char g_cli[MAX_TOP][64];
static long g_cli_cnt[MAX_TOP];
static int  g_cli_n = 0;

/* Sleep / activity tracking ──────────────────────────────────────────── */
static int    g_sleeping      = 0;
static int    g_dimmed        = 0;
static time_t g_last_activity = 0;
static int    g_need_fetch    = 0;  /* set by handle_input, cleared after fetch */

/* Debounce ────────────────────────────────────────────────────────────── */
#define NK 8
static long g_key_ms[NK] = {0};
enum { K_UP=0, K_DOWN, K_LEFT, K_RIGHT, K_PRESS, K_B1, K_B2, K_B3 };

/* ═══════════════════════════════════════════════════════════════════════
   Utility
   ═══════════════════════════════════════════════════════════════════════ */
static long millis(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}

static void run_cmd(const char *cmd, char *out, size_t out_sz)
{
    out[0] = 0;
    FILE *fp = popen(cmd, "r");
    if (!fp) return;
    size_t pos = 0;
    int c;
    while (pos < out_sz - 1 && (c = fgetc(fp)) != EOF)
        out[pos++] = (char)c;
    out[pos] = 0;
    pclose(fp);
}

/* ── Minimal JSON helpers ─────────────────────────────────────────────── */
static const char *jval(const char *p, const char *key)
{
    char needle[80];
    snprintf(needle, sizeof(needle), "\"%s\":", key);
    p = strstr(p, needle);
    if (!p) return NULL;
    p += strlen(needle);
    while (*p == ' ' || *p == '\t') p++;
    return p;
}

static long jlong(const char *json, const char *parent, const char *key)
{
    const char *p = jval(json, parent);
    if (!p || *p != '{') return 0;
    p = jval(p, key);
    if (!p) return 0;
    return strtol(p, NULL, 10);
}

static float jfloat(const char *json, const char *parent, const char *key)
{
    const char *p = jval(json, parent);
    if (!p || *p != '{') return 0.0f;
    p = jval(p, key);
    if (!p) return 0.0f;
    return strtof(p, NULL);
}

static void jstr(const char *json, const char *key, char *out, int out_len)
{
    out[0] = 0;
    const char *p = jval(json, key);
    if (!p || *p != '"') return;
    p++;
    const char *end = strchr(p, '"');
    if (!end) return;
    int n = (int)(end - p);
    if (n >= out_len) n = out_len - 1;
    memcpy(out, p, (size_t)n);
    out[n] = 0;
}

static int jbool(const char *json, const char *key)
{
    const char *p = jval(json, key);
    if (!p) return 0;
    return (strncmp(p, "true", 4) == 0) ? 1 : 0;
}

/* ═══════════════════════════════════════════════════════════════════════
   System stats
   ═══════════════════════════════════════════════════════════════════════ */
static void get_cpu(char *b, int n)
{
    run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1", b, (size_t)n);
    b[strcspn(b, "\n")] = 0;
    if (!b[0]) strcpy(b, "0");
}

static void get_ram(char *b, int n)
{
    run_cmd("free | grep Mem | awk '{printf \"%.0f\", $3/$2*100}'", b, (size_t)n);
    b[strcspn(b, "\n")] = 0;
    if (!b[0]) strcpy(b, "0");
}

static void get_temp(char *b, int n)
{
    run_cmd("vcgencmd measure_temp | cut -d'=' -f2 | tr -d \"'C\"", b, (size_t)n);
    b[strcspn(b, "\n")] = 0;
    if (!b[0]) strcpy(b, "0");
}

static void get_uptime(char *b, int n)
{
    run_cmd("uptime -p | sed 's/up //'", b, (size_t)n);
    b[strcspn(b, "\n")] = 0;
    if (!b[0]) strcpy(b, "N/A");
    if ((int)strlen(b) > 18) b[18] = 0;
}

static void get_ip(const char *iface, char *b, int n)
{
    char cmd[128];
    snprintf(cmd, sizeof(cmd),
        "ip -4 addr show %s 2>/dev/null | grep inet | awk '{print $2}' | cut -d'/' -f1",
        iface);
    run_cmd(cmd, b, (size_t)n);
    b[strcspn(b, "\n")] = 0;
    if (!b[0]) strcpy(b, "N/A");
}

static void get_ts_ip(char *b, int n)
{
    run_cmd("tailscale ip -4 2>/dev/null", b, (size_t)n);
    b[strcspn(b, "\n")] = 0;
    if (!b[0]) strcpy(b, "N/A");
}

static void get_disk(char *b, int n)
{
    run_cmd("df / | tail -1 | awk '{print $5}' | tr -d '%'", b, (size_t)n);
    b[strcspn(b, "\n")] = 0;
    if (!b[0]) strcpy(b, "0");
}

/* ═══════════════════════════════════════════════════════════════════════
   Pi-hole v6 API
   ═══════════════════════════════════════════════════════════════════════ */
static void curl_cmd(char *buf, size_t sz, const char *method,
                     const char *path, const char *extra)
{
    if (g_sid[0])
        snprintf(buf, sz, "curl -sm5 -X %s %s%s -H 'sid: %s' %s 2>/dev/null",
                 method, PIHOLE_HOST, path, g_sid, extra ? extra : "");
    else
        snprintf(buf, sz, "curl -sm5 -X %s %s%s %s 2>/dev/null",
                 method, PIHOLE_HOST, path, extra ? extra : "");
}

static void ph_auth(void)
{
    char cmd[CMD_SZ], rsp[512] = {0};
    snprintf(cmd, sizeof(cmd),
        "curl -sm5 -X POST %s/api/auth "
        "-H 'Content-Type: application/json' "
        "-d '{\"password\":\"%s\"}' 2>/dev/null",
        PIHOLE_HOST, PIHOLE_PASS);
    run_cmd(cmd, rsp, sizeof(rsp));
    const char *p = jval(rsp, "session");
    if (p && *p == '{')
        jstr(p, "sid", g_sid, SID_LEN);
}

static void ph_fetch_summary(void)
{
    char cmd[CMD_SZ], rsp[RSP_SZ];
    curl_cmd(cmd, sizeof(cmd), "GET", "/api/stats/summary", NULL);
    run_cmd(cmd, rsp, sizeof(rsp));
    if (!strstr(rsp, "\"queries\"")) {
        ph_auth();
        curl_cmd(cmd, sizeof(cmd), "GET", "/api/stats/summary", NULL);
        run_cmd(cmd, rsp, sizeof(rsp));
    }
    if (!strstr(rsp, "\"queries\"")) return;
    g_ph_total    = jlong(rsp,  "queries", "total");
    g_ph_blocked  = jlong(rsp,  "queries", "blocked");
    g_ph_pct      = jfloat(rsp, "queries", "percent_blocked");
    g_ph_list     = jlong(rsp,  "gravity", "domains_being_blocked");
    g_ph_clients  = (int)jlong(rsp, "clients", "active");
}

static void ph_fetch_blocking(void)
{
    char cmd[CMD_SZ], rsp[512];
    curl_cmd(cmd, sizeof(cmd), "GET", "/api/dns/blocking", NULL);
    run_cmd(cmd, rsp, sizeof(rsp));
    if (strstr(rsp, "\"blocking\""))
        g_ph_blocking = jbool(rsp, "blocking");
}

static void ph_toggle(void)
{
    char cmd[CMD_SZ];
    g_ph_blocking = !g_ph_blocking;
    char body[96];
    snprintf(body, sizeof(body),
        "-H 'Content-Type: application/json' -d '{\"blocking\":%s,\"timer\":null}'",
        g_ph_blocking ? "true" : "false");
    curl_cmd(cmd, sizeof(cmd), "POST", "/api/dns/blocking", body);
    strncat(cmd, " >/dev/null", sizeof(cmd) - strlen(cmd) - 1);
    system(cmd);
}

static void ph_fetch_top_domains(void)
{
    char cmd[CMD_SZ], rsp[RSP_SZ];
    curl_cmd(cmd, sizeof(cmd), "GET",
             "/api/stats/database/top_domains?blocked=true&count=5", NULL);
    run_cmd(cmd, rsp, sizeof(rsp));
    g_dom_n = 0;
    const char *p = rsp;
    for (int i = 0; i < MAX_TOP; i++) {
        p = strstr(p, "\"domain\":\"");
        if (!p) break;
        p += 10;
        const char *end = strchr(p, '"');
        if (!end) break;
        int len = (int)(end - p);
        if (len >= 64) len = 63;
        memcpy(g_dom[i], p, (size_t)len);
        g_dom[i][len] = 0;
        const char *cnt = strstr(end, "\"count\":");
        const char *nxt = strstr(end + 1, "\"domain\":");
        if (cnt && (!nxt || cnt < nxt)) {
            cnt += 8;
            while (*cnt == ' ') cnt++;
            g_dom_cnt[i] = strtol(cnt, NULL, 10);
        } else {
            g_dom_cnt[i] = 0;
        }
        g_dom_n++;
        p = end + 1;
    }
}

static void ph_fetch_top_clients(void)
{
    char cmd[CMD_SZ], rsp[RSP_SZ];
    curl_cmd(cmd, sizeof(cmd), "GET",
             "/api/stats/database/top_clients?count=5", NULL);
    run_cmd(cmd, rsp, sizeof(rsp));
    g_cli_n = 0;
    const char *p = rsp;
    for (int i = 0; i < MAX_TOP; i++) {
        p = strstr(p, "\"ip\":\"");
        if (!p) break;
        p += 6;
        const char *end = strchr(p, '"');
        if (!end) break;
        int len = (int)(end - p);
        if (len >= 64) len = 63;
        memcpy(g_cli[i], p, (size_t)len);
        g_cli[i][len] = 0;
        const char *cnt = strstr(end, "\"count\":");
        const char *nxt = strstr(end + 1, "\"ip\":");
        if (cnt && (!nxt || cnt < nxt)) {
            cnt += 8;
            while (*cnt == ' ') cnt++;
            g_cli_cnt[i] = strtol(cnt, NULL, 10);
        } else {
            g_cli_cnt[i] = 0;
        }
        g_cli_n++;
        p = end + 1;
    }
}

static void fetch_pihole(void)
{
    ph_fetch_summary();
    ph_fetch_blocking();
    if (g_page == 3) ph_fetch_top_domains();
    if (g_page == 4) ph_fetch_top_clients();
}

/* ═══════════════════════════════════════════════════════════════════════
   Drawing helpers
   Canvas: 128×128, ROTATE_0, BLACK background
   Paint_DrawString_EN(x,y,s,font, BG_COLOR, TEXT_COLOR)  ← library quirk
   ═══════════════════════════════════════════════════════════════════════ */
#define HDR_H   15   /* header bar height in pixels */
#define FTR_Y  119   /* footer Y start              */

/* Draw centred text with Font8 (5 px/char ≈ 6 px advance) */
static void draw_hdr_text(int y, const char *s, UWORD hdr_color)
{
    int tw = (int)strlen(s) * 6;
    int x  = (W - tw) / 2;
    if (x < 2) x = 2;
    /* hdr_color = non-text bg (matches filled rect), BLACK = text */
    Paint_DrawString_EN(x, y, s, &Font8, hdr_color, BLACK);
}

static void draw_header(const char *title, UWORD color)
{
    Paint_DrawRectangle(0, 0, W - 1, HDR_H, color, DOT_PIXEL_1X1, DRAW_FILL_FULL);
    draw_hdr_text(3, title, color);
}

static void draw_bar(int x, int y, int w, int h,
                     int val, int maxv, UWORD col)
{
    Paint_DrawRectangle(x, y, x + w, y + h, WHITE, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);
    if (val > 0 && maxv > 0) {
        int bw = (val * (w - 2)) / maxv;
        if (bw > w - 2) bw = w - 2;
        if (bw > 0)
            Paint_DrawRectangle(x + 1, y + 1, x + 1 + bw, y + h - 1,
                                col, DOT_PIXEL_1X1, DRAW_FILL_FULL);
    }
}

static void draw_footer(void)
{
    /* left: HH:MM */
    time_t t = time(NULL);
    struct tm *tm_info = localtime(&t);
    char tbuf[8];
    snprintf(tbuf, sizeof(tbuf), "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
    Paint_DrawString_EN(2, FTR_Y, tbuf, &Font8, BLACK, GRAY);

    /* right: page n/N */
    char buf[8];
    snprintf(buf, sizeof(buf), "%d/%d", (int)(g_page + 1), (int)TOTAL_PAGES);
    int x = W - (int)strlen(buf) * 6 - 2;
    Paint_DrawString_EN(x, FTR_Y, buf, &Font8, BLACK, GRAY);
}

static void trunc_str(const char *src, char *dst, int max_chars)
{
    strncpy(dst, src, (size_t)max_chars);
    dst[max_chars] = 0;
}

/* ═══════════════════════════════════════════════════════════════════════
   Page 1 – System Stats
   ═══════════════════════════════════════════════════════════════════════ */
static void draw_page_system(void)
{
    char cpu[16], ram[16], temp[16], disk[16], up[24], line[48];
    get_cpu(cpu, sizeof(cpu));
    get_ram(ram, sizeof(ram));
    get_temp(temp, sizeof(temp));
    get_disk(disk, sizeof(disk));
    get_uptime(up, sizeof(up));

    draw_header("SYSTEM STATS", CYAN);
    int y = HDR_H + 3;  /* 18 */

    snprintf(line, sizeof(line), "CPU  %s%%", cpu);
    Paint_DrawString_EN(4, y, line, &Font12, BLACK, WHITE);
    y += 12;
    draw_bar(4, y, 120, 6, atoi(cpu), 100, GREEN);
    y += 10;

    snprintf(line, sizeof(line), "RAM  %s%%", ram);
    Paint_DrawString_EN(4, y, line, &Font12, BLACK, WHITE);
    y += 12;
    draw_bar(4, y, 120, 6, atoi(ram), 100, BLUE);
    y += 10;

    snprintf(line, sizeof(line), "Disk %s%%", disk);
    Paint_DrawString_EN(4, y, line, &Font12, BLACK, WHITE);
    y += 12;
    draw_bar(4, y, 120, 6, atoi(disk), 100, YELLOW);
    y += 10;

    int t_val = (int)(atof(temp));
    UWORD t_col = (t_val >= 70) ? RED : (t_val >= 55 ? YELLOW : GREEN);
    snprintf(line, sizeof(line), "Temp %s C", temp);
    Paint_DrawString_EN(4, y, line, &Font12, BLACK, t_col);
    y += 12;

    snprintf(line, sizeof(line), "Up: %s", up);
    Paint_DrawString_EN(4, y, line, &Font8, BLACK, GRAY);

    draw_footer();
}

/* ═══════════════════════════════════════════════════════════════════════
   Page 2 – Network Info
   ═══════════════════════════════════════════════════════════════════════ */
static void draw_page_network(void)
{
    char wip[32], uip[32], tip[32];
    get_ip("wlan0", wip, sizeof(wip));
    get_ip("usb0",  uip, sizeof(uip));
    get_ts_ip(tip,  sizeof(tip));

    draw_header("NETWORK", GREEN);
    int y = HDR_H + 5;

    Paint_DrawString_EN(4, y, "WiFi IP", &Font8, BLACK, GRAY);   y += 10;
    Paint_DrawString_EN(4, y, wip, &Font12, BLACK, YELLOW);       y += 16;

    Paint_DrawString_EN(4, y, "USB IP", &Font8, BLACK, GRAY);    y += 10;
    Paint_DrawString_EN(4, y, uip, &Font12, BLACK, CYAN);         y += 16;

    Paint_DrawString_EN(4, y, "Tailscale", &Font8, BLACK, GRAY);  y += 10;
    Paint_DrawString_EN(4, y, tip, &Font12, BLACK, GBLUE);

    draw_footer();
}

/* ═══════════════════════════════════════════════════════════════════════
   Page 3 – Pi-hole Summary
   ═══════════════════════════════════════════════════════════════════════ */
static void draw_page_pihole(void)
{
    char line[48];
    draw_header("PI-HOLE", RED);
    int y = HDR_H + 4;

    const char *state_str = g_ph_blocking ? "ENABLED " : "DISABLED";
    UWORD state_col = g_ph_blocking ? GREEN : RED;
    snprintf(line, sizeof(line), "Block: %s", state_str);
    Paint_DrawString_EN(4, y, line, &Font12, BLACK, state_col);
    y += 16;

    if (g_ph_total < 0) {
        Paint_DrawString_EN(4, y, "Fetching...", &Font12, BLACK, GRAY);
        draw_footer();
        return;
    }

    snprintf(line, sizeof(line), "Total: %ld", g_ph_total);
    Paint_DrawString_EN(4, y, line, &Font12, BLACK, WHITE);
    y += 14;

    snprintf(line, sizeof(line), "Block: %ld", g_ph_blocked);
    Paint_DrawString_EN(4, y, line, &Font12, BLACK, RED);
    y += 14;

    snprintf(line, sizeof(line), "Rate:  %.1f%%", g_ph_pct);
    Paint_DrawString_EN(4, y, line, &Font12, BLACK, YELLOW);
    y += 14;

    if (g_ph_list > 0)
        snprintf(line, sizeof(line), "List: %ldK", g_ph_list / 1000);
    else
        snprintf(line, sizeof(line), "List: N/A");
    Paint_DrawString_EN(4, y, line, &Font8, BLACK, GRAY);

    draw_footer();
}

/* ═══════════════════════════════════════════════════════════════════════
   Page 4 – Top Blocked Domains
   ═══════════════════════════════════════════════════════════════════════ */
static void draw_page_top_blocked(void)
{
    char line[48];
    draw_header("TOP BLOCKED", RED);
    int y = HDR_H + 4;

    if (g_dom_n == 0) {
        Paint_DrawString_EN(4, y + 20, "No data yet", &Font12, BLACK, GRAY);
        draw_footer();
        return;
    }

    for (int i = 0; i < g_dom_n && i < MAX_TOP; i++) {
        char dom[19];
        trunc_str(g_dom[i], dom, 18);
        snprintf(line, sizeof(line), "%d.%s", i + 1, dom);
        Paint_DrawString_EN(4, y, line, &Font8, BLACK, CYAN);
        y += 9;
        snprintf(line, sizeof(line), "   %ld hits", g_dom_cnt[i]);
        Paint_DrawString_EN(4, y, line, &Font8, BLACK, GRAY);
        y += 10;
    }
    draw_footer();
}

/* ═══════════════════════════════════════════════════════════════════════
   Page 5 – Active Clients
   ═══════════════════════════════════════════════════════════════════════ */
static void draw_page_clients(void)
{
    char line[48];
    draw_header("CLIENTS", CYAN);
    int y = HDR_H + 4;

    snprintf(line, sizeof(line), "Active: %d", g_ph_clients);
    Paint_DrawString_EN(4, y, line, &Font12, BLACK, GREEN);
    y += 16;

    Paint_DrawLine(4, y, W - 4, y, GRAY, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
    y += 5;

    if (g_cli_n == 0) {
        Paint_DrawString_EN(4, y + 10, "No data yet", &Font12, BLACK, GRAY);
        draw_footer();
        return;
    }

    for (int i = 0; i < g_cli_n && i < 3; i++) {
        char cli[17];
        trunc_str(g_cli[i], cli, 16);
        snprintf(line, sizeof(line), "%d. %s", i + 1, cli);
        Paint_DrawString_EN(4, y, line, &Font8, BLACK, WHITE);
        y += 9;
        snprintf(line, sizeof(line), "   %ld qry", g_cli_cnt[i]);
        Paint_DrawString_EN(4, y, line, &Font8, BLACK, GRAY);
        y += 11;
    }
    draw_footer();
}

/* ═══════════════════════════════════════════════════════════════════════
   Render current page
   ═══════════════════════════════════════════════════════════════════════ */
static void render(void)
{
    /* Use SCAN_DIR_DFT + rotate 0 — matches Waveshare example exactly   */
    Paint_NewImage(g_img, W, H, 0, BLACK, 16);
    Paint_Clear(BLACK);

    switch (g_page) {
        case 0: draw_page_system();      break;
        case 1: draw_page_network();     break;
        case 2: draw_page_pihole();      break;
        case 3: draw_page_top_blocked(); break;
        case 4: draw_page_clients();     break;
    }

    LCD_1in44_Display(g_img);
}

/* ═══════════════════════════════════════════════════════════════════════
   Input  –  non-blocking, debounced
   ═══════════════════════════════════════════════════════════════════════ */
static int key_fired(int id)
{
    long now = millis();
    if (now - g_key_ms[id] < DEBOUNCE_MS) return 0;
    int pressed = 0;
    switch (id) {
        case K_UP:    pressed = (GET_KEY_UP    == 0); break;
        case K_DOWN:  pressed = (GET_KEY_DOWN  == 0); break;
        case K_LEFT:  pressed = (GET_KEY_LEFT  == 0); break;
        case K_RIGHT: pressed = (GET_KEY_RIGHT == 0); break;
        case K_PRESS: pressed = (GET_KEY_PRESS == 0); break;
        case K_B1:    pressed = (GET_KEY1      == 0); break;
        case K_B2:    pressed = (GET_KEY2      == 0); break;
        case K_B3:    pressed = (GET_KEY3      == 0); break;
    }
    if (pressed) g_key_ms[id] = now;
    return pressed;
}

static int handle_input(void)
{
    /* Poll all keys in one pass */
    int up    = key_fired(K_UP);
    int down  = key_fired(K_DOWN);
    int left  = key_fired(K_LEFT);
    int right = key_fired(K_RIGHT);
    int press = key_fired(K_PRESS);
    int b1    = key_fired(K_B1);
    int b2    = key_fired(K_B2);
    int b3    = key_fired(K_B3);

    if (!(up || down || left || right || press || b1 || b2 || b3)) return 0;

    g_last_activity = time(NULL);

    /* Press while sleeping: wake display, don't process action */
    if (g_sleeping) {
        g_sleeping = 0;
        g_dimmed   = 0;
        LCD_SetBacklight((UWORD)BL_VALS[g_bl_idx]);
        return 1;
    }

    /* Press while dimmed: restore brightness, then process action normally */
    if (g_dimmed) {
        g_dimmed = 0;
        LCD_SetBacklight((UWORD)BL_VALS[g_bl_idx]);
    }

    int redraw = 0;

    if (up) {
        g_page = (g_page - 1 + TOTAL_PAGES) % TOTAL_PAGES;
        if (g_page >= 2) g_need_fetch = 1;
        redraw = 1;
    }
    if (down) {
        g_page = (g_page + 1) % TOTAL_PAGES;
        if (g_page >= 2) g_need_fetch = 1;
        redraw = 1;
    }
    if (left) {                      /* home: jump to page 1 */
        g_page = 0;
        redraw = 1;
    }
    if (right) {                     /* end: jump to last page */
        g_page = TOTAL_PAGES - 1;
        g_need_fetch = 1;
        redraw = 1;
    }
    if (press) {                     /* joystick press: force refresh */
        if (g_page >= 2) g_need_fetch = 1;
        redraw = 1;
    }
    if (b1) {                        /* KEY1: toggle Pi-hole */
        ph_toggle();
        redraw = 1;
    }
    if (b2) {                        /* KEY2: force refresh */
        if (g_page >= 2) g_need_fetch = 1;
        redraw = 1;
    }
    if (b3) {                        /* KEY3: cycle brightness */
        g_bl_idx = (g_bl_idx + 1) % 3;
        LCD_SetBacklight((UWORD)BL_VALS[g_bl_idx]);
    }
    return redraw;
}

/* ═══════════════════════════════════════════════════════════════════════
   Signal handler + main
   ═══════════════════════════════════════════════════════════════════════ */
static void sig_handler(int s) { (void)s; g_run = 0; }

int main(void)
{
    printf("=== Pi Zero 2W Dashboard ===\n");
    printf("Buttons not working? Add to /boot/config.txt:\n");
    printf("  gpio=6,19,5,26,13,21,20,16=pu  then reboot\n\n");

    signal(SIGINT,  sig_handler);
    signal(SIGTERM, sig_handler);

    if (DEV_ModuleInit() != 0) {
        fprintf(stderr, "DEV_ModuleInit failed\n");
        return 1;
    }

    /* Use SCAN_DIR_DFT (U2D_R2L) – same as Waveshare C example */
    LCD_1in44_Init(SCAN_DIR_DFT);
    LCD_1in44_Clear(BLACK);

    UDOUBLE img_bytes = (UDOUBLE)W * H * 2;
    g_img = (UWORD *)malloc(img_bytes);
    if (!g_img) {
        fprintf(stderr, "malloc failed\n");
        DEV_ModuleExit();
        return 1;
    }

    LCD_SetBacklight((UWORD)BL_VALS[g_bl_idx]);
    g_last_activity = time(NULL);

    printf("Authenticating to Pi-hole...\n");
    ph_auth();
    printf(g_sid[0] ? "Pi-hole auth OK\n" : "Pi-hole: no auth needed / unreachable\n");

    printf("Fetching initial data...\n");
    ph_fetch_summary();
    ph_fetch_blocking();

    time_t last_refresh = time(NULL);
    int need_draw = 1;

    while (g_run) {
        /* --- input (render immediately for snappy feedback, fetch after) --- */
        if (handle_input()) {
            if (!g_sleeping) render();
            need_draw = 0;
        }

        /* --- deferred Pi-hole fetch triggered by navigation / KEY2 --- */
        if (g_need_fetch) {
            fetch_pihole();
            g_need_fetch = 0;
            need_draw = 1;
        }

        /* --- auto-refresh --- */
        time_t now_t = time(NULL);
        if (now_t - last_refresh >= REFRESH_SECS) {
            if (g_page >= 2 && !g_sleeping) fetch_pihole();
            last_refresh = now_t;
            need_draw = 1;
        }

        /* --- dim / sleep timeout --- */
        if (!g_sleeping) {
            long idle = (long)(now_t - g_last_activity);
            if (idle >= SLEEP_SECS) {
                g_sleeping = 1;
                g_dimmed   = 0;
                LCD_SetBacklight(0);
                need_draw  = 0;
            } else if (!g_dimmed && idle >= DIM_SECS) {
                g_dimmed = 1;
                LCD_SetBacklight((UWORD)BL_VALS[0]); /* dim to minimum */
            }
        }

        /* --- draw --- */
        if (need_draw && !g_sleeping) {
            render();
            need_draw = 0;
        }

        DEV_Delay_ms(20);
    }

    printf("\nShutting down...\n");
    LCD_1in44_Clear(BLACK);
    free(g_img);
    DEV_ModuleExit();
    return 0;
}
