import config
import time
import numpy as np

LCD_WIDTH  = 128
LCD_HEIGHT = 128
LCD_X = 2
LCD_Y = 1

LCD_X_MAXPIXEL = 132
LCD_Y_MAXPIXEL = 162

L2R_U2D = 1; L2R_D2U = 2; R2L_U2D = 3; R2L_D2U = 4
U2D_L2R = 5; U2D_R2L = 6; D2U_L2R = 7; D2U_R2L = 8
SCAN_DIR_DFT = U2D_R2L


class LCD(config.RaspberryPi):
    width        = LCD_WIDTH
    height       = LCD_HEIGHT
    LCD_Scan_Dir = SCAN_DIR_DFT
    LCD_X_Adjust = LCD_X
    LCD_Y_Adjust = LCD_Y

    def LCD_Reset(self):
        self.digital_write(self.GPIO_RST_PIN, True);  time.sleep(0.01)
        self.digital_write(self.GPIO_RST_PIN, False); time.sleep(0.01)
        self.digital_write(self.GPIO_RST_PIN, True);  time.sleep(0.01)

    def LCD_WriteReg(self, Reg):
        self.digital_write(self.GPIO_DC_PIN, False)
        self.spi_writebyte([Reg])

    def LCD_WriteData_8bit(self, Data):
        self.digital_write(self.GPIO_DC_PIN, True)
        self.spi_writebyte([Data])

    def LCD_InitReg(self):
        self.LCD_WriteReg(0xB1)
        self.LCD_WriteData_8bit(0x01); self.LCD_WriteData_8bit(0x2C); self.LCD_WriteData_8bit(0x2D)
        self.LCD_WriteReg(0xB2)
        self.LCD_WriteData_8bit(0x01); self.LCD_WriteData_8bit(0x2C); self.LCD_WriteData_8bit(0x2D)
        self.LCD_WriteReg(0xB3)
        for _ in range(2):
            self.LCD_WriteData_8bit(0x01); self.LCD_WriteData_8bit(0x2C); self.LCD_WriteData_8bit(0x2D)
        self.LCD_WriteReg(0xB4); self.LCD_WriteData_8bit(0x07)
        self.LCD_WriteReg(0xC0)
        self.LCD_WriteData_8bit(0xA2); self.LCD_WriteData_8bit(0x02); self.LCD_WriteData_8bit(0x84)
        self.LCD_WriteReg(0xC1); self.LCD_WriteData_8bit(0xC5)
        self.LCD_WriteReg(0xC2); self.LCD_WriteData_8bit(0x0A); self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteReg(0xC3); self.LCD_WriteData_8bit(0x8A); self.LCD_WriteData_8bit(0x2A)
        self.LCD_WriteReg(0xC4); self.LCD_WriteData_8bit(0x8A); self.LCD_WriteData_8bit(0xEE)
        self.LCD_WriteReg(0xC5); self.LCD_WriteData_8bit(0x0E)
        self.LCD_WriteReg(0xe0)
        for b in [0x0f,0x1a,0x0f,0x18,0x2f,0x28,0x20,0x22,0x1f,0x1b,0x23,0x37,0x00,0x07,0x02,0x10]:
            self.LCD_WriteData_8bit(b)
        self.LCD_WriteReg(0xe1)
        for b in [0x0f,0x1b,0x0f,0x17,0x33,0x2c,0x29,0x2e,0x30,0x30,0x39,0x3f,0x00,0x07,0x03,0x10]:
            self.LCD_WriteData_8bit(b)
        self.LCD_WriteReg(0xF0); self.LCD_WriteData_8bit(0x01)
        self.LCD_WriteReg(0xF6); self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteReg(0x3A); self.LCD_WriteData_8bit(0x05)

    def LCD_SetGramScanWay(self, Scan_dir):
        self.LCD_Scan_Dir = Scan_dir
        if Scan_dir in (L2R_U2D, L2R_D2U, R2L_U2D, R2L_D2U):
            self.width = LCD_HEIGHT; self.height = LCD_WIDTH
            mem = {L2R_U2D: 0x00, L2R_D2U: 0x80, R2L_U2D: 0x40, R2L_D2U: 0xC0}[Scan_dir]
        else:
            self.width = LCD_WIDTH; self.height = LCD_HEIGHT
            mem = {U2D_L2R: 0x20, U2D_R2L: 0x60, D2U_L2R: 0xA0, D2U_R2L: 0xE0}[Scan_dir]
        self.LCD_X_Adjust = LCD_Y
        self.LCD_Y_Adjust = LCD_X
        self.LCD_WriteReg(0x36)
        self.LCD_WriteData_8bit(mem | 0x08)

    def LCD_Init(self, Lcd_ScanDir):
        if self.module_init() != 0:
            return -1
        # keep the backlight OFF through init so the white power-on / clear
        # is never shown; the app raises it (apply_backlight) once the first
        # frame is drawn.
        self.bl_DutyCycle(0)
        self.LCD_Reset()
        self.LCD_InitReg()
        self.LCD_SetGramScanWay(Lcd_ScanDir)
        self.delay_ms(200)
        self.LCD_WriteReg(0x11); self.delay_ms(120)
        self.LCD_WriteReg(0x29)

    def LCD_SetWindows(self, Xstart, Ystart, Xend, Yend):
        self.LCD_WriteReg(0x2A)
        self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteData_8bit((Xstart & 0xff) + self.LCD_X_Adjust)
        self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteData_8bit(((Xend - 1) & 0xff) + self.LCD_X_Adjust)
        self.LCD_WriteReg(0x2B)
        self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteData_8bit((Ystart & 0xff) + self.LCD_Y_Adjust)
        self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteData_8bit(((Yend - 1) & 0xff) + self.LCD_Y_Adjust)
        self.LCD_WriteReg(0x2C)

    def LCD_Clear(self):
        buf = b'\x00' * (self.width * self.height * 2)   # black, not white
        self.LCD_SetWindows(0, 0, self.width, self.height)
        self.digital_write(self.GPIO_DC_PIN, True)
        for i in range(0, len(buf), 4096):
            self.spi_writebyte(buf[i:i+4096])

    def LCD_ShowImage(self, Image):
        if Image is None:
            return
        img = np.asarray(Image)
        pix = np.empty((self.width, self.height, 2), dtype=np.uint8)
        pix[..., [0]] = np.bitwise_and(img[..., [0]], 0xF8) | np.right_shift(img[..., [1]], 5)
        pix[..., [1]] = np.bitwise_and(np.left_shift(img[..., [1]], 3), 0xE0) | np.right_shift(img[..., [2]], 3)
        raw = pix.tobytes()
        self.LCD_SetWindows(0, 0, self.width, self.height)
        self.digital_write(self.GPIO_DC_PIN, True)
        for i in range(0, len(raw), 4096):
            self.spi_writebyte(raw[i:i+4096])
