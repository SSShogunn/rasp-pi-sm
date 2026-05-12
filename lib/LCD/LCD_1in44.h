/*****************************************************************************
* | File      	:   LCD_1in44.h
* | Author      :   Waveshare team
* | Function    :   Hardware underlying interface
* | Info        :
*                Used to shield the underlying layers of each master 
*                and enhance portability
*----------------
* |	This version:   V1.1
* | Date        :   2023-06-05
* | Info        :   Basic version
*
******************************************************************************/
#ifndef __LCD_1IN44_H
#define __LCD_1IN44_H	
	
#include "DEV_Config.h"
#include <stdint.h>

#include <stdlib.h>		//itoa()
#include <stdio.h>


#define LCD_HEIGHT 128
#define LCD_WIDTH 128

#define LCD_X	2
#define LCD_Y	1

#define LCD_WIDTH_Byte 240

#define HORIZONTAL 0
#define VERTICAL   1

#define LCD_X_MAXPIXEL  132  //LCD width maximum memory 
#define LCD_Y_MAXPIXEL  162 //LCD height maximum memory

/********************************************************************************
function:	
			scanning method
********************************************************************************/
typedef enum{
	L2R_U2D  = 0,	//The display interface is displayed , left to right, up to down 
	L2R_D2U  ,
	R2L_U2D  ,
	R2L_D2U  ,
	
	U2D_L2R  ,
	U2D_R2L  ,
	D2U_L2R  ,
	D2U_R2L  , 
}LCD_SCAN_DIR;
#define SCAN_DIR_DFT  U2D_R2L  //Default scan direction = L2R_U2D

typedef struct{
	UWORD LCD_Dis_Column;	//COLUMN
	UWORD LCD_Dis_Page;	//PAGE
	LCD_SCAN_DIR LCD_Scan_Dir;
	UWORD LCD_X_Adjust;		//LCD x actual display position calibration
	UWORD LCD_Y_Adjust;		//LCD y actual display position calibration
}LCD_DIS;



/********************************************************************************
function:	
			Macro definition variable name
********************************************************************************/
void LCD_1in44_Init(LCD_SCAN_DIR Scan_dir);
void LCD_1in44_Clear(UWORD Color);
void LCD_1in44_Display(UWORD *Image);
void LCD_1in44_DisplayWindows(UWORD Xstart, UWORD Ystart, UWORD Xend, UWORD Yend, UWORD *Image);
void LCD_1in44_DisplayPoint(UWORD X, UWORD Y, UWORD Color);
void Handler_1in44_LCD(int signo);
#endif
