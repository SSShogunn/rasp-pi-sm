/*****************************************************************************
* | File      	:   .c
* | Author      :   Waveshare team
* | Function    :   Hardware underlying interface
* | Info        :
*                Used to shield the underlying layers of each master
*                and enhance portability
*----------------
* |	This version:   V1.0
* | Date        :   2018-01-11
* | Info        :   Basic version
*
******************************************************************************/
#include "Debug.h"
#include "KEY_APP.h"


void Draw_Init(UWORD *Image)
{
       /* Press */
    Paint_DrawRectangle(40, 60, 60, 80, RED,DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(43, 60, "P", &Font24, IMAGE_BACKGROUND, BLUE);

    /* Left */
    Paint_DrawRectangle(20, 60, 40, 80, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(23, 60, "L", &Font24, IMAGE_BACKGROUND, BLUE);

    /* Right */
    Paint_DrawRectangle(60, 60, 80, 80, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(63, 60, "R", &Font24, IMAGE_BACKGROUND, BLUE);

    /* Up */
    Paint_DrawRectangle(40, 40, 60, 60, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(43, 40, "U", &Font24, IMAGE_BACKGROUND, BLUE);

    /* Down */
    Paint_DrawRectangle(40, 80, 60, 100, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(43, 80, "D", &Font24, IMAGE_BACKGROUND, BLUE);

    /* Key1 */
    Paint_DrawRectangle(95, 40, 120, 60, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(98, 43, "K1", &Font16, IMAGE_BACKGROUND, BLUE);

    /* Key2	*/
    Paint_DrawRectangle(95, 60, 120, 80, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(98, 63, "K2", &Font16, IMAGE_BACKGROUND, BLUE);

    /* Key3 */
    Paint_DrawRectangle(95, 80, 120, 100, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(98, 83, "K3", &Font16, IMAGE_BACKGROUND, BLUE);

    LCD_1in44_Display(Image);
}

void KEY_Listen(UWORD *Image)
{
    Draw_Init(Image);
    for(;;) {
        if(GET_KEY_UP == 0) {
            while(GET_KEY_UP == 0) {
                Paint_DrawRectangle(40, 40, 60, 60, BLUE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
                GUI_Partial_Refresh(40, 40, 60, 60);
            }
            Paint_DrawRectangle(40, 40, 60, 60, WHITE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
            Paint_DrawRectangle(40, 40, 60, 60, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
            Paint_DrawString_EN(43, 40, "U", &Font24, IMAGE_BACKGROUND, BLUE);
            GUI_Partial_Refresh(40, 40, 60, 60);
        }
        if(GET_KEY_DOWN == 0) {
            while(GET_KEY_DOWN == 0) {
                Paint_DrawRectangle(40, 80, 60, 100, BLUE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
                GUI_Partial_Refresh(40, 80, 60, 100);
            }
            Paint_DrawRectangle(40, 80, 60, 100, WHITE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
            Paint_DrawRectangle(40, 80, 60, 100, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
            Paint_DrawString_EN(43, 80, "D", &Font24, IMAGE_BACKGROUND, BLUE);
            GUI_Partial_Refresh(40, 80, 60, 100);
        }
        if(GET_KEY_LEFT == 0) {
            while(GET_KEY_LEFT == 0) {
                Paint_DrawRectangle(20, 60, 40, 80, BLUE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
                GUI_Partial_Refresh(20, 60, 40, 80);
            }
            Paint_DrawRectangle(20, 60, 40, 80, WHITE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
            Paint_DrawRectangle(20, 60, 40, 80, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
            Paint_DrawString_EN(23, 60, "L", &Font24, IMAGE_BACKGROUND, BLUE);
            GUI_Partial_Refresh(20, 60, 40, 80);
        }
        if(GET_KEY_RIGHT == 0) {
            while(GET_KEY_RIGHT == 0) {
                Paint_DrawRectangle(60, 60, 80, 80, BLUE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
                GUI_Partial_Refresh(60, 60, 80, 80);
            }
            Paint_DrawRectangle(60, 60, 80, 80, WHITE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
            Paint_DrawRectangle(60, 60, 80, 80, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
            Paint_DrawString_EN(63, 60, "R", &Font24, IMAGE_BACKGROUND, BLUE);
            GUI_Partial_Refresh(60, 60, 80, 80);
        }
        if(GET_KEY_PRESS == 0) {
            while(GET_KEY_PRESS == 0) {
                Paint_DrawRectangle(40, 60, 60, 80, BLUE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
                GUI_Partial_Refresh(40, 60, 60, 80);
            }
            Paint_DrawRectangle(40, 60, 60, 80, WHITE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
            Paint_DrawRectangle(40, 60, 60, 80, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
            Paint_DrawString_EN(43, 60, "P", &Font24, IMAGE_BACKGROUND, BLUE);
            GUI_Partial_Refresh(40, 60, 60, 80);
        }
        if(GET_KEY1 == 0) {
            while(GET_KEY1 == 0) {
                Paint_DrawRectangle(95, 40, 120, 60, BLUE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
                GUI_Partial_Refresh(95, 40, 120, 60);
            }
            Paint_DrawRectangle(95, 40, 120, 60, WHITE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
            Paint_DrawRectangle(95, 40, 120, 60, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
            Paint_DrawString_EN(98, 43, "K1", &Font16, IMAGE_BACKGROUND, BLUE);
            GUI_Partial_Refresh(95, 40, 120, 60);
        }
        if(GET_KEY2 == 0) {
            while(GET_KEY2 == 0) {
                Paint_DrawRectangle(95, 60, 120, 80, BLUE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
                GUI_Partial_Refresh(95, 60, 120, 80);
            }
            Paint_DrawRectangle(95, 60, 120, 80, WHITE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
            Paint_DrawRectangle(95, 60, 120, 80, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
            Paint_DrawString_EN(98, 63, "K2", &Font16, IMAGE_BACKGROUND, BLUE);
            GUI_Partial_Refresh(95, 60, 120, 80);
        }
        if(GET_KEY3 == 0) {
            while(GET_KEY3 == 0) {
                Paint_DrawRectangle(95, 80, 120, 100, BLUE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
                GUI_Partial_Refresh(95, 80, 120, 100);
            }
            Paint_DrawRectangle(95, 80, 120, 100, WHITE, DOT_PIXEL_DFT, DRAW_FILL_FULL);
            Paint_DrawRectangle(95, 80, 120, 100, RED, DOT_PIXEL_DFT, DRAW_FILL_EMPTY);
            Paint_DrawString_EN(98, 83, "K3", &Font16, IMAGE_BACKGROUND, BLUE);
            GUI_Partial_Refresh(95, 80, 120, 100);
        }
    }
}