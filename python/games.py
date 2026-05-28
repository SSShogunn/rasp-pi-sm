import time, random, threading
from typing import Any, Callable
import state, settings_mgr
from constants import W, H, F_VAL, F_LABEL, F_FOOT, T_PRI, T_DIM, C_HOT
from PIL import Image, ImageDraw

_lock_ref:  Any                       = None
_lcd_ref:   Any                       = None
_render_fn: Callable[[], None] | None = None

def init(lcd, lock, render_fn):
    global _lcd_ref, _lock_ref, _render_fn
    _lcd_ref   = lcd
    _lock_ref  = lock
    _render_fn = render_fn

def _show(img):
    with _lock_ref:
        _lcd_ref.LCD_ShowImage(img)

def _game_over(key, score):
    hi = state.high_scores.get(key, 0)
    img = Image.new("RGB", (W, H), (15, 0, 0))
    d   = ImageDraw.Draw(img)
    tw  = lambda t, f: int(d.textlength(t, font=f))
    d.text(((W - tw("GAME OVER", F_VAL)) // 2, 40), "GAME OVER", font=F_VAL, fill=C_HOT)
    d.text(((W - tw(f"Score: {score}", F_LABEL)) // 2, 58),
           f"Score: {score}", font=F_LABEL, fill=T_PRI)
    d.text(((W - tw(f"Best:  {hi}", F_LABEL)) // 2, 72),
           f"Best:  {hi}", font=F_LABEL, fill=(255, 200, 0))
    d.text(((W - tw("KEY3 to exit", F_FOOT)) // 2, 92),
           "KEY3 to exit", font=F_FOOT, fill=T_DIM)
    _show(img)
    while state.running and not _lcd_ref.GPIO_KEY3_PIN.value:
        time.sleep(0.1)
    time.sleep(0.3)
    state.game_active = False
    if _render_fn: _render_fn()

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
        if lcd.GPIO_KEY3_PIN.value: break

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

    if score > state.high_scores["SNAKE"]:
        state.high_scores["SNAKE"] = score
        settings_mgr.save()
    _game_over("SNAKE", score)

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
        if lcd.GPIO_KEY3_PIN.value: break

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

    if p_sc > state.high_scores["PONG"]:
        state.high_scores["PONG"] = p_sc
        settings_mgr.save()
    _game_over("PONG", p_sc)

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
        if lcd.GPIO_KEY3_PIN.value: break

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

    if score > state.high_scores["FLAPPY"]:
        state.high_scores["FLAPPY"] = score
        settings_mgr.save()
    _game_over("FLAPPY", score)

# ── tetris ────────────────────────────────────────────────────────────────────
_T_CELL = 5
_T_COLS = 10
_T_ROWS = 20
_T_BX   = 4
_T_BY   = 8
_T_BW   = _T_COLS * _T_CELL
_T_BH   = _T_ROWS * _T_CELL

_PIECES = [
    [(0,1),(1,1),(2,1),(3,1)],
    [(0,0),(1,0),(0,1),(1,1)],
    [(1,0),(0,1),(1,1),(2,1)],
    [(0,1),(1,1),(1,0),(2,0)],
    [(0,0),(1,0),(1,1),(2,1)],
    [(0,0),(0,1),(1,1),(2,1)],
    [(2,0),(0,1),(1,1),(2,1)],
]
_PIECE_COLS = [
    (0,220,220),(220,220,0),(160,0,220),
    (0,220,0),(220,0,0),(0,80,220),(220,120,0),
]

def _t_rotate(piece):
    my = max(y for x,y in piece)
    return [(my-y, x) for x,y in piece]

def _t_valid(board, piece, ox, oy):
    for x,y in piece:
        nx,ny = x+ox, y+oy
        if nx<0 or nx>=_T_COLS or ny>=_T_ROWS: return False
        if ny>=0 and board[ny][nx]: return False
    return True

def _game_tetris():
    BG_T=(5,5,18); GRID_C=(20,22,40); BORDER=(40,44,70)
    board = [[None]*_T_COLS for _ in range(_T_ROWS)]
    lcd   = _lcd_ref
    score=0; level=1; lines_total=0
    FRAME=1.0/30

    def _new():
        idx=random.randrange(len(_PIECES))
        return list(_PIECES[idx]), _PIECE_COLS[idx]

    def _draw(cur, col, ox, oy, goy):
        img=Image.new("RGB",(W,H),BG_T); d=ImageDraw.Draw(img)
        d.rectangle([_T_BX-1,_T_BY-1,_T_BX+_T_BW,_T_BY+_T_BH],outline=BORDER)
        for c in range(1,_T_COLS):
            d.line([(_T_BX+c*_T_CELL,_T_BY),(_T_BX+c*_T_CELL,_T_BY+_T_BH-1)],fill=GRID_C)
        for r in range(1,_T_ROWS):
            d.line([(_T_BX,_T_BY+r*_T_CELL),(_T_BX+_T_BW-1,_T_BY+r*_T_CELL)],fill=GRID_C)
        for r in range(_T_ROWS):
            for c in range(_T_COLS):
                if board[r][c]:
                    px=_T_BX+c*_T_CELL; py=_T_BY+r*_T_CELL
                    d.rectangle([px+1,py+1,px+_T_CELL-2,py+_T_CELL-2],fill=board[r][c])
        gc=(col[0]//5,col[1]//5,col[2]//5)
        for x,y in cur:
            if y+goy>=0:
                px=_T_BX+(x+ox)*_T_CELL; py=_T_BY+(y+goy)*_T_CELL
                d.rectangle([px+1,py+1,px+_T_CELL-2,py+_T_CELL-2],outline=gc)
        for x,y in cur:
            if y+oy>=0:
                px=_T_BX+(x+ox)*_T_CELL; py=_T_BY+(y+oy)*_T_CELL
                d.rectangle([px+1,py+1,px+_T_CELL-2,py+_T_CELL-2],fill=col)
        sx=_T_BX+_T_BW+5
        d.text((sx,_T_BY),    "SCR",      font=F_FOOT,fill=(100,110,132))
        d.text((sx,_T_BY+9),  str(score), font=F_FOOT,fill=(220,225,238))
        d.text((sx,_T_BY+22), "LVL",      font=F_FOOT,fill=(100,110,132))
        d.text((sx,_T_BY+31), str(level), font=F_FOOT,fill=(255,200,0))
        d.text((sx,_T_BY+44), "LNS",      font=F_FOOT,fill=(100,110,132))
        d.text((sx,_T_BY+53), str(lines_total),font=F_FOOT,fill=(0,215,105))
        return img

    piece,col=_new(); ox=_T_COLS//2-2; oy=-2
    drop_iv=0.7; last_drop=last_inp=time.time()
    prev_up=prev_lt=prev_rt=False

    while state.running:
        t0=time.time()
        if lcd.GPIO_KEY3_PIN.value: break
        goy=oy
        while _t_valid(board,piece,ox,goy+1): goy+=1

        if t0-last_inp>=0.1:
            up=lcd.GPIO_KEY_UP_PIN.value
            lt=lcd.GPIO_KEY_LEFT_PIN.value
            rt=lcd.GPIO_KEY_RIGHT_PIN.value
            dn=lcd.GPIO_KEY_DOWN_PIN.value
            pr=lcd.GPIO_KEY_PRESS_PIN.value
            if lt and not prev_lt and _t_valid(board,piece,ox-1,oy): ox-=1
            if rt and not prev_rt and _t_valid(board,piece,ox+1,oy): ox+=1
            drop_iv=0.05 if dn else max(0.1,0.7-(level-1)*0.05)
            if up and not prev_up:
                rot=_t_rotate(piece)
                if   _t_valid(board,rot,ox,oy):  piece=rot
                elif _t_valid(board,rot,ox+1,oy): piece=rot; ox+=1
                elif _t_valid(board,rot,ox-1,oy): piece=rot; ox-=1
            if pr: oy=goy; last_drop=0
            prev_up=up; prev_lt=lt; prev_rt=rt; last_inp=t0

        if t0-last_drop>=drop_iv:
            if _t_valid(board,piece,ox,oy+1):
                oy+=1
            else:
                for x,y in piece:
                    if y+oy>=0: board[y+oy][x+ox]=col
                new_b=[r for r in board if any(c is None for c in r)]
                cleared=_T_ROWS-len(new_b)
                if cleared:
                    lines_total+=cleared
                    score+=[0,100,300,500,800][min(cleared,4)]*level
                    level=lines_total//10+1
                    board=[[None]*_T_COLS for _ in range(cleared)]+new_b
                piece,col=_new(); ox=_T_COLS//2-2; oy=-2
                if not _t_valid(board,piece,ox,oy): break
            last_drop=t0

        _show(_draw(piece,col,ox,oy,goy))
        time.sleep(max(0,FRAME-(time.time()-t0)))

    if score>state.high_scores["TETRIS"]:
        state.high_scores["TETRIS"]=score; settings_mgr.save()
    _game_over("TETRIS",score)

# ── breakout ──────────────────────────────────────────────────────────────────
_BRK_ROWS=5; _BRK_COLS=8; _BRK_W=14; _BRK_H=6; _BRK_PAD_Y=2; _BRK_OFF_Y=16
_BRK_COLS_C=[(220,50,50),(220,150,30),(200,200,0),(50,200,80),(50,150,220)]

def _game_breakout():
    BG_B=(5,5,20); PAD_W=26; PAD_H=4; PAD_Y=H-12; BALL=4
    lcd=_lcd_ref
    bricks=[[True]*_BRK_COLS for _ in range(_BRK_ROWS)]
    total=_BRK_ROWS*_BRK_COLS
    px=W//2-PAD_W//2
    bx=float(W//2); by=float(PAD_Y-BALL-2)
    speed=2.2
    bvx=speed*(1 if random.random()>0.5 else -1); bvy=-speed
    score=0; lives=3; FRAME=1.0/40

    while state.running:
        t0=time.time()
        if lcd.GPIO_KEY3_PIN.value: break
        if lcd.GPIO_KEY_LEFT_PIN.value:  px=max(0,px-4)
        if lcd.GPIO_KEY_RIGHT_PIN.value: px=min(W-PAD_W,px+4)
        bx+=bvx; by+=bvy
        if bx<=0:        bx=0;        bvx=abs(bvx)
        if bx>=W-BALL:   bx=W-BALL;   bvx=-abs(bvx)
        if by<=0:        by=0;        bvy=abs(bvy)
        if (by+BALL>=PAD_Y and by+BALL<=PAD_Y+PAD_H
                and bx+BALL>=px and bx<=px+PAD_W):
            rel=(bx+BALL/2-px)/PAD_W
            bvx=speed*(rel-0.5)*2.4; bvy=-abs(bvy); by=PAD_Y-BALL-1
        bx1=int(bx);bx2=bx1+BALL-1;by1=int(by);by2=by1+BALL-1
        for r in range(_BRK_ROWS):
            for c in range(_BRK_COLS):
                if not bricks[r][c]: continue
                rx1=1+c*(_BRK_W+1); ry1=_BRK_OFF_Y+r*(_BRK_H+_BRK_PAD_Y)
                rx2=rx1+_BRK_W-1;   ry2=ry1+_BRK_H-1
                if bx2>=rx1 and bx1<=rx2 and by2>=ry1 and by1<=ry2:
                    bricks[r][c]=False; score+=(5-r)*10; total-=1
                    ov_y=min(by2-ry1,ry2-by1); ov_x=min(bx2-rx1,rx2-bx1)
                    if ov_y<ov_x: bvy=-bvy
                    else:         bvx=-bvx
        if by>H:
            lives-=1
            if lives<=0: break
            bx=float(px+PAD_W//2); by=float(PAD_Y-BALL-2)
            bvx=speed*(1 if random.random()>0.5 else -1); bvy=-speed
        if total<=0:
            speed=min(speed+0.5,5.0)
            bricks=[[True]*_BRK_COLS for _ in range(_BRK_ROWS)]; total=_BRK_ROWS*_BRK_COLS
        img=Image.new("RGB",(W,H),BG_B); d=ImageDraw.Draw(img)
        for r in range(_BRK_ROWS):
            for c in range(_BRK_COLS):
                if bricks[r][c]:
                    rx=1+c*(_BRK_W+1); ry=_BRK_OFF_Y+r*(_BRK_H+_BRK_PAD_Y)
                    d.rectangle([rx,ry,rx+_BRK_W-1,ry+_BRK_H-1],fill=_BRK_COLS_C[r])
        d.rectangle([px,PAD_Y,px+PAD_W-1,PAD_Y+PAD_H-1],fill=(0,200,255))
        d.ellipse([int(bx),int(by),int(bx)+BALL-1,int(by)+BALL-1],fill=(255,220,80))
        tw=lambda t,f:int(d.textlength(t,font=f))
        d.text((2,2),f"SCR {score}",font=F_FOOT,fill=(180,180,200))
        d.text((W-tw(f"x{lives}",F_FOOT)-2,2),f"x{lives}",font=F_FOOT,fill=(220,50,50))
        _show(img)
        time.sleep(max(0,FRAME-(time.time()-t0)))

    if score>state.high_scores["BREAKOUT"]:
        state.high_scores["BREAKOUT"]=score; settings_mgr.save()
    _game_over("BREAKOUT",score)

# ── launcher ──────────────────────────────────────────────────────────────────
_GAME_FNS = [_game_snake, _game_pong, _game_flappy, _game_tetris, _game_breakout]

def launch(idx):
    state.game_active = True
    threading.Thread(target=_GAME_FNS[idx], daemon=True).start()
