#!/usr/bin/env python3
"""Clears the LCD and turns off the backlight. Run on boot before the dashboard starts,
and on service stop/crash to avoid leaving a white screen."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import LCD_1in44

lcd = LCD_1in44.LCD()
lcd.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
lcd.LCD_Clear()
lcd.bl_DutyCycle(0)
lcd.module_exit()
