import time, random, threading
import state
from constants import W, H, F_VAL, F_LABEL, F_FOOT, T_PRI, T_DIM, C_HOT, C_OK, GAME_LIST
from PIL import Image, ImageDraw

_lock_ref  = None
_lcd_ref   = None
_render_fn = None

def init(lcd, lock, render_fn):
    global _lcd_ref, _lock_ref, _render_fn
    _lcd_ref   = lcd
    _lock_ref  = lock
    _render_fn = render_fn

def _show(img):
    with _lock_ref:
        _lcd_ref.LCD_ShowImage(img)

# ── snake ─────────────────────────────────────────────────────────────────────
_SN_CELL = 5
_SN_COLS = W // _SN_CELL
_SN_ROWS = H // _SN_CELL

def _sn_food(body):
    while True:
        c, r = random.randint(0, _SN_COLS - 1), random.randint(0, _SN_ROWS - 1)
        if (c, r) not in body:
            return (c, r)

def _game_snake():
    BG_G = (5, 18, 5); SNKC = (0, 190, 80); HEAD = (0, 255, 110); FOOD = (255, 50, 50)
    snake  = [(12, 12), (11, 12), (10, 12)]
    direc  = (1, 0); pend = (1, 0)
    food   = _sn_food(snake)
    score  = 0; step = 0.18
    last_step = last_inp = time.time()
    lcd = _lcd_ref

    while state.running:
        now = time.time()
        if now - last_inp >= 0.08:
            if   lcd.GPIO_KEY_UP_PIN.value    and direc != (0,  1): pend = (0, -1); last_inp = now
            elif lcd.GPIO_KEY_DOWN_PIN.value  and direc != (0, -1): pend = (0,  1); last_inp = now
            elif lcd.GPIO_KEY_LEFT_PIN.value  and direc != (1,  0): pend = (-1, 0); last_inp = now
            elif lcd.GPIO_KEY_RIGHT_PIN.value and direc != (-1, 0): pend = (1,  0); last_inp = now
        if lcd.GPIO_KEY2_PIN.value: break

        if now - last_step >= step:
            direc = pend
            hx = snake[0][0] + direc[0]
            hy = snake[0][1] + direc[1]
            if hx < 0 or hx >= _SN_COLS or hy < 0 or hy >= _SN_ROWS or (hx, hy) in snake:
                break
            snake.insert(0, (hx, hy))
            if (hx, hy) == food:
                score += 1; food = _sn_food(snake); step = max(0.07, step - 0.008)
            else:
                snake.pop()
            last_step = now

            img = Image.new("RGB", (W, H), BG_G); d = ImageDraw.Draw(img)
            fx, fy = food
            d.ellipse([fx*_SN_CELL+1, fy*_SN_CELL+1,
                       fx*_SN_CELL+_SN_CELL-2, fy*_SN_CELL+_SN_CELL-2], fill=FOOD)
            for i, (cx, cy) in enumerate(snake):
                d.rectangle([cx*_SN_CELL, cy*_SN_CELL,
                             cx*_SN_CELL+_SN_CELL-2, cy*_SN_CELL+_SN_CELL-2],
                            fill=HEAD if i == 0 else SNKC)
            d.text((2, 2), str(score), font=F_VAL, fill=T_PRI)
            _show(img)
        time.sleep(0.02)

    img = Image.new("RGB", (W, H), (15, 0, 0)); d = ImageDraw.Draw(img)
    tw = lambda t, f: int(d.textlength(t, font=f))
    d.text(((W - tw("GAME OVER", F_VAL)) // 2, 50), "GAME OVER", font=F_VAL, fill=C_HOT)
    d.text(((W - tw(f"Score: {score}", F_LABEL)) // 2, 66), f"Score: {score}", font=F_LABEL, fill=T_PRI)
    d.text(((W - tw("KEY2 to exit", F_FOOT)) // 2, 86), "KEY2 to exit", font=F_FOOT, fill=T_DIM)
    _show(img)
    while state.running and not _lcd_ref.GPIO_KEY2_PIN.value:
        time.sleep(0.1)
    time.sleep(0.3)
    state.game_active = False
    if _render_fn: _render_fn()

# ── pong ──────────────────────────────────────────────────────────────────────
def _game_pong():
    PAD_W=4; PAD_H=22; PL_SPD=3; AI_SPD=2; BALL=4
    PL_X=5; AI_X=W-5-PAD_W
    ball=[W//2, H//2]; bvx=2; bvy=2
    pl_y=H//2-PAD_H//2; ai_y=H//2-PAD_H//2
    p_sc=0; a_sc=0
    BG_P=(5,5,20); PLCOL=(0,200,255); AICOL=(255,80,50); BCOL=(255,220,0)
    FRAME=1.0/30
    lcd = _lcd_ref

    while state.running:
        t0 = time.time()
        if lcd.GPIO_KEY_UP_PIN.value:   pl_y = max(0, pl_y - PL_SPD)
        if lcd.GPIO_KEY_DOWN_PIN.value: pl_y = min(H - PAD_H, pl_y + PL_SPD)
        if lcd.GPIO_KEY2_PIN.value: break

        ball[0] += bvx; ball[1] += bvy
        if ball[1] <= 0:       ball[1] = 0;      bvy = abs(bvy)
        if ball[1] >= H-BALL:  ball[1] = H-BALL; bvy = -abs(bvy)

        if bvx < 0 and ball[0] <= PL_X+PAD_W and pl_y <= ball[1]+BALL and ball[1] <= pl_y+PAD_H:
            bvx = abs(bvx); rel = (ball[1]+BALL//2-pl_y)/PAD_H; bvy = int((rel-0.5)*5) or 1
        if bvx > 0 and ball[0]+BALL >= AI_X and ball[0] <= AI_X+PAD_W and ai_y <= ball[1]+BALL and ball[1] <= ai_y+PAD_H:
            bvx = -abs(bvx); rel = (ball[1]+BALL//2-ai_y)/PAD_H; bvy = int((rel-0.5)*5) or -1

        if ball[0] < 0:  a_sc += 1; ball = [W//2, H//2]; bvx = -2; bvy = random.choice([-2, 2])
        if ball[0] > W:  p_sc += 1; ball = [W//2, H//2]; bvx = 2;  bvy = random.choice([-2, 2])

        ac = ai_y + PAD_H//2; bc = ball[1] + BALL//2
        if ac < bc: ai_y = min(H-PAD_H, ai_y+AI_SPD)
        elif ac > bc: ai_y = max(0, ai_y-AI_SPD)

        img = Image.new("RGB", (W, H), BG_P); d = ImageDraw.Draw(img)
        for y in range(0, H, 8): d.rectangle([W//2-1, y, W//2, y+4], fill=(25, 25, 50))
        d.rectangle([PL_X, pl_y, PL_X+PAD_W-1, pl_y+PAD_H-1], fill=PLCOL)
        d.rectangle([AI_X, ai_y, AI_X+PAD_W-1, ai_y+PAD_H-1], fill=AICOL)
        d.rectangle([ball[0], ball[1], ball[0]+BALL-1, ball[1]+BALL-1], fill=BCOL)
        ps = str(p_sc); as_ = str(a_sc)
        tw = lambda t, f: int(d.textlength(t, font=f))
        d.text((W//4  - tw(ps,  F_VAL)//2, 2), ps,  font=F_VAL, fill=PLCOL)
        d.text((3*W//4 - tw(as_, F_VAL)//2, 2), as_, font=F_VAL, fill=AICOL)
        _show(img)
        time.sleep(max(0, FRAME - (time.time() - t0)))

    state.game_active = False
    if _render_fn: _render_fn()

# ── flappy ────────────────────────────────────────────────────────────────────
def _game_flappy():
    GRAVITY=0.35; FLAP=-3.5; PIPE_W=14; GAP=40; SCROLL=2; BIRD_X=28; BIRD_S=6
    bird_y=float(H//2); bird_v=0.0; pipes=[]; score=0; ticks=0
    prev_up=prev_pr=prev_k3=False
    BG_F=(5,8,28); PCOL=(30,160,50); BCOL=(255,220,0); GCOL=(30,20,8)
    FRAME=1.0/30
    lcd = _lcd_ref

    while state.running:
        t0 = time.time(); ticks += 1
        if ticks % 55 == 0 or not pipes:
            pipes.append([W + PIPE_W, random.randint(15, H - GAP - 15)])

        up_now = lcd.GPIO_KEY_UP_PIN.value
        pr_now = lcd.GPIO_KEY_PRESS_PIN.value
        k3_now = lcd.GPIO_KEY3_PIN.value
        flap   = (up_now and not prev_up) or (pr_now and not prev_pr) or (k3_now and not prev_k3)
        prev_up = up_now; prev_pr = pr_now; prev_k3 = k3_now
        if lcd.GPIO_KEY2_PIN.value: break

        if flap: bird_v = FLAP
        bird_v += GRAVITY; bird_y += bird_v
        for p in pipes: p[0] -= SCROLL
        for p in pipes:
            if p[0] + PIPE_W == BIRD_X: score += 1
        pipes = [p for p in pipes if p[0] > -PIPE_W]

        bx1=BIRD_X-BIRD_S//2; bx2=BIRD_X+BIRD_S//2
        by1=int(bird_y-BIRD_S//2); by2=int(bird_y+BIRD_S//2)
        dead = bird_y < BIRD_S//2 or bird_y > H - BIRD_S//2
        for px, gy in pipes:
            if bx2 > px and bx1 < px+PIPE_W and (by1 < gy or by2 > gy+GAP): dead = True

        img = Image.new("RGB", (W, H), BG_F); d = ImageDraw.Draw(img)
        d.rectangle([0, H-5, W-1, H-1], fill=GCOL)
        for px, gy in pipes:
            d.rectangle([px, 0, px+PIPE_W-1, gy-1], fill=PCOL)
            d.rectangle([px, gy+GAP, px+PIPE_W-1, H-6], fill=PCOL)
        d.rectangle([bx1, by1, bx2-1, by2-1], fill=BCOL)
        sc = str(score)
        tw = lambda t, f: int(d.textlength(t, font=f))
        d.text(((W - tw(sc, F_VAL)) // 2, 3), sc, font=F_VAL, fill=T_PRI)
        if dead:
            d.text(((W - tw("DEAD!", F_VAL)) // 2, H//2-8), "DEAD!", font=F_VAL, fill=C_HOT)
            _show(img)
            time.sleep(1.5); break
        _show(img)
        time.sleep(max(0, FRAME - (time.time() - t0)))

    state.game_active = False
    if _render_fn: _render_fn()

# ── launcher ──────────────────────────────────────────────────────────────────
_GAME_FNS = [_game_snake, _game_pong, _game_flappy]

def launch(idx):
    state.game_active = True
    threading.Thread(target=_GAME_FNS[idx], daemon=True).start()
