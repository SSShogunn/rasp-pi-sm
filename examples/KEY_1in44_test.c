#include "DEV_Config.h"
#include "LCD_1in44.h"
#include "GUI_Paint.h"
#include "GUI_BMP.h"
#include "KEY_APP.h"

#include "test.h"

#include <stdio.h>		//printf()
#include <stdlib.h>		//exit()
#include <signal.h>     //signal()
#include <time.h>  
// extern LCD_DIS sLCD_DIS;
/************************************
When using the button
Please execute
    sudo nano /boot/config.txt
Add at the end
    gpio=6,19,5,26,13,21,20,16=pu
*************************************/
void KEY_1in44_test(void)
{
    // Exception handling:ctrl + c
    // signal(SIGINT, Handler_1in44_LCD);
    
    /* Module Init */
	// if(DEV_ModuleInit() != 0){
    //     DEV_ModuleExit();
    //     exit(0);
    // }
    // printf("Use this routine to add gpio=6,19,5,26,13,21,20,16=pu at the end of /boot/config.txt\r\n");
    // LCD_SCAN_DIR LCD_ScanDir = SCAN_DIR_DFT;//SCAN_DIR_DFT = D2U_L2R
	
    // /* LCD Init */
	// printf("1.44inch LCD KEY demo...\r\n");
	// LCD_1in44_Init(LCD_ScanDir);
	// LCD_1in44_Clear(WHITE);
    
    UWORD *BlackImage;
    UWORD Imagesize = LCD_HEIGHT*LCD_WIDTH;
    if((BlackImage = (UWORD *)malloc(Imagesize)) == NULL) {
        printf("Failed to apply for black memory...\r\n");
        exit(0);
    }

    /*1.Create a new image cache named IMAGE_RGB and fill it with white*/
    printf("LCD_WIDTH = %d   LCD_HEIGHT  = %d\r\n", LCD_WIDTH , LCD_HEIGHT);
    
    Paint_NewImage(BlackImage, LCD_WIDTH, LCD_HEIGHT, 0, WHITE, 16);
    Paint_Clear(WHITE);
   
    /* Monitor button */
    printf("Listening KEY\r\n");
    KEY_Listen(BlackImage);
    
    /* Module Exit */
    free(BlackImage);
    BlackImage = NULL;
	// DEV_ModuleExit();
}

