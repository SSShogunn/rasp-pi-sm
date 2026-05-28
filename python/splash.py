"""Boot splash — shown immediately after the LCD comes up, before the
heavier modules (fetch/draw/games) finish importing. Pure PIL, no deps on
the rest of the app so it can be imported and run as early as possible."""
import time
from PIL import Image, ImageDraw
from constants import W, H, F_BIG, F_LABEL, F_FOOT, BG, ACC_SYS, ACC_NET, T_PRI, T_DIM


def show(lcd, hold=0.9):
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    tw  = lambda t, f: int(d.textlength(t, font=f))

    # title
    t1 = "Pi"; t2 = "DASH"
    d.text(((W - tw(t1 + t2, F_BIG)) // 2, 34), t1, font=F_BIG, fill=ACC_SYS)
    d.text(((W - tw(t1 + t2, F_BIG)) // 2 + tw(t1, F_BIG), 34),
           t2, font=F_BIG, fill=T_PRI)
    sub = "Zero 2W Dashboard"
    d.text(((W - tw(sub, F_LABEL)) // 2, 66), sub, font=F_LABEL, fill=T_DIM)

    # animated loading bar
    bx, by, bw, bh = 24, 86, W - 48, 6
    d.rectangle([bx, by, bx + bw - 1, by + bh - 1], outline=T_DIM)
    steps = 10
    for i in range(steps + 1):
        fw = int((bw - 2) * i / steps)
        d.rectangle([bx + 1, by + 1, bx + 1 + fw, by + bh - 2], fill=ACC_NET)
        lcd.LCD_ShowImage(img)
        time.sleep(hold / steps)
